#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Project 01 Data Island Fusion Pipeline

适配你的实际目录结构：

C:/Users/Lenovo/Desktop/自然语言处理
├── 1_数据包
│   └── processed_data
│       ├── dataset_coverage_summary.csv
│       ├── weather_noaa_daily_summaries_clean.csv
│       ├── disaster_fema_la_county_clean.csv 或 DisasterDeclarationsSummaries_la_county.csv
│       ├── earthquake_usgs_la_region_clean.csv 或 usgs_earthquake_query_la_region.csv
│       ├── population_svi_la_county.geojson
│       ├── emergency_fire_ems_stations_la.geojson
│       ├── emergency_hospitals_la.geojson
│       ├── landslide_cgs_la_county.geojson
│       ├── unified_hazard_events.csv
│       ├── unified_monitoring_daily.csv
│       └── unified_resource_points.geojson
└── 2_源码
    └── 2_源码
        └── main.py

运行：
python C:/Users/Lenovo/Desktop/自然语言处理/2_源码/2_源码/main.py

输出：
2_源码/2_源码/outputs/processed
2_源码/2_源码/outputs/figures
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# =============================================================================
# 1. 路径设置：自动寻找项目根目录和数据目录
# =============================================================================

SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent


def find_project_root() -> Path:
    """
    从 main.py 所在目录向上查找数据目录，兼容两种布局：
    1. 项目根目录/1_数据包/processed_data          （原始开发布局）
    2. 项目根目录/数据集/1_数据包/processed_data   （课程交付布局，含"1 数据包"带空格变体）
    找到即返回"数据目录的上一级"（布局 1 返回项目根，布局 2 返回 数据集/1_数据包）。
    """
    candidates: List[Path] = []

    candidates.extend([SCRIPT_DIR] + list(SCRIPT_DIR.parents))

    cwd = Path.cwd().resolve()
    candidates.extend([cwd] + list(cwd.parents))

    # 数据目录的候选相对布局：目录名 -> 数据子目录名
    layouts = [
        ("1_数据包", "processed_data"),
        ("数据集", "processed_data"),          # 数据集根下直接放 processed_data
        ("数据集/1_数据包", "processed_data"),  # 交付布局（下划线）
        ("数据集/1 数据包", "processed_data"),  # 交付布局（带空格）
    ]

    seen = set()
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        for folder, sub in layouts:
            if (c / folder / sub).exists():
                return c / folder

    raise FileNotFoundError(
        "没有找到数据目录：1_数据包/processed_data 或 数据集/1_数据包/processed_data。\n"
        "请确认数据目录与 main.py 的相对位置（详见复现指南 2.4 节）"
    )


PROJECT_ROOT = find_project_root()
DATA_DIR = PROJECT_ROOT / "processed_data"
OUTPUT_DIR = SCRIPT_DIR / "outputs"
PROCESSED_OUT = OUTPUT_DIR / "processed"
FIGURE_OUT = OUTPUT_DIR / "figures"

PROCESSED_OUT.mkdir(parents=True, exist_ok=True)
FIGURE_OUT.mkdir(parents=True, exist_ok=True)


# =============================================================================
# 2. 工具函数
# =============================================================================

def print_header() -> None:
    print("=" * 80)
    print("Project 01 Data Island Fusion Pipeline")
    print(f"Script path:      {SCRIPT_PATH}")
    print(f"Project root:     {PROJECT_ROOT}")
    print(f"Data directory:   {DATA_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 80)


def first_existing(*names: str) -> Optional[Path]:
    for name in names:
        p = DATA_DIR / name
        if p.exists():
            return p
    return None


def read_csv_if_exists(path: Optional[Path]) -> pd.DataFrame:
    if path is None or not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="utf-8-sig")
    except Exception as e:
        print(f"[WARN] CSV read failed: {path} -> {e}")
        return pd.DataFrame()


def read_geojson_if_exists(path: Optional[Path]) -> Dict[str, Any]:
    if path is None or not path.exists():
        return {"type": "FeatureCollection", "features": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] GeoJSON read failed: {path} -> {e}")
        return {"type": "FeatureCollection", "features": []}


def find_col(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    if df.empty:
        return None
    lower_map = {str(c).lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    for col in df.columns:
        col_lower = str(col).lower()
        for cand in candidates:
            if cand.lower() in col_lower:
                return col
    return None


def to_numeric(s: Any) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def safe_date(series: Any) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.strftime("%Y-%m-%d")


def save_csv(df: pd.DataFrame, filename: str) -> Path:
    out = PROCESSED_OUT / filename
    df.to_csv(out, index=False, encoding="utf-8-sig")
    return out


def save_geojson(data: Dict[str, Any], filename: str) -> Path:
    out = PROCESSED_OUT / filename
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return out


def geojson_feature_count(data: Dict[str, Any]) -> int:
    return len(data.get("features", []))


def extract_xy_from_geometry(geometry: Optional[Dict[str, Any]]) -> Tuple[float, float]:
    """
    从 GeoJSON geometry 中提取一个代表点。
    - Point：直接取坐标
    - Polygon/MultiPolygon/LineString：递归取全部坐标平均值
    """
    if not geometry:
        return (np.nan, np.nan)

    coords = geometry.get("coordinates")
    if coords is None:
        return (np.nan, np.nan)

    points: List[Tuple[float, float]] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, (list, tuple)):
            if len(obj) >= 2 and isinstance(obj[0], (int, float)) and isinstance(obj[1], (int, float)):
                points.append((float(obj[0]), float(obj[1])))
            else:
                for x in obj:
                    walk(x)

    walk(coords)
    if not points:
        return (np.nan, np.nan)

    lon = float(np.mean([p[0] for p in points]))
    lat = float(np.mean([p[1] for p in points]))
    return lon, lat


# =============================================================================
# 3. 数据清洗函数
# =============================================================================

def clean_weather() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    path = first_existing(
        "weather_noaa_daily_summaries_clean.csv",
        "daily_summaries_noaa_la_2020_2025.csv",
        "daily-summaries-2026-06-15T04-09-57.csv",
    )
    raw = read_csv_if_exists(path)

    if raw.empty:
        out = pd.DataFrame(columns=[
            "date", "source_agency", "source_status", "station_id", "station_name",
            "latitude", "longitude", "indicator", "value"
        ])
        save_csv(out, "weather_clean.csv")
        return out, {"data_type": "weather", "records": 0, "source": "MISSING", "file": ""}

    date_col = find_col(raw, ["date", "DATE", "time"])
    station_col = find_col(raw, ["station_id", "station", "STATION"])
    name_col = find_col(raw, ["station_name", "name", "NAME"])
    lat_col = find_col(raw, ["latitude", "lat"])
    lon_col = find_col(raw, ["longitude", "lon", "lng"])

    wind_col = find_col(raw, ["wind_avg", "wind_speed_mps", "WDSP", "wind"])
    prcp_col = find_col(raw, ["precipitation", "precip_mm", "PRCP", "precip"])
    tmax_col = find_col(raw, ["temp_max_c", "TMAX", "MAX"])
    tmin_col = find_col(raw, ["temp_min_c", "TMIN", "MIN"])
    tmean_col = find_col(raw, ["temp_mean_c", "TAVG", "TEMP"])

    base = pd.DataFrame()
    base["date"] = safe_date(raw[date_col]) if date_col else ""
    base["station_id"] = raw[station_col].astype(str) if station_col else "NOAA_STATION"
    base["station_name"] = raw[name_col].astype(str) if name_col else "NOAA weather station"
    base["latitude"] = to_numeric(raw[lat_col]) if lat_col else np.nan
    base["longitude"] = to_numeric(raw[lon_col]) if lon_col else np.nan

    indicators: Dict[str, pd.Series] = {}

    if wind_col:
        indicators["wind_avg"] = to_numeric(raw[wind_col])
    if prcp_col:
        indicators["precipitation"] = to_numeric(raw[prcp_col])
    if tmax_col:
        indicators["temp_max_c"] = to_numeric(raw[tmax_col])
    if tmin_col:
        indicators["temp_min_c"] = to_numeric(raw[tmin_col])
    if tmean_col:
        indicators["temp_mean_c"] = to_numeric(raw[tmean_col])
    elif tmax_col and tmin_col:
        indicators["temp_mean_c"] = (to_numeric(raw[tmax_col]) + to_numeric(raw[tmin_col])) / 2

    rows: List[pd.DataFrame] = []
    for indicator, values in indicators.items():
        tmp = base.copy()
        tmp["indicator"] = indicator
        tmp["value"] = values
        tmp["source_agency"] = "NOAA"
        tmp["source_status"] = "real_downloaded"
        rows.append(tmp[[
            "date", "source_agency", "source_status", "station_id", "station_name",
            "latitude", "longitude", "indicator", "value"
        ]])

    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=[
        "date", "source_agency", "source_status", "station_id", "station_name",
        "latitude", "longitude", "indicator", "value"
    ])

    save_csv(out, "weather_clean.csv")
    return out, {
        "data_type": "weather",
        "records": len(out),
        "source": "real_downloaded",
        "file": path.name if path else "",
    }


def clean_fema() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    path = first_existing(
        "disaster_fema_la_county_clean.csv",
        "DisasterDeclarationsSummaries_la_county.csv",
        "DisasterDeclarationsSummaries.csv",
    )
    raw = read_csv_if_exists(path)

    if raw.empty:
        out = pd.DataFrame(columns=[
            "event_id", "event_date", "hazard_type", "source_agency", "source_status",
            "latitude", "longitude", "severity_metric", "severity_value", "location_name"
        ])
        save_csv(out, "fema_disaster_clean.csv")
        return out, {"data_type": "fema", "records": 0, "source": "MISSING", "file": ""}

    area_col = find_col(raw, ["designatedArea", "countyName", "placeName", "location_name"])
    if area_col:
        mask = raw[area_col].astype(str).str.contains("Los Angeles", case=False, na=False)
        if mask.any():
            raw = raw[mask].copy()

    id_col = find_col(raw, ["event_id", "disasterNumber", "disaster_number", "id"])
    date_col = find_col(raw, ["event_date", "incidentBeginDate", "declarationDate", "date"])
    type_col = find_col(raw, ["hazard_type", "incidentType", "incident_type", "type"])
    title_col = find_col(raw, ["declaration_title", "declarationTitle", "title"])

    out = pd.DataFrame()
    out["event_id"] = raw[id_col].astype(str) if id_col else [f"FEMA_{i:05d}" for i in range(len(raw))]
    out["event_date"] = safe_date(raw[date_col]) if date_col else ""
    out["hazard_type"] = raw[type_col].astype(str) if type_col else "FEMA_declaration"
    out["source_agency"] = "FEMA"
    out["source_status"] = "real_downloaded"
    out["latitude"] = np.nan
    out["longitude"] = np.nan
    out["severity_metric"] = "declaration"
    out["severity_value"] = raw[title_col].astype(str) if title_col else ""
    out["location_name"] = raw[area_col].astype(str) if area_col else "Los Angeles County"

    save_csv(out, "fema_disaster_clean.csv")
    return out, {
        "data_type": "fema",
        "records": len(out),
        "source": "real_downloaded",
        "file": path.name if path else "",
    }


def clean_earthquake() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    path = first_existing(
        "earthquake_usgs_la_region_clean.csv",
        "usgs_earthquake_query_la_region.csv",
        "query.csv",
    )
    raw = read_csv_if_exists(path)

    if raw.empty:
        out = pd.DataFrame(columns=[
            "event_id", "event_date", "hazard_type", "source_agency", "source_status",
            "latitude", "longitude", "severity_metric", "severity_value", "location_name"
        ])
        save_csv(out, "earthquake_clean.csv")
        return out, {"data_type": "earthquake", "records": 0, "source": "MISSING", "file": ""}

    id_col = find_col(raw, ["event_id", "id"])
    time_col = find_col(raw, ["event_time", "time", "date"])
    lat_col = find_col(raw, ["latitude", "lat"])
    lon_col = find_col(raw, ["longitude", "lon", "lng"])
    mag_col = find_col(raw, ["magnitude", "mag"])
    place_col = find_col(raw, ["location_name", "place", "location"])

    out = pd.DataFrame()
    out["event_id"] = raw[id_col].astype(str) if id_col else [f"EQ_{i:06d}" for i in range(len(raw))]
    out["event_date"] = safe_date(raw[time_col]) if time_col else ""
    out["hazard_type"] = "earthquake"
    out["source_agency"] = "USGS"
    out["source_status"] = "real_downloaded"
    out["latitude"] = to_numeric(raw[lat_col]) if lat_col else np.nan
    out["longitude"] = to_numeric(raw[lon_col]) if lon_col else np.nan
    out["severity_metric"] = "magnitude"
    out["severity_value"] = to_numeric(raw[mag_col]) if mag_col else np.nan
    out["location_name"] = raw[place_col].astype(str) if place_col else "Los Angeles region"

    save_csv(out, "earthquake_clean.csv")
    return out, {
        "data_type": "earthquake",
        "records": len(out),
        "source": "real_downloaded",
        "file": path.name if path else "",
    }


def clean_svi() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    path = first_existing("population_svi_la_county.geojson", "population_svi_la_county_fallback.geojson")
    data = read_geojson_if_exists(path)
    rows = []

    for i, feat in enumerate(data.get("features", [])):
        props = feat.get("properties", {}) or {}
        lon, lat = extract_xy_from_geometry(feat.get("geometry"))
        rows.append({
            "svi_id": props.get("FIPS") or props.get("GEOID") or props.get("OBJECTID") or f"SVI_{i:05d}",
            "location_name": props.get("LOCATION") or props.get("NAME") or "Los Angeles County tract",
            "total_population": props.get("E_TOTPOP"),
            "svi_score": props.get("SVI_SCORE", props.get("RPL_THEMES")),
            "poverty_pct": props.get("EP_POV150"),
            "unemployment_pct": props.get("EP_UNEMP"),
            "age65_pct": props.get("EP_AGE65"),
            "disability_pct": props.get("EP_DISABL"),
            "latitude": lat,
            "longitude": lon,
            "source_agency": "LA County / CDC SVI style",
            "source_status": props.get("source_status", "real_or_fallback_geojson"),
        })

    out = pd.DataFrame(rows)
    save_csv(out, "population_svi_clean.csv")

    source_status = "MISSING"
    if len(out) > 0:
        status_text = " ".join(out.get("source_status", pd.Series(dtype=str)).astype(str).head(20).tolist()).lower()
        source_status = "SIMULATED_FALLBACK" if ("fallback" in status_text or "simulated" in status_text) else "real_downloaded"

    return out, {
        "data_type": "svi",
        "records": len(out),
        "source": source_status,
        "file": path.name if path else "",
    }


def normalize_resource_features(data: Dict[str, Any], default_type: str) -> List[Dict[str, Any]]:
    rows = []
    for i, feat in enumerate(data.get("features", [])):
        props = feat.get("properties", {}) or {}

        lon, lat = extract_xy_from_geometry(feat.get("geometry"))
        if pd.isna(lon) or pd.isna(lat):
            lon = props.get("LONGITUDE", props.get("longitude", np.nan))
            lat = props.get("LATITUDE", props.get("latitude", np.nan))

        rows.append({
            "resource_id": props.get("OBJECTID") or props.get("ID") or props.get("resource_id") or f"{default_type}_{i:05d}",
            "resource_name": props.get("NAME") or props.get("FACILITY_NAME") or props.get("name") or f"{default_type} facility",
            "resource_type": props.get("resource_type") or default_type,
            "address": props.get("ADDRESS") or props.get("address") or "",
            "city": props.get("CITY") or props.get("city") or "",
            "latitude": pd.to_numeric(pd.Series([lat]), errors="coerce").iloc[0],
            "longitude": pd.to_numeric(pd.Series([lon]), errors="coerce").iloc[0],
            "source_agency": "LA County / HIFLD style",
            "source_status": props.get("source_status", "real_or_fallback_geojson"),
        })
    return rows


def clean_resources() -> Tuple[pd.DataFrame, Dict[str, Any], Dict[str, Any]]:
    fire_path = first_existing("emergency_fire_ems_stations_la.geojson")
    hospital_path = first_existing("emergency_hospitals_la.geojson")
    unified_path = first_existing("unified_resource_points.geojson", "unified_resource_points_fallback.geojson")

    rows: List[Dict[str, Any]] = []
    used_files = []

    fire = read_geojson_if_exists(fire_path)
    hospital = read_geojson_if_exists(hospital_path)

    if geojson_feature_count(fire) > 0:
        rows.extend(normalize_resource_features(fire, "fire_ems_station"))
        used_files.append(fire_path.name if fire_path else "")
    if geojson_feature_count(hospital) > 0:
        rows.extend(normalize_resource_features(hospital, "hospital"))
        used_files.append(hospital_path.name if hospital_path else "")

    if not rows:
        unified = read_geojson_if_exists(unified_path)
        if geojson_feature_count(unified) > 0:
            rows.extend(normalize_resource_features(unified, "emergency_resource"))
            used_files.append(unified_path.name if unified_path else "")

    out = pd.DataFrame(rows)
    save_csv(out, "emergency_resources_clean.csv")

    features = []
    for _, r in out.iterrows():
        props = r.drop(labels=["latitude", "longitude"]).to_dict()
        lon = None if pd.isna(r.get("longitude")) else float(r.get("longitude"))
        lat = None if pd.isna(r.get("latitude")) else float(r.get("latitude"))
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": props,
        })

    geojson_out = {"type": "FeatureCollection", "features": features}
    save_geojson(geojson_out, "unified_resource_points.geojson")

    if out.empty:
        source_status = "MISSING"
    else:
        status_text = " ".join(out.get("source_status", pd.Series(dtype=str)).astype(str).head(30).tolist()).lower()
        source_status = "MIXED_OR_FALLBACK" if ("fallback" in status_text or "simulated" in status_text) else "real_downloaded"

    return out, geojson_out, {
        "data_type": "resources",
        "records": len(out),
        "source": source_status,
        "file": ";".join(used_files),
    }


def clean_landslide() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    path = first_existing("landslide_cgs_la_county.geojson", "landslide_cgs_la_county_fallback.geojson")
    data = read_geojson_if_exists(path)
    rows = []

    for i, feat in enumerate(data.get("features", [])):
        props = feat.get("properties", {}) or {}
        lon, lat = extract_xy_from_geometry(feat.get("geometry"))

        rows.append({
            "landslide_id": props.get("LS_ID") or props.get("landslide_id") or props.get("OBJECTID") or f"LS_{i:05d}",
            "county": props.get("COUNTY") or "Los Angeles",
            "zone_name": props.get("ZONE_NAME") or props.get("location_name") or "",
            "landslide_type": props.get("LANDSLIDE_TYPE") or props.get("event_type") or "landslide",
            "confidence": props.get("CONFIDENCE") or props.get("confidence") or "",
            "activity": props.get("ACTIVITY") or "",
            "year_mapped": props.get("YEAR_MAPPED") or "",
            "area_sqkm_est": props.get("AREA_SQKM_EST") or "",
            "latitude": lat,
            "longitude": lon,
            "source_agency": "California Geological Survey style",
            "source_status": props.get("source_status", "simulated_fallback_same_schema"),
        })

    out = pd.DataFrame(rows)
    save_csv(out, "landslide_clean.csv")

    if out.empty:
        source_status = "MISSING"
    else:
        status_text = " ".join(out.get("source_status", pd.Series(dtype=str)).astype(str).head(30).tolist()).lower()
        source_status = "SIMULATED_FALLBACK" if ("fallback" in status_text or "simulated" in status_text) else "real_downloaded"

    return out, {
        "data_type": "landslide",
        "records": len(out),
        "source": source_status,
        "file": path.name if path else "",
    }


def summarize_roads() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    coverage_path = first_existing("dataset_coverage_summary.csv")
    coverage = read_csv_if_exists(coverage_path)

    roads_rows = []
    if not coverage.empty:
        text_cols = [c for c in coverage.columns if coverage[c].dtype == object]
        mask = pd.Series(False, index=coverage.index)
        for c in text_cols:
            mask |= coverage[c].astype(str).str.contains("road|tiger|shapefile", case=False, na=False)
        if mask.any():
            roads_rows = coverage[mask].to_dict("records")

    if roads_rows:
        out = pd.DataFrame(roads_rows)
        if "record_count" not in out.columns:
            out["record_count"] = np.nan
        if "source_status" not in out.columns:
            out["source_status"] = "real_downloaded"
    else:
        out = pd.DataFrame([{
            "data_type": "roads",
            "source": "U.S. Census TIGER/Line Roads",
            "record_count": np.nan,
            "source_status": "SKIPPED",
            "output_file": "roads shapefile exists outside processed CSV workflow",
        }])

    save_csv(out, "roads_summary.csv")

    source = "real_downloaded" if not out.empty and str(out.get("source_status", pd.Series([""])).iloc[0]).lower() != "skipped" else "SKIPPED"
    records = int(pd.to_numeric(out.get("record_count", pd.Series([0])), errors="coerce").fillna(0).sum())
    return out, {
        "data_type": "roads",
        "records": records,
        "source": source,
        "file": coverage_path.name if coverage_path else "",
    }


# =============================================================================
# 4. 融合表与可视化
# =============================================================================

def build_unified_hazard_events(
    earthquake: pd.DataFrame,
    fema: pd.DataFrame,
    landslide: pd.DataFrame,
) -> pd.DataFrame:
    existing = first_existing("unified_hazard_events.csv")
    existing_df = read_csv_if_exists(existing)
    if not existing_df.empty:
        out = existing_df.copy()
        save_csv(out, "unified_hazard_events.csv")
        return out

    rows: List[Dict[str, Any]] = []

    if not earthquake.empty:
        rows.extend(earthquake.to_dict("records"))

    if not fema.empty:
        rows.extend(fema.to_dict("records"))

    if not landslide.empty:
        for _, r in landslide.iterrows():
            rows.append({
                "event_id": r.get("landslide_id", ""),
                "event_date": r.get("year_mapped", ""),
                "hazard_type": "landslide",
                "source_agency": "CGS / fallback",
                "source_status": r.get("source_status", ""),
                "latitude": r.get("latitude", np.nan),
                "longitude": r.get("longitude", np.nan),
                "severity_metric": "confidence",
                "severity_value": r.get("confidence", ""),
                "location_name": r.get("zone_name", "Los Angeles County"),
            })

    out = pd.DataFrame(rows)
    save_csv(out, "unified_hazard_events.csv")
    return out


def build_unified_monitoring_daily(weather_long: pd.DataFrame) -> pd.DataFrame:
    existing = first_existing("unified_monitoring_daily.csv")
    existing_df = read_csv_if_exists(existing)
    if not existing_df.empty:
        out = existing_df.copy()
        save_csv(out, "unified_monitoring_daily.csv")
        return out

    out = weather_long.copy()
    save_csv(out, "unified_monitoring_daily.csv")
    return out


def build_data_source_status(status_rows: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(status_rows)
    save_csv(df, "data_source_status.csv")
    return df


def build_data_fusion_summary(
    status: pd.DataFrame,
    hazard: pd.DataFrame,
    monitoring: pd.DataFrame,
    resources: pd.DataFrame,
    svi: pd.DataFrame,
) -> pd.DataFrame:
    rows = [
        {"item": "data_sources_total", "value": len(status)},
        {"item": "real_or_mixed_sources", "value": int(status["source"].astype(str).str.contains("real|MIXED", case=False, na=False).sum()) if not status.empty else 0},
        {"item": "missing_sources", "value": int(status["source"].astype(str).str.contains("MISSING", case=False, na=False).sum()) if not status.empty else 0},
        {"item": "hazard_events", "value": len(hazard)},
        {"item": "monitoring_records", "value": len(monitoring)},
        {"item": "resource_points", "value": len(resources)},
        {"item": "svi_records", "value": len(svi)},
    ]
    df = pd.DataFrame(rows)
    save_csv(df, "data_fusion_summary.csv")
    return df


def plot_data_source_records(status: pd.DataFrame) -> Optional[Path]:
    if status.empty:
        return None

    plot_df = status.copy()
    plot_df["records"] = pd.to_numeric(plot_df["records"], errors="coerce").fillna(0)

    plt.figure(figsize=(9, 5))
    plt.bar(plot_df["data_type"].astype(str), plot_df["records"])
    plt.title("Records by Data Source")
    plt.xlabel("Data source")
    plt.ylabel("Records / Features")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    out = FIGURE_OUT / "data_source_records.png"
    plt.savefig(out, dpi=180)
    plt.close()
    return out


def plot_hazard_event_counts(hazard: pd.DataFrame) -> Optional[Path]:
    if hazard.empty or "hazard_type" not in hazard.columns:
        return None

    counts = hazard["hazard_type"].fillna("unknown").astype(str).value_counts().head(12)

    plt.figure(figsize=(9, 5))
    plt.bar(counts.index, counts.values)
    plt.title("Unified Hazard Events by Type")
    plt.xlabel("Hazard type")
    plt.ylabel("Event count")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    out = FIGURE_OUT / "hazard_event_counts.png"
    plt.savefig(out, dpi=180)
    plt.close()
    return out


def plot_resource_type_counts(resources: pd.DataFrame) -> Optional[Path]:
    if resources.empty or "resource_type" not in resources.columns:
        return None

    counts = resources["resource_type"].fillna("unknown").astype(str).value_counts().head(12)

    plt.figure(figsize=(8, 5))
    plt.bar(counts.index, counts.values)
    plt.title("Emergency Resource Points by Type")
    plt.xlabel("Resource type")
    plt.ylabel("Count")
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    out = FIGURE_OUT / "resource_type_counts.png"
    plt.savefig(out, dpi=180)
    plt.close()
    return out


# =============================================================================
# 5. 主程序
# =============================================================================

def main() -> None:
    print_header()

    status_rows: List[Dict[str, Any]] = []

    weather_long, s_weather = clean_weather()
    status_rows.append(s_weather)
    print(f"[weather] records={s_weather['records']} source={s_weather['source']} file={s_weather['file']}")

    fema, s_fema = clean_fema()
    status_rows.append(s_fema)
    print(f"[fema] records={s_fema['records']} source={s_fema['source']} file={s_fema['file']}")

    earthquake, s_earthquake = clean_earthquake()
    status_rows.append(s_earthquake)
    print(f"[earthquake] records={s_earthquake['records']} source={s_earthquake['source']} file={s_earthquake['file']}")

    svi, s_svi = clean_svi()
    status_rows.append(s_svi)
    print(f"[svi] records={s_svi['records']} source={s_svi['source']} file={s_svi['file']}")

    resources, resources_geojson, s_resources = clean_resources()
    status_rows.append(s_resources)
    print(f"[resources] records={s_resources['records']} source={s_resources['source']} file={s_resources['file']}")

    landslide, s_landslide = clean_landslide()
    status_rows.append(s_landslide)
    print(f"[landslide] records={s_landslide['records']} source={s_landslide['source']} file={s_landslide['file']}")

    roads, s_roads = summarize_roads()
    status_rows.append(s_roads)
    print(f"[roads] records={s_roads['records']} source={s_roads['source']} file={s_roads['file']}")

    hazard = build_unified_hazard_events(earthquake, fema, landslide)
    monitoring = build_unified_monitoring_daily(weather_long)

    status = build_data_source_status(status_rows)
    summary = build_data_fusion_summary(status, hazard, monitoring, resources, svi)

    figures = [
        plot_data_source_records(status),
        plot_hazard_event_counts(hazard),
        plot_resource_type_counts(resources),
    ]

    print("-" * 80)
    print("Finished. Main output files:")
    for p in sorted(PROCESSED_OUT.glob("*")):
        print(f" - {p}")
    print("Figures:")
    for p in figures:
        if p is not None:
            print(f" - {p}")
    print("-" * 80)

    missing = status[status["source"].astype(str).str.contains("MISSING", case=False, na=False)]
    if not missing.empty:
        print("[WARN] Some data sources are still missing:")
        print(missing.to_string(index=False))
    else:
        print("[OK] No required source is marked as MISSING.")


if __name__ == "__main__":
    main()
