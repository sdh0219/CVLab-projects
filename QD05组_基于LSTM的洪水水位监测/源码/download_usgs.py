import json
import time

import pandas as pd
import requests

from config import (
    CLEAN_DATA_PATH,
    DATA_DIR,
    END_DATE,
    RAINFALL_RAW_DATA_PATH,
    RAW_DATA_PATH,
    SITE_LATITUDE,
    SITE_LONGITUDE,
    START_DATE,
    USGS_SITE,
)


USGS_INSTANT_VALUES_URL = "https://waterservices.usgs.gov/nwis/iv/"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def year_ranges(start_date: str, end_date: str) -> list[tuple[str, str]]:
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    ranges = []
    current = start

    while current <= end:
        chunk_end = min(pd.Timestamp(year=current.year, month=12, day=31), end)
        ranges.append((current.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        current = chunk_end + pd.Timedelta(days=1)

    return ranges


def fetch_chunk(start_date: str, end_date: str) -> dict:
    params = {
        "format": "json",
        "sites": USGS_SITE,
        "parameterCd": "00065,00060",
        "startDT": start_date,
        "endDT": end_date,
        "siteStatus": "all",
    }
    response = requests.get(USGS_INSTANT_VALUES_URL, params=params, timeout=120)
    response.raise_for_status()
    return response.json()


def fetch_rainfall_chunk(start_date: str, end_date: str) -> dict:
    params = {
        "latitude": SITE_LATITUDE,
        "longitude": SITE_LONGITUDE,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "precipitation",
        "precipitation_unit": "mm",
        "timezone": "GMT",
        "models": "era5",
    }
    for attempt in range(1, 6):
        try:
            response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=180)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            if attempt == 5:
                raise
            delay = 2**attempt
            print(f"Rainfall request failed; retrying in {delay} seconds ({attempt}/5)...")
            time.sleep(delay)
    raise RuntimeError("Rainfall request retry loop exited unexpectedly.")


def parse_timeseries(payloads: list[dict]) -> pd.DataFrame:
    series_frames = []

    for payload in payloads:
        time_series = payload.get("value", {}).get("timeSeries", [])
        for item in time_series:
            parameter_code = item["variable"]["variableCode"][0]["value"]
            if parameter_code == "00065":
                column_name = "stage_ft"
            elif parameter_code == "00060":
                column_name = "discharge_cfs"
            else:
                continue

            values = item.get("values", [{}])[0].get("value", [])
            rows = [
                {
                    "datetime": entry["dateTime"],
                    column_name: pd.to_numeric(entry["value"], errors="coerce"),
                }
                for entry in values
            ]
            if rows:
                series_frames.append(pd.DataFrame(rows))

    if not series_frames:
        raise ValueError("USGS response did not contain usable instantaneous values.")

    normalized = []
    for frame in series_frames:
        frame["datetime"] = pd.to_datetime(frame["datetime"], utc=True)
        normalized.append(frame)

    combined = pd.concat(normalized, ignore_index=True, sort=False)
    value_columns = [column for column in ["stage_ft", "discharge_cfs"] if column in combined.columns]
    combined = combined.groupby("datetime", as_index=False)[value_columns].mean()
    return combined.sort_values("datetime")


def parse_rainfall(payloads: list[dict]) -> pd.DataFrame:
    frames = []
    for payload in payloads:
        hourly = payload.get("hourly", {})
        times = hourly.get("time", [])
        precipitation = hourly.get("precipitation", [])
        if len(times) != len(precipitation):
            raise ValueError("Rainfall response contains mismatched time and precipitation arrays.")
        if times:
            frames.append(
                pd.DataFrame(
                    {
                        "datetime": pd.to_datetime(times, utc=True),
                        "precipitation_mm": pd.to_numeric(precipitation, errors="coerce"),
                    }
                )
            )

    if not frames:
        raise ValueError("Open-Meteo response did not contain hourly precipitation.")

    rainfall = pd.concat(frames, ignore_index=True)
    rainfall = rainfall.drop_duplicates(subset="datetime", keep="last").sort_values("datetime")
    if rainfall["precipitation_mm"].isna().any():
        last_valid_index = rainfall["precipitation_mm"].last_valid_index()
        if last_valid_index is None:
            raise ValueError("Rainfall data does not contain any usable values.")
        interior_missing = rainfall.loc[:last_valid_index, "precipitation_mm"].isna()
        if interior_missing.any():
            missing = int(interior_missing.sum())
            raise ValueError(f"Rainfall data contains {missing} missing values inside its coverage period.")
        trailing_missing = len(rainfall) - last_valid_index - 1
        print(f"Dropping {trailing_missing} unavailable rainfall hours at the end of the period.")
        rainfall = rainfall.loc[:last_valid_index].copy()
    rainfall["precipitation_mm"] = rainfall["precipitation_mm"].clip(lower=0)
    return rainfall


def download_hourly_rainfall() -> pd.DataFrame:
    if RAINFALL_RAW_DATA_PATH.exists():
        print(f"Using existing rainfall data: {RAINFALL_RAW_DATA_PATH}")
        payloads = json.loads(RAINFALL_RAW_DATA_PATH.read_text(encoding="utf-8"))
        values = [
            value
            for payload in payloads
            for value in payload.get("hourly", {}).get("precipitation", [])
        ]
        if values and all(value is None for value in values):
            print("Existing rainfall cache contains no usable values; rebuilding it.")
            payloads = []
    else:
        payloads = []

    covered_years = {
        pd.Timestamp(payload["hourly"]["time"][0]).year
        for payload in payloads
        if payload.get("hourly", {}).get("time")
    }
    for start_date, end_date in year_ranges(START_DATE, END_DATE):
        year = pd.Timestamp(start_date).year
        if year in covered_years:
            continue
        print(f"Downloading rainfall {start_date} to {end_date}...")
        payloads.append(fetch_rainfall_chunk(start_date, end_date))
        RAINFALL_RAW_DATA_PATH.write_text(json.dumps(payloads), encoding="utf-8")

    return parse_rainfall(payloads)


def download_instantaneous_values() -> pd.DataFrame:
    if RAW_DATA_PATH.exists():
        print(f"Using existing raw data: {RAW_DATA_PATH}")
        payloads = json.loads(RAW_DATA_PATH.read_text(encoding="utf-8"))
    else:
        payloads = []
        for start_date, end_date in year_ranges(START_DATE, END_DATE):
            print(f"Downloading {start_date} to {end_date}...")
            payloads.append(fetch_chunk(start_date, end_date))
        RAW_DATA_PATH.write_text(json.dumps(payloads), encoding="utf-8")

    observed = parse_timeseries(payloads)
    rainfall = download_hourly_rainfall().set_index("datetime")
    clean = observed.set_index("datetime").resample("1h").mean()
    clean["stage_ft"] = clean["stage_ft"].interpolate(limit_direction="both")
    if "discharge_cfs" in clean.columns:
        clean["discharge_cfs"] = clean["discharge_cfs"].interpolate(limit_direction="both")

    hydrology_rows = len(clean)
    clean = clean.join(rainfall, how="inner")
    if len(clean) < hydrology_rows:
        print(
            f"Trimmed {hydrology_rows - len(clean)} hydrology hours outside the available "
            "rainfall period."
        )

    clean["stage_m"] = clean["stage_ft"] * 0.3048
    clean = clean.rename_axis("datetime").reset_index()
    return clean


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    clean = download_instantaneous_values()
    clean.to_csv(CLEAN_DATA_PATH, index=False, encoding="utf-8")
    print(f"Prepared {len(clean)} hourly hydrology and rainfall records for USGS site {USGS_SITE}.")
    print(f"Clean data saved to {CLEAN_DATA_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
