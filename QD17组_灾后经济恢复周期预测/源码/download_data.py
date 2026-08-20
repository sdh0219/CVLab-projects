from __future__ import annotations

import argparse
import io
import json
import zipfile
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
RAW_DIR = PROJECT_DIR / "data" / "raw"
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"

START_YEAR = 1990
END_DATE = date(2026, 6, 16)
USER_AGENT = "earthquake-recovery-dataset/1.0"
BEA_SAGDP_URL = "https://apps.bea.gov/regional/zip/SAGDP.zip"


def open_url(url: str, accept: str = "*/*", timeout: int = 60) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def download_usgs_usa_earthquakes(min_magnitude: float) -> pd.DataFrame:
    """Download USGS earthquake events in a broad U.S. bounding box by year."""
    frames: list[pd.DataFrame] = []
    base_url = "https://earthquake.usgs.gov/fdsnws/event/1/query"

    for year in range(START_YEAR, END_DATE.year + 1):
        start = date(year, 1, 1)
        end = date(year + 1, 1, 1) if year < END_DATE.year else END_DATE

        params = {
            "format": "csv",
            "starttime": start.isoformat(),
            "endtime": end.isoformat(),
            "minmagnitude": min_magnitude,
            "eventtype": "earthquake",
            "orderby": "time-asc",
            "limit": 20000,
            # Broad U.S. window: contiguous U.S., Alaska, Hawaii, and Puerto Rico area.
            "minlatitude": 18,
            "maxlatitude": 72,
            "minlongitude": -180,
            "maxlongitude": -60,
        }
        url = f"{base_url}?{urlencode(params)}"
        print(f"Downloading USGS {year}...")
        payload = open_url(url, accept="text/csv")
        df = pd.read_csv(io.BytesIO(payload))
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    earthquakes = pd.concat(frames, ignore_index=True)
    earthquakes = earthquakes.drop_duplicates(subset=["id"]).reset_index(drop=True)
    earthquakes["time"] = pd.to_datetime(earthquakes["time"], utc=True, errors="coerce")
    earthquakes["year"] = earthquakes["time"].dt.year
    earthquakes["month"] = earthquakes["time"].dt.month
    earthquakes["event_date"] = earthquakes["time"].dt.date.astype("string")
    earthquakes["source"] = "USGS Earthquake Catalog"
    return earthquakes


def download_noaa_ncei_significant_earthquakes() -> pd.DataFrame:
    """Download NOAA/NCEI Significant Earthquake records for the United States."""
    base_url = "https://www.ngdc.noaa.gov/hazel/hazard-service/api/v1/earthquakes"
    items: list[dict] = []
    page = 1
    total_pages = 1

    while page <= total_pages:
        params = {
            "country": "USA",
            "minYear": START_YEAR,
            "maxYear": END_DATE.year,
            "itemsPerPage": 200,
            "page": page,
        }
        url = f"{base_url}?{urlencode(params)}"
        print(f"Downloading NOAA/NCEI page {page}...")
        payload = open_url(url, accept="application/json")
        data = json.loads(payload.decode("utf-8"))
        items.extend(data.get("items", []))
        total_pages = int(data.get("totalPages", 1))
        page += 1

    losses = pd.json_normalize(items)
    if losses.empty:
        return losses

    losses["source"] = "NOAA/NCEI Significant Earthquake Database"
    return losses


def download_bea_state_gdp() -> dict[str, Path]:
    """Download BEA state GDP tables used for economic features."""
    print("Downloading BEA state GDP ZIP...")
    payload = open_url(BEA_SAGDP_URL, accept="*/*")
    zip_path = RAW_DIR / "bea_sagdp_1997_2025.zip"
    zip_path.write_bytes(payload)

    outputs = {
        "bea_sagdp1": RAW_DIR / "bea_sagdp1_all_areas_1997_2025.csv",
        "bea_sagdp2": RAW_DIR / "bea_sagdp2_all_areas_1997_2025.csv",
    }
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        outputs["bea_sagdp1"].write_bytes(archive.read("SAGDP1__ALL_AREAS_1997_2025.csv"))
        outputs["bea_sagdp2"].write_bytes(archive.read("SAGDP2__ALL_AREAS_1997_2025.csv"))

    outputs["bea_zip"] = zip_path
    return outputs


def build_processed_noaa(losses: pd.DataFrame) -> pd.DataFrame:
    if losses.empty:
        return losses

    selected_columns = [
        "id",
        "year",
        "month",
        "day",
        "locationName",
        "area",
        "country",
        "latitude",
        "longitude",
        "eqDepth",
        "eqMagnitude",
        "intensity",
        "deaths",
        "injuries",
        "damageMillionsDollars",
        "damageAmountOrder",
        "housesDestroyed",
        "housesDamaged",
        "source",
    ]
    existing = [column for column in selected_columns if column in losses.columns]
    processed = losses[existing].copy()
    processed = processed.rename(
        columns={
            "id": "noaa_event_id",
            "locationName": "location_name",
            "eqDepth": "depth_km",
            "eqMagnitude": "magnitude",
            "damageMillionsDollars": "damage_million_usd",
            "damageAmountOrder": "damage_amount_order",
            "housesDestroyed": "houses_destroyed",
            "housesDamaged": "houses_damaged",
        }
    )
    return processed


def build_yearly_usgs_features(earthquakes: pd.DataFrame) -> pd.DataFrame:
    if earthquakes.empty:
        return earthquakes

    aggregations = {
        "earthquake_count": ("id", "count"),
        "max_magnitude": ("mag", "max"),
        "avg_magnitude": ("mag", "mean"),
        "min_depth_km": ("depth", "min"),
        "avg_depth_km": ("depth", "mean"),
    }
    if "mmi" in earthquakes.columns:
        aggregations["max_reported_mmi"] = ("mmi", "max")
    if "sig" in earthquakes.columns:
        aggregations["max_significance"] = ("sig", "max")

    grouped = (
        earthquakes.groupby("year", as_index=False)
        .agg(**aggregations)
        .sort_values("year")
    )
    grouped["major_earthquake_flag"] = (grouped["max_magnitude"] >= 6.0).astype(int)
    return grouped


def magnitude_tag(min_magnitude: float) -> str:
    scaled = int(round(min_magnitude * 10))
    return f"m{scaled}"


def write_summary(
    usgs: pd.DataFrame,
    noaa_raw: pd.DataFrame,
    noaa_processed: pd.DataFrame,
    usgs_yearly: pd.DataFrame,
    min_magnitude: float,
    usgs_raw_path: Path,
    usgs_yearly_path: Path,
    noaa_raw_path: Path,
    noaa_processed_path: Path,
    bea_paths: dict[str, Path],
) -> None:
    summary = {
        "download_date": END_DATE.isoformat(),
        "usgs_min_magnitude": min_magnitude,
        "usgs_rows": int(len(usgs)),
        "noaa_ncei_rows": int(len(noaa_raw)),
        "files": {
            "usgs_raw": str(usgs_raw_path.relative_to(PROJECT_DIR)).replace("\\", "/"),
            "noaa_ncei_raw": str(noaa_raw_path.relative_to(PROJECT_DIR)).replace("\\", "/"),
            "noaa_ncei_processed": str(noaa_processed_path.relative_to(PROJECT_DIR)).replace("\\", "/"),
            "usgs_yearly_features": str(usgs_yearly_path.relative_to(PROJECT_DIR)).replace("\\", "/"),
            "bea_sagdp_zip": str(bea_paths["bea_zip"].relative_to(PROJECT_DIR)).replace("\\", "/"),
            "bea_sagdp1": str(bea_paths["bea_sagdp1"].relative_to(PROJECT_DIR)).replace("\\", "/"),
            "bea_sagdp2": str(bea_paths["bea_sagdp2"].relative_to(PROJECT_DIR)).replace("\\", "/"),
        },
        "usgs_year_range": [
            int(usgs["year"].min()) if not usgs.empty else None,
            int(usgs["year"].max()) if not usgs.empty else None,
        ],
        "noaa_year_range": [
            int(noaa_processed["year"].min()) if not noaa_processed.empty else None,
            int(noaa_processed["year"].max()) if not noaa_processed.empty else None,
        ],
        "usgs_yearly_rows": int(len(usgs_yearly)),
        "noaa_processed_columns": list(noaa_processed.columns),
    }
    (PROJECT_DIR / "data" / "dataset_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download earthquake recovery source data.")
    parser.add_argument("--min-magnitude", type=float, default=4.5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    mag_tag = magnitude_tag(args.min_magnitude)

    usgs = download_usgs_usa_earthquakes(args.min_magnitude)
    usgs_raw_path = RAW_DIR / f"usgs_earthquakes_usa_{mag_tag}_1990_2026.csv"
    usgs.to_csv(usgs_raw_path, index=False, encoding="utf-8-sig")

    usgs_yearly = build_yearly_usgs_features(usgs)
    usgs_yearly_path = PROCESSED_DIR / f"usgs_earthquake_yearly_features_usa_{mag_tag}_1990_2026.csv"
    usgs_yearly.to_csv(usgs_yearly_path, index=False, encoding="utf-8-sig")

    noaa_raw = download_noaa_ncei_significant_earthquakes()
    noaa_raw_path = RAW_DIR / "noaa_ncei_significant_earthquakes_usa_1990_2026.csv"
    noaa_raw.to_csv(noaa_raw_path, index=False, encoding="utf-8-sig")

    noaa_processed = build_processed_noaa(noaa_raw)
    noaa_processed_path = PROCESSED_DIR / "significant_earthquake_losses_usa_1990_2026.csv"
    noaa_processed.to_csv(noaa_processed_path, index=False, encoding="utf-8-sig")

    bea_paths = download_bea_state_gdp()

    write_summary(
        usgs,
        noaa_raw,
        noaa_processed,
        usgs_yearly,
        args.min_magnitude,
        usgs_raw_path,
        usgs_yearly_path,
        noaa_raw_path,
        noaa_processed_path,
        bea_paths,
    )

    print("\nDownloaded files:")
    print(f"- {usgs_raw_path.relative_to(PROJECT_DIR)} rows={len(usgs)}")
    print(f"- {usgs_yearly_path.relative_to(PROJECT_DIR)} rows={len(usgs_yearly)}")
    print(f"- {noaa_raw_path.relative_to(PROJECT_DIR)} rows={len(noaa_raw)}")
    print(f"- {noaa_processed_path.relative_to(PROJECT_DIR)} rows={len(noaa_processed)}")
    print(f"- {bea_paths['bea_sagdp1'].relative_to(PROJECT_DIR)}")
    print(f"- {bea_paths['bea_sagdp2'].relative_to(PROJECT_DIR)}")
    print("- data/dataset_summary.json")


if __name__ == "__main__":
    main()
