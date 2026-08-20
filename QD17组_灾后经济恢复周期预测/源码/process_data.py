from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
RAW_DIR = PROJECT_DIR / "data" / "raw"
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"

USGS_RAW = RAW_DIR / "usgs_earthquakes_usa_m45_1990_2026.csv"
NOAA_LOSSES = PROCESSED_DIR / "significant_earthquake_losses_usa_1990_2026.csv"
USGS_YEARLY = PROCESSED_DIR / "usgs_earthquake_yearly_features_usa_m45_1990_2026.csv"
BEA_SAGDP1 = RAW_DIR / "bea_sagdp1_all_areas_1997_2025.csv"
BEA_SAGDP2 = RAW_DIR / "bea_sagdp2_all_areas_1997_2025.csv"

STATE_OR_TERRITORY_TO_CODE = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "District of Columbia": "DC",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Puerto Rico": "PR",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
    "U.S. Virgin Islands": "VI",
    "Virgin Islands": "VI",
    "Guam": "GU",
    "Northern Mariana Islands": "MP",
    "American Samoa": "AS",
}


LOSS_FILL_COLUMNS = [
    "noaa_significant_event_count",
    "noaa_deaths_sum",
    "noaa_injuries_sum",
    "noaa_damage_million_usd_sum",
    "noaa_houses_destroyed_sum",
    "noaa_houses_damaged_sum",
    "noaa_max_intensity",
    "noaa_max_magnitude",
]


def extract_area_code(place: object) -> str | None:
    if pd.isna(place):
        return None

    text = str(place)
    for name, code in sorted(STATE_OR_TERRITORY_TO_CODE.items(), key=lambda item: -len(item[0])):
        if re.search(rf"\b{re.escape(name)}\b", text, flags=re.IGNORECASE):
            return code
    return None


def load_usgs_events() -> pd.DataFrame:
    usgs = pd.read_csv(USGS_RAW)
    usgs["time"] = pd.to_datetime(usgs["time"], utc=True, errors="coerce")
    usgs["event_date"] = usgs["time"].dt.date.astype("string")
    usgs["year"] = usgs["time"].dt.year
    usgs["month"] = usgs["time"].dt.month
    usgs["area"] = usgs["place"].apply(extract_area_code)
    usgs = usgs.dropna(subset=["year", "mag", "depth", "latitude", "longitude"])
    return usgs


def build_noaa_state_year_features(noaa: pd.DataFrame) -> pd.DataFrame:
    noaa = noaa.copy()
    noaa["area"] = noaa["area"].astype("string")

    numeric_columns = [
        "deaths",
        "injuries",
        "damage_million_usd",
        "houses_destroyed",
        "houses_damaged",
        "intensity",
        "magnitude",
    ]
    for column in numeric_columns:
        if column in noaa.columns:
            noaa[column] = pd.to_numeric(noaa[column], errors="coerce")

    grouped = (
        noaa.groupby(["area", "year"], as_index=False)
        .agg(
            noaa_significant_event_count=("noaa_event_id", "count"),
            noaa_deaths_sum=("deaths", "sum"),
            noaa_injuries_sum=("injuries", "sum"),
            noaa_damage_million_usd_sum=("damage_million_usd", "sum"),
            noaa_houses_destroyed_sum=("houses_destroyed", "sum"),
            noaa_houses_damaged_sum=("houses_damaged", "sum"),
            noaa_max_intensity=("intensity", "max"),
            noaa_max_magnitude=("magnitude", "max"),
        )
        .sort_values(["area", "year"])
    )
    return grouped


def clean_bea_geo_name(value: object) -> str:
    return str(value).replace("*", "").strip()


def melt_bea_years(df: pd.DataFrame, value_name: str) -> pd.DataFrame:
    year_columns = [column for column in df.columns if re.fullmatch(r"\d{4}", str(column))]
    melted = df.melt(
        id_vars=["GeoName", "LineCode", "Description"],
        value_vars=year_columns,
        var_name="year",
        value_name=value_name,
    )
    melted["year"] = pd.to_numeric(melted["year"], errors="coerce").astype("Int64")
    melted[value_name] = pd.to_numeric(melted[value_name], errors="coerce")
    melted["geo_name_clean"] = melted["GeoName"].apply(clean_bea_geo_name)
    melted["area"] = melted["geo_name_clean"].map(STATE_OR_TERRITORY_TO_CODE)
    return melted.dropna(subset=["area", "year"])


def build_bea_state_year_features() -> pd.DataFrame:
    if not BEA_SAGDP1.exists() or not BEA_SAGDP2.exists():
        raise FileNotFoundError("BEA GDP files are missing. Run `python download_data.py` first.")

    sagdp1 = pd.read_csv(BEA_SAGDP1)
    sagdp2 = pd.read_csv(BEA_SAGDP2)

    sagdp1["LineCode"] = pd.to_numeric(sagdp1["LineCode"], errors="coerce")
    total = melt_bea_years(sagdp1[sagdp1["LineCode"].isin([1, 3])], "value")
    total = (
        total.pivot_table(index=["area", "year"], columns="LineCode", values="value", aggfunc="first")
        .reset_index()
        .rename(
            columns={
                1.0: "gdp_real_million_2017usd",
                3.0: "gdp_current_million_usd",
            }
        )
    )

    sagdp2["LineCode"] = pd.to_numeric(sagdp2["LineCode"], errors="coerce")
    sector_line_codes = {
        1.0: "industry_total_million_usd",
        3.0: "industry_agriculture_million_usd",
        11.0: "industry_construction_million_usd",
        12.0: "industry_manufacturing_million_usd",
        92.0: "industry_private_services_million_usd",
    }
    sectors = melt_bea_years(sagdp2[sagdp2["LineCode"].isin(sector_line_codes)], "value")
    sectors = (
        sectors.pivot_table(index=["area", "year"], columns="LineCode", values="value", aggfunc="first")
        .reset_index()
        .rename(columns=sector_line_codes)
    )

    bea = total.merge(sectors, on=["area", "year"], how="outer")
    denominator = bea["industry_total_million_usd"].replace(0, pd.NA)
    bea["industry_agriculture_share"] = bea["industry_agriculture_million_usd"] / denominator
    bea["industry_construction_share"] = bea["industry_construction_million_usd"] / denominator
    bea["industry_manufacturing_share"] = bea["industry_manufacturing_million_usd"] / denominator
    bea["industry_private_services_share"] = bea["industry_private_services_million_usd"] / denominator
    return bea


def build_integrated_dataset(limit: int, random_state: int) -> pd.DataFrame:
    usgs = load_usgs_events()
    noaa = pd.read_csv(NOAA_LOSSES)
    yearly = pd.read_csv(USGS_YEARLY)
    noaa_state_year = build_noaa_state_year_features(noaa)
    bea_state_year = build_bea_state_year_features()

    model = usgs.rename(
        columns={
            "id": "usgs_event_id",
            "mag": "magnitude",
            "magType": "magnitude_type",
            "depth": "depth_km",
            "place": "place_name",
            "status": "review_status",
        }
    )
    model = model[
        [
            "usgs_event_id",
            "event_date",
            "year",
            "month",
            "area",
            "place_name",
            "latitude",
            "longitude",
            "depth_km",
            "magnitude",
            "magnitude_type",
            "review_status",
            "locationSource",
            "magSource",
        ]
    ].copy()

    yearly = yearly.rename(
        columns={
            "earthquake_count": "year_earthquake_count",
            "max_magnitude": "year_max_magnitude",
            "avg_magnitude": "year_avg_magnitude",
            "min_depth_km": "year_min_depth_km",
            "avg_depth_km": "year_avg_depth_km",
            "major_earthquake_flag": "year_major_earthquake_flag",
        }
    )

    model = model.merge(yearly, on="year", how="left")
    model = model.merge(noaa_state_year, on=["area", "year"], how="left")
    model = model.merge(bea_state_year, on=["area", "year"], how="left")

    for column in LOSS_FILL_COLUMNS:
        if column not in model.columns:
            model[column] = 0
        model[column] = model[column].fillna(0)

    model["has_noaa_loss_record"] = (model["noaa_significant_event_count"] > 0).astype(int)
    model["major_event_flag"] = (model["magnitude"] >= 6.0).astype(int)
    model["shallow_event_flag"] = (model["depth_km"] <= 70).astype(int)
    model["very_shallow_event_flag"] = (model["depth_km"] <= 20).astype(int)

    # A simple transparent severity index for sorting and exploratory analysis.
    model["event_severity_score"] = (
        model["magnitude"].fillna(0) * 10
        + model["major_event_flag"] * 10
        + model["shallow_event_flag"] * 3
        + model["has_noaa_loss_record"] * 5
    )

    model = model.dropna(subset=["area", "gdp_current_million_usd"]).reset_index(drop=True)
    if len(model) < limit:
        raise ValueError(f"Only {len(model)} rows are available after filtering, cannot build {limit} rows.")

    loss_rows = model[model["has_noaa_loss_record"] == 1]
    other_rows = model[model["has_noaa_loss_record"] == 0]

    target_loss_rows = min(len(loss_rows), limit // 2)
    sampled_parts: list[pd.DataFrame] = []
    if target_loss_rows:
        sampled_parts.append(loss_rows.sample(n=target_loss_rows, random_state=random_state))

    remaining = limit - sum(len(part) for part in sampled_parts)
    if remaining:
        sampled_parts.append(other_rows.sample(n=remaining, random_state=random_state))

    dataset = pd.concat(sampled_parts, ignore_index=True)
    dataset = dataset.sample(frac=1, random_state=random_state).reset_index(drop=True)
    dataset.insert(0, "sample_id", range(1, len(dataset) + 1))
    return dataset


def write_outputs(dataset: pd.DataFrame, limit: int, random_state: int) -> None:
    output_path = PROCESSED_DIR / f"earthquake_integrated_dataset_{limit}.csv"
    dataset.to_csv(output_path, index=False, encoding="utf-8-sig")

    metadata = {
        "output_file": str(output_path.relative_to(PROJECT_DIR)).replace("\\", "/"),
        "rows": int(len(dataset)),
        "columns": int(len(dataset.columns)),
        "random_state": random_state,
        "sources": [
            "USGS Earthquake Catalog",
            "NOAA/NCEI Significant Earthquake Database",
            "BEA Regional Economic Accounts",
        ],
        "source_files": {
            "usgs_raw": str(USGS_RAW.relative_to(PROJECT_DIR)).replace("\\", "/"),
            "noaa_losses": str(NOAA_LOSSES.relative_to(PROJECT_DIR)).replace("\\", "/"),
            "usgs_yearly": str(USGS_YEARLY.relative_to(PROJECT_DIR)).replace("\\", "/"),
            "bea_sagdp1": str(BEA_SAGDP1.relative_to(PROJECT_DIR)).replace("\\", "/"),
            "bea_sagdp2": str(BEA_SAGDP2.relative_to(PROJECT_DIR)).replace("\\", "/"),
        },
        "year_range": [
            int(dataset["year"].min()),
            int(dataset["year"].max()),
        ],
        "loss_record_rows": int(dataset["has_noaa_loss_record"].sum()),
        "columns_list": list(dataset.columns),
    }
    metadata_path = PROCESSED_DIR / f"earthquake_integrated_dataset_{limit}_metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved {len(dataset)} rows to {output_path.relative_to(PROJECT_DIR)}")
    print(f"Saved metadata to {metadata_path.relative_to(PROJECT_DIR)}")
    print(f"Rows with NOAA/NCEI loss records: {metadata['loss_record_rows']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an integrated earthquake dataset.")
    parser.add_argument("--limit", type=int, default=2000, help="Number of rows to output.")
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    dataset = build_integrated_dataset(args.limit, args.random_state)
    write_outputs(dataset, args.limit, args.random_state)


if __name__ == "__main__":
    main()
