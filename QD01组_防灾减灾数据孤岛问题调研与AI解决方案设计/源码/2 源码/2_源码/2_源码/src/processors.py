# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple

import pandas as pd

from .fallback import make_svi_fallback, make_resource_fallback, make_landslide_fallback
from .utils import (
    ensure_dir,
    find_first,
    find_all,
    read_csv_safely,
    save_csv,
    load_geojson,
    save_geojson,
    feature_collection,
    representative_point_from_geometry,
    status_row,
    to_date,
    to_numeric,
)


def process_weather(data_dir: Path, out_dir: Path) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    p = find_first(data_dir, [
        "weather_noaa_daily_summaries_clean.csv",
        "daily-summaries-*.csv",
        "*daily_summaries*noaa*.csv",
    ])
    if not p:
        df = pd.DataFrame(columns=[
            "station_id", "station_name", "latitude", "longitude", "elevation_m",
            "date", "wind_avg", "precipitation", "snow", "snow_depth",
            "temp_max_c", "temp_min_c", "source", "is_simulated"
        ])
        save_csv(df, out_dir / "processed" / "weather_clean.csv")
        return df, status_row("weather", "", "MISSING", 0, "未找到气象文件。")

    raw = read_csv_safely(p)
    colmap = {
        "STATION": "station_id",
        "NAME": "station_name",
        "LATITUDE": "latitude",
        "LONGITUDE": "longitude",
        "ELEVATION": "elevation_m",
        "DATE": "date",
        "AWND": "wind_avg",
        "PRCP": "precipitation",
        "SNOW": "snow",
        "SNWD": "snow_depth",
        "TMAX": "temp_max_c",
        "TMIN": "temp_min_c",
    }
    raw = raw.rename(columns={k: v for k, v in colmap.items() if k in raw.columns})

    expected = ["station_id", "station_name", "latitude", "longitude", "elevation_m", "date",
                "wind_avg", "precipitation", "snow", "snow_depth", "temp_max_c", "temp_min_c"]
    for c in expected:
        if c not in raw.columns:
            raw[c] = pd.NA

    df = raw[expected].copy()
    df["date"] = to_date(df["date"])
    for c in ["latitude", "longitude", "elevation_m", "wind_avg", "precipitation", "snow", "snow_depth", "temp_max_c", "temp_min_c"]:
        df[c] = to_numeric(df[c])
    df["source"] = "NOAA Daily Summaries"
    df["is_simulated"] = 0

    save_csv(df, out_dir / "processed" / "weather_clean.csv")
    return df, status_row("weather", str(p), "REAL", len(df), "NOAA 气象日值数据。")


def process_fema(data_dir: Path, out_dir: Path) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    p = find_first(data_dir, [
        "disaster_fema_la_county_clean.csv",
        "DisasterDeclarationsSummaries.csv",
        "*DisasterDeclarations*.csv",
    ])
    if not p:
        df = pd.DataFrame(columns=[
            "disasterNumber", "state", "declarationType", "declarationDate",
            "incidentType", "declarationTitle", "incidentBeginDate", "incidentEndDate",
            "designatedArea", "source", "is_simulated"
        ])
        save_csv(df, out_dir / "processed" / "fema_disaster_clean.csv")
        return df, status_row("disaster_fema", "", "MISSING", 0, "未找到 FEMA 文件。")

    raw = read_csv_safely(p)
    # 只保留加州洛杉矶县，如果原始表已经过滤，这一步不影响。
    if "state" in raw.columns:
        raw = raw[raw["state"].astype(str).str.upper().eq("CA")].copy()
    if "designatedArea" in raw.columns:
        mask = raw["designatedArea"].astype(str).str.contains("Los Angeles", case=False, na=False)
        if mask.any():
            raw = raw[mask].copy()

    cols = [
        "femaDeclarationString", "disasterNumber", "state", "declarationType",
        "declarationDate", "fyDeclared", "incidentType", "declarationTitle",
        "incidentBeginDate", "incidentEndDate", "designatedArea",
        "fipsStateCode", "fipsCountyCode", "placeCode", "region", "lastRefresh", "id"
    ]
    for c in cols:
        if c not in raw.columns:
            raw[c] = pd.NA
    df = raw[cols].copy()
    df["declaration_date"] = to_date(df["declarationDate"])
    df["incident_begin_date"] = to_date(df["incidentBeginDate"])
    df["incident_end_date"] = to_date(df["incidentEndDate"])
    df["source"] = "FEMA OpenFEMA Disaster Declarations Summaries"
    df["is_simulated"] = 0

    save_csv(df, out_dir / "processed" / "fema_disaster_clean.csv")
    return df, status_row("disaster_fema", str(p), "REAL", len(df), "FEMA 官方灾害声明数据。")


def process_earthquake(data_dir: Path, out_dir: Path) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    p = find_first(data_dir, [
        "earthquake_usgs_la_region_clean.csv",
        "query.csv",
        "*earthquake*.csv",
    ])
    if not p:
        df = pd.DataFrame(columns=[
            "time", "event_date", "latitude", "longitude", "depth", "mag",
            "place", "type", "hazard_type", "source", "is_simulated"
        ])
        save_csv(df, out_dir / "processed" / "earthquake_clean.csv")
        return df, status_row("earthquake", "", "MISSING", 0, "未找到 USGS 地震文件。")

    raw = read_csv_safely(p)
    for c in ["time", "latitude", "longitude", "depth", "mag", "place", "type", "id"]:
        if c not in raw.columns:
            raw[c] = pd.NA
    df = raw.copy()
    df["event_date"] = to_date(df["time"])
    for c in ["latitude", "longitude", "depth", "mag"]:
        df[c] = to_numeric(df[c])
    df["hazard_type"] = "earthquake"
    df["source"] = "USGS Earthquake Catalog"
    df["is_simulated"] = 0

    save_csv(df, out_dir / "processed" / "earthquake_clean.csv")
    return df, status_row("earthquake", str(p), "REAL", len(df), "USGS 地震目录数据。")


def process_svi(data_dir: Path, out_dir: Path) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    full = find_first(data_dir, ["population_svi_la_county.geojson"])
    parts = find_all(data_dir, ["population_svi_la_county_part*.geojson"])

    if full:
        geo = load_geojson(full)
        source_file = str(full)
        source_kind = "REAL"
        note = "读取完整 SVI GeoJSON。"
    elif parts:
        features = []
        for p in parts:
            g = load_geojson(p)
            features.extend(g.get("features", []))
        geo = feature_collection(features)
        source_file = "; ".join(str(p) for p in parts)
        source_kind = "REAL"
        note = "读取 SVI 分片 GeoJSON 并合并。"
    else:
        geo = make_svi_fallback()
        source_file = "generated_population_svi_fallback"
        source_kind = "SIMULATED_FALLBACK"
        note = "未找到 SVI 文件，生成同格式模拟兜底数据。"

    save_geojson(geo, out_dir / "geojson" / "population_svi_used.geojson")

    rows = []
    for idx, feat in enumerate(geo.get("features", [])):
        props = dict(feat.get("properties") or {})
        lon, lat = representative_point_from_geometry(feat.get("geometry"))
        row = {
            "feature_id": props.get("GEOID") or props.get("FIPS") or props.get("OBJECTID") or idx,
            "longitude": lon,
            "latitude": lat,
            "total_population": props.get("E_TOTPOP") or props.get("TOTPOP") or props.get("POPULATION"),
            "svi_score": props.get("RPL_THEMES") or props.get("SPL_THEMES") or props.get("SVI_SCORE"),
            "poverty_pct": props.get("EP_POV150") or props.get("EP_POV") or props.get("POVERTY"),
            "elderly_pct": props.get("EP_AGE65") or props.get("AGE65"),
            "source": props.get("source") or "LA County SVI",
            "is_simulated": props.get("is_simulated", 0 if source_kind == "REAL" else 1),
        }
        rows.append(row)
    df = pd.DataFrame(rows)
    save_csv(df, out_dir / "processed" / "population_svi_clean.csv")
    return df, status_row("population_svi", source_file, source_kind, len(df), note)


def process_resources(data_dir: Path, out_dir: Path) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    files = [
        ("fire_ems", find_first(data_dir, ["emergency_fire_ems_stations_la.geojson", "*fire*stations*.geojson"])),
        ("hospital", find_first(data_dir, ["emergency_hospitals_la.geojson", "*hospitals*.geojson", "*hospital*.geojson"])),
    ]

    all_features = []
    status_notes = []
    source_kinds = []

    for kind, path in files:
        if path:
            geo = load_geojson(path)
            feats = geo.get("features", [])
            for feat in feats:
                props = feat.setdefault("properties", {})
                props["resource_type"] = "fire_ems" if kind == "fire_ems" else "hospital"
                props.setdefault("source", "REAL_GEOJSON")
                props.setdefault("is_simulated", 0)
            all_features.extend(feats)
            status_notes.append(f"{kind}: REAL {len(feats)}")
            source_kinds.append("REAL")
        else:
            fallback_kind = "fire_ems" if kind == "fire_ems" else "hospital"
            n = 40 if fallback_kind == "fire_ems" else 25
            geo = make_resource_fallback(fallback_kind, n)
            feats = geo.get("features", [])
            all_features.extend(feats)
            status_notes.append(f"{kind}: SIMULATED_FALLBACK {len(feats)}")
            source_kinds.append("SIMULATED_FALLBACK")

    unified_geo = feature_collection(all_features)
    save_geojson(unified_geo, out_dir / "geojson" / "emergency_resources_used.geojson")

    rows = []
    for idx, feat in enumerate(all_features):
        props = feat.get("properties") or {}
        lon, lat = representative_point_from_geometry(feat.get("geometry"))
        name = props.get("NAME") or props.get("name") or props.get("FACILITY") or props.get("FAC_NAME") or f"resource_{idx}"
        rows.append({
            "resource_id": props.get("OBJECTID") or props.get("ID") or idx,
            "resource_name": name,
            "resource_type": props.get("resource_type") or props.get("cat2") or "emergency_resource",
            "longitude": lon,
            "latitude": lat,
            "source": props.get("source") or "REAL_GEOJSON",
            "is_simulated": props.get("is_simulated", 0),
        })
    df = pd.DataFrame(rows)
    save_csv(df, out_dir / "processed" / "emergency_resources_clean.csv")
    source_kind = "REAL" if all(k == "REAL" for k in source_kinds) else "MIXED_OR_FALLBACK"
    return df, status_row("emergency_resources", "geojson resources", source_kind, len(df), "；".join(status_notes))


def process_landslide(data_dir: Path, out_dir: Path) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    p = find_first(data_dir, ["landslide_cgs_la_county.geojson", "*landslide*.geojson"])
    if p:
        geo = load_geojson(p)
        source_file = str(p)
        # 如果读到的是以前生成的兜底文件，也继续标记为兜底，避免伪装成真实数据。
        features = geo.get("features", [])
        simulated_count = 0
        for feat in features:
            props = feat.get("properties") or {}
            if str(props.get("source", "")).upper() == "SIMULATED_FALLBACK" or str(props.get("is_simulated", "")) == "1":
                simulated_count += 1
        if features and simulated_count == len(features):
            source_kind = "SIMULATED_FALLBACK"
            note = "读取到滑坡兜底 GeoJSON，继续按模拟兜底数据处理。"
        else:
            source_kind = "REAL"
            note = "读取 CGS/滑坡 GeoJSON。"
    else:
        geo = make_landslide_fallback()
        source_file = "generated_landslide_cgs_la_county_fallback"
        source_kind = "SIMULATED_FALLBACK"
        note = "真实滑坡 ZIP 下载失败或文件缺失，生成同格式模拟兜底数据。"

    save_geojson(geo, out_dir / "geojson" / "landslide_used.geojson")

    rows = []
    for idx, feat in enumerate(geo.get("features", [])):
        props = feat.get("properties") or {}
        lon, lat = representative_point_from_geometry(feat.get("geometry"))
        rows.append({
            "landslide_id": props.get("LS_ID") or props.get("OBJECTID") or props.get("id") or idx,
            "landslide_type": props.get("TYPE") or props.get("MOVEMENT") or props.get("type") or "landslide",
            "confidence": props.get("CONFIDENCE") or props.get("confidence"),
            "longitude": lon,
            "latitude": lat,
            "hazard_type": "landslide",
            "source": props.get("source") or ("CGS Landslide Inventory" if source_kind == "REAL" else "SIMULATED_FALLBACK"),
            "is_simulated": props.get("is_simulated", 0 if source_kind == "REAL" else 1),
        })
    df = pd.DataFrame(rows)
    save_csv(df, out_dir / "processed" / "landslide_clean.csv")
    return df, status_row("landslide", source_file, source_kind, len(df), note)


def process_roads(data_dir: Path, out_dir: Path) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """读取 TIGER roads shapefile，生成统计表和少量样本 GeoJSON。"""
    shp = find_first(data_dir, ["tl_2024_06037_roads.shp"])
    zip_path = find_first(data_dir, ["tiger_roads_la_county_shapefile.zip", "tl_2024_06037_roads.zip"])

    try:
        import shapefile  # pyshp
    except Exception:
        df = pd.DataFrame([{
            "road_records": 0,
            "note": "pyshp 未安装，无法读取 shapefile。",
        }])
        save_csv(df, out_dir / "processed" / "roads_summary.csv")
        return df, status_row("roads", "", "SKIPPED", 0, "缺少 pyshp 库。")

    reader = None
    source_file = ""

    try:
        if shp:
            reader = shapefile.Reader(str(shp))
            source_file = str(shp)
        elif zip_path:
            reader = shapefile.Reader(str(zip_path))
            source_file = str(zip_path)
        else:
            df = pd.DataFrame([{"road_records": 0, "note": "未找到 roads shapefile。"}])
            save_csv(df, out_dir / "processed" / "roads_summary.csv")
            return df, status_row("roads", "", "MISSING", 0, "未找到道路 shapefile。")

        fields = [f[0] for f in reader.fields[1:]]
        total = len(reader)
        records = []
        sample_features = []
        max_sample = min(500, total)

        for i, sr in enumerate(reader.iterShapeRecords()):
            rec = dict(zip(fields, sr.record))
            records.append({
                "MTFCC": rec.get("MTFCC", ""),
                "RTTYP": rec.get("RTTYP", ""),
                "FULLNAME": rec.get("FULLNAME", ""),
            })
            if i < max_sample:
                pts = sr.shape.points
                if len(pts) >= 2:
                    coords = [[float(x), float(y)] for x, y in pts]
                    sample_features.append({
                        "type": "Feature",
                        "geometry": {"type": "LineString", "coordinates": coords},
                        "properties": {
                            "FULLNAME": rec.get("FULLNAME", ""),
                            "MTFCC": rec.get("MTFCC", ""),
                            "RTTYP": rec.get("RTTYP", ""),
                            "source": "US Census TIGER/Line Roads",
                            "is_simulated": 0,
                        },
                    })

        rec_df = pd.DataFrame(records)
        if rec_df.empty:
            summary = pd.DataFrame([{"category": "all", "code": "all", "count": total}])
        else:
            mtfcc = rec_df["MTFCC"].fillna("UNKNOWN").value_counts().reset_index()
            mtfcc.columns = ["code", "count"]
            mtfcc["category"] = "MTFCC"
            rttyp = rec_df["RTTYP"].fillna("UNKNOWN").replace("", "UNKNOWN").value_counts().reset_index()
            rttyp.columns = ["code", "count"]
            rttyp["category"] = "RTTYP"
            summary = pd.concat([mtfcc[["category", "code", "count"]], rttyp[["category", "code", "count"]]], ignore_index=True)

        save_csv(summary, out_dir / "processed" / "roads_summary.csv")
        save_geojson(feature_collection(sample_features), out_dir / "geojson" / "roads_sample.geojson")
        return summary, status_row("roads", source_file, "REAL", total, "U.S. Census TIGER/Line Roads。")
    except Exception as e:
        df = pd.DataFrame([{"road_records": 0, "note": f"读取道路数据失败：{e}"}])
        save_csv(df, out_dir / "processed" / "roads_summary.csv")
        return df, status_row("roads", source_file, "ERROR", 0, f"读取道路数据失败：{e}")
