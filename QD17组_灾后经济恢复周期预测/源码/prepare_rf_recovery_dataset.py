from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from process_data import (
    LOSS_FILL_COLUMNS,
    NOAA_LOSSES,
    PROCESSED_DIR,
    PROJECT_DIR,
    USGS_YEARLY,
    build_bea_state_year_features,
    build_noaa_state_year_features,
    load_usgs_events,
)


TARGET_COLUMN = "recovery_cycle_years"
DEFAULT_OUTPUT = "earthquake_rf_recovery_dataset.csv"


def build_full_event_table(max_horizon: int) -> pd.DataFrame:
    usgs = load_usgs_events()
    usgs = usgs.drop_duplicates(subset=["id"]).copy()
    usgs = usgs[
        (usgs["status"].eq("reviewed"))
        & (usgs["mag"].between(4.5, 10, inclusive="both"))
        & (usgs["depth"].ge(0))
    ].copy()

    noaa = pd.read_csv(NOAA_LOSSES)
    yearly = pd.read_csv(USGS_YEARLY)
    noaa_state_year = build_noaa_state_year_features(noaa)
    bea_state_year = build_bea_state_year_features()

    events = usgs.rename(
        columns={
            "id": "usgs_event_id",
            "mag": "magnitude",
            "magType": "magnitude_type",
            "depth": "depth_km",
            "place": "place_name",
            "status": "review_status",
        }
    )
    events = events[
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

    events = events.merge(yearly, on="year", how="left")
    events = events.merge(noaa_state_year, on=["area", "year"], how="left")
    events = events.merge(bea_state_year, on=["area", "year"], how="left")

    for column in LOSS_FILL_COLUMNS:
        if column not in events.columns:
            events[column] = 0
        events[column] = events[column].fillna(0)

    events["has_noaa_loss_record"] = (events["noaa_significant_event_count"] > 0).astype(int)
    events["major_event_flag"] = (events["magnitude"] >= 6.0).astype(int)
    events["shallow_event_flag"] = (events["depth_km"] <= 70).astype(int)
    events["very_shallow_event_flag"] = (events["depth_km"] <= 20).astype(int)
    events["event_severity_score"] = (
        events["magnitude"].fillna(0) * 10
        + events["major_event_flag"] * 10
        + events["shallow_event_flag"] * 3
        + events["has_noaa_loss_record"] * 5
    )

    gdp_lookup = bea_state_year.set_index(["area", "year"])["gdp_real_million_2017usd"].to_dict()
    events["gdp_pre_1y"] = events.apply(
        lambda row: gdp_lookup.get((row["area"], int(row["year"]) - 1)), axis=1
    )
    events["gdp_pre_2y"] = events.apply(
        lambda row: gdp_lookup.get((row["area"], int(row["year"]) - 2)), axis=1
    )
    events["gdp_pre_3y"] = events.apply(
        lambda row: gdp_lookup.get((row["area"], int(row["year"]) - 3)), axis=1
    )
    events["gdp_event_year"] = events["gdp_real_million_2017usd"]
    for horizon in range(1, max_horizon + 1):
        events[f"gdp_post_{horizon}y"] = events.apply(
            lambda row, h=horizon: gdp_lookup.get((row["area"], int(row["year"]) + h)), axis=1
        )

    required_gdp = ["gdp_pre_1y", "gdp_pre_2y", "gdp_pre_3y", "gdp_event_year"] + [
        f"gdp_post_{horizon}y" for horizon in range(1, max_horizon + 1)
    ]
    events = events.dropna(subset=["area", *required_gdp]).copy()
    for column in required_gdp:
        events = events[events[column] > 0]

    events["gdp_change_event_vs_pre"] = (
        events["gdp_event_year"] - events["gdp_pre_1y"]
    ) / events["gdp_pre_1y"]
    events["gdp_growth_pre_1y"] = events["gdp_change_event_vs_pre"]
    events["gdp_growth_pre_2y"] = (
        events["gdp_pre_1y"] - events["gdp_pre_2y"]
    ) / events["gdp_pre_2y"]
    events["gdp_growth_pre_3y"] = (
        events["gdp_pre_2y"] - events["gdp_pre_3y"]
    ) / events["gdp_pre_3y"]
    events["gdp_decline_from_pre_pct"] = (
        (events["gdp_pre_1y"] - events["gdp_event_year"]) / events["gdp_pre_1y"]
    ).clip(lower=0)
    events["gdp_growth_next_1y"] = (
        events["gdp_post_1y"] - events["gdp_event_year"]
    ) / events["gdp_event_year"]
    events[f"gdp_growth_next_{max_horizon}y"] = (
        events[f"gdp_post_{max_horizon}y"] - events["gdp_event_year"]
    ) / events["gdp_event_year"]

    events[TARGET_COLUMN] = events.apply(
        lambda row: recovery_cycle(row, max_horizon=max_horizon), axis=1
    )
    events["recovered_within_horizon"] = (events[TARGET_COLUMN] <= max_horizon).astype(int)
    events["recovery_target_note"] = events[TARGET_COLUMN].map(
        lambda value: f">{max_horizon}" if value == max_horizon + 1 else str(value)
    )
    events["damage_to_gdp_ratio"] = (
        events["noaa_damage_million_usd_sum"] / events["gdp_current_million_usd"]
    ).fillna(0)
    events["casualties_sum"] = events["noaa_deaths_sum"] + events["noaa_injuries_sum"]
    events["houses_affected_sum"] = (
        events["noaa_houses_destroyed_sum"] + events["noaa_houses_damaged_sum"]
    )
    return events.reset_index(drop=True)


def recovery_cycle(row: pd.Series, max_horizon: int) -> int:
    baseline = row["gdp_pre_1y"]
    if row["gdp_event_year"] >= baseline:
        return 0

    for horizon in range(1, max_horizon + 1):
        if row[f"gdp_post_{horizon}y"] >= baseline:
            return horizon
    return max_horizon + 1


def recommended_feature_columns() -> list[str]:
    return [
        "year",
        "month",
        "area",
        "latitude",
        "longitude",
        "depth_km",
        "magnitude",
        "magnitude_type",
        "year_earthquake_count",
        "year_max_magnitude",
        "year_avg_magnitude",
        "year_min_depth_km",
        "year_avg_depth_km",
        "year_major_earthquake_flag",
        "noaa_significant_event_count",
        "noaa_deaths_sum",
        "noaa_injuries_sum",
        "noaa_damage_million_usd_sum",
        "noaa_houses_destroyed_sum",
        "noaa_houses_damaged_sum",
        "noaa_max_intensity",
        "noaa_max_magnitude",
        "damage_to_gdp_ratio",
        "casualties_sum",
        "houses_affected_sum",
        "gdp_pre_3y",
        "gdp_pre_2y",
        "gdp_pre_1y",
        "gdp_event_year",
        "gdp_growth_pre_1y",
        "gdp_growth_pre_2y",
        "gdp_growth_pre_3y",
        "gdp_decline_from_pre_pct",
        "gdp_current_million_usd",
        "industry_agriculture_share",
        "industry_construction_share",
        "industry_manufacturing_share",
        "industry_private_services_share",
        "has_noaa_loss_record",
        "major_event_flag",
        "shallow_event_flag",
        "very_shallow_event_flag",
        "event_severity_score",
    ]


def select_reliable_rows(
    df: pd.DataFrame,
    limit: int,
    random_state: int,
    max_area_share: float,
) -> pd.DataFrame:
    # Keep real, high-quality matched records. Sampling is not class-balanced; it preserves
    # the natural distribution after reliability filters, while preventing one area from
    # dominating nearly the whole dataset.
    df = df.sort_values(["year", "event_date", "usgs_event_id"]).reset_index(drop=True)
    if len(df) <= limit:
        selected = df.copy()
    else:
        max_area_rows = max(1, int(limit * max_area_share))
        capped_parts = []
        leftover_parts = []
        for _, area_df in df.groupby("area", sort=False):
            if len(area_df) <= max_area_rows:
                capped_parts.append(area_df)
            else:
                sampled = area_df.sample(n=max_area_rows, random_state=random_state)
                capped_parts.append(sampled)
                leftover_parts.append(area_df.drop(sampled.index))

        candidate = pd.concat(capped_parts, ignore_index=False)
        if len(candidate) < limit and leftover_parts:
            remaining = limit - len(candidate)
            leftover = pd.concat(leftover_parts, ignore_index=False)
            fill = leftover.sample(n=min(remaining, len(leftover)), random_state=random_state)
            candidate = pd.concat([candidate, fill], ignore_index=False)

        if len(candidate) > limit:
            selected = candidate.sample(n=limit, random_state=random_state)
        else:
            selected = candidate
        selected = selected.sort_values(["year", "event_date", "usgs_event_id"])
    selected = selected.reset_index(drop=True)
    selected.insert(0, "sample_id", range(1, len(selected) + 1))
    return selected


def write_outputs(df: pd.DataFrame, args: argparse.Namespace) -> None:
    output_path = PROCESSED_DIR / args.output
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    feature_columns = [column for column in recommended_feature_columns() if column in df.columns]
    feature_path = PROCESSED_DIR / "earthquake_rf_feature_columns.txt"
    feature_path.write_text("\n".join(feature_columns) + "\n", encoding="utf-8")
    generic_feature_path = PROCESSED_DIR / "earthquake_recovery_feature_columns.txt"
    generic_feature_path.write_text("\n".join(feature_columns) + "\n", encoding="utf-8")

    metadata = {
        "output_file": str(output_path.relative_to(PROJECT_DIR)).replace("\\", "/"),
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "target_column": TARGET_COLUMN,
        "target_definition": (
            "Years until real GDP returns to at least the pre-disaster-year GDP level. "
            f"{args.max_horizon + 1} means not recovered within {args.max_horizon} years."
        ),
        "max_horizon_years": args.max_horizon,
        "random_state": args.random_state,
        "sampling_method": "Reliability-filtered random sample; no class balancing.",
        "max_area_share": args.max_area_share,
        "feature_columns_file": str(feature_path.relative_to(PROJECT_DIR)).replace("\\", "/"),
        "generic_feature_columns_file": str(generic_feature_path.relative_to(PROJECT_DIR)).replace("\\", "/"),
        "recommended_feature_columns": feature_columns,
        "excluded_from_features": [
            "sample_id",
            "usgs_event_id",
            "event_date",
            "place_name",
            "gdp_post_1y",
            "gdp_post_2y",
            "gdp_post_3y",
            "gdp_growth_next_1y",
            "gdp_growth_next_3y",
            TARGET_COLUMN,
            "recovered_within_horizon",
            "recovery_target_note",
        ],
        "year_range": [int(df["year"].min()), int(df["year"].max())],
        "target_distribution": {
            str(key): int(value) for key, value in df[TARGET_COLUMN].value_counts().sort_index().items()
        },
        "sources": [
            "USGS Earthquake Catalog",
            "NOAA/NCEI Significant Earthquake Database",
            "BEA Regional Economic Accounts",
        ],
    }
    metadata_path = PROCESSED_DIR / output_path.with_suffix(".metadata.json").name
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved dataset: {output_path.relative_to(PROJECT_DIR)} rows={len(df)} cols={len(df.columns)}")
    print(f"Saved metadata: {metadata_path.relative_to(PROJECT_DIR)}")
    print(f"Saved feature list: {feature_path.relative_to(PROJECT_DIR)}")
    print(f"Saved feature list: {generic_feature_path.relative_to(PROJECT_DIR)}")
    print(f"Target distribution: {metadata['target_distribution']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare reliable data for random forest recovery modeling.")
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--max-horizon", type=int, default=3)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--max-area-share", type=float, default=0.6)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    full = build_full_event_table(max_horizon=args.max_horizon)
    selected = select_reliable_rows(
        full,
        limit=args.limit,
        random_state=args.random_state,
        max_area_share=args.max_area_share,
    )
    write_outputs(selected, args)


if __name__ == "__main__":
    main()
