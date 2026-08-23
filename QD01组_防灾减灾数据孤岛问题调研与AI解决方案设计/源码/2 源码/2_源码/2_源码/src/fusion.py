# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

from .utils import save_csv


def build_unified_tables(
    weather: pd.DataFrame,
    fema: pd.DataFrame,
    earthquake: pd.DataFrame,
    svi: pd.DataFrame,
    resources: pd.DataFrame,
    landslide: pd.DataFrame,
    roads_summary: pd.DataFrame,
    out_dir: Path,
):
    # 1. 监测数据统一表：气象长表
    monitor_rows = []
    if not weather.empty:
        id_cols = ["date", "station_id", "station_name", "latitude", "longitude", "source", "is_simulated"]
        for col in ["wind_avg", "precipitation", "snow", "snow_depth", "temp_max_c", "temp_min_c"]:
            if col in weather.columns:
                tmp = weather[id_cols + [col]].copy()
                tmp = tmp.rename(columns={col: "value"})
                tmp["indicator"] = col
                tmp["source_agency"] = "NOAA"
                monitor_rows.append(tmp)
    if monitor_rows:
        unified_monitoring = pd.concat(monitor_rows, ignore_index=True)
    else:
        unified_monitoring = pd.DataFrame(columns=[
            "date", "station_id", "station_name", "latitude", "longitude",
            "source", "is_simulated", "value", "indicator", "source_agency"
        ])
    save_csv(unified_monitoring, out_dir / "processed" / "unified_monitoring_daily.csv")

    # 2. 灾害事件统一表：FEMA + 地震 + 滑坡
    hazard_rows = []

    if not earthquake.empty:
        for _, r in earthquake.iterrows():
            hazard_rows.append({
                "event_id": r.get("id", ""),
                "event_date": r.get("event_date", ""),
                "hazard_type": "earthquake",
                "source_agency": "USGS",
                "latitude": r.get("latitude", ""),
                "longitude": r.get("longitude", ""),
                "severity_metric": "magnitude",
                "severity_value": r.get("mag", ""),
                "location_name": r.get("place", ""),
                "source": r.get("source", "USGS Earthquake Catalog"),
                "is_simulated": r.get("is_simulated", 0),
            })

    if not fema.empty:
        for _, r in fema.iterrows():
            hazard_rows.append({
                "event_id": r.get("disasterNumber", ""),
                "event_date": r.get("incident_begin_date", "") or r.get("declaration_date", ""),
                "hazard_type": r.get("incidentType", "FEMA_declaration"),
                "source_agency": "FEMA",
                "latitude": "",
                "longitude": "",
                "severity_metric": "declarationType",
                "severity_value": r.get("declarationType", ""),
                "location_name": r.get("designatedArea", "Los Angeles County"),
                "source": r.get("source", "FEMA OpenFEMA"),
                "is_simulated": r.get("is_simulated", 0),
            })

    if not landslide.empty:
        for _, r in landslide.iterrows():
            hazard_rows.append({
                "event_id": r.get("landslide_id", ""),
                "event_date": "",
                "hazard_type": "landslide",
                "source_agency": "CGS_or_fallback",
                "latitude": r.get("latitude", ""),
                "longitude": r.get("longitude", ""),
                "severity_metric": "confidence",
                "severity_value": r.get("confidence", ""),
                "location_name": r.get("landslide_type", "landslide"),
                "source": r.get("source", ""),
                "is_simulated": r.get("is_simulated", 0),
            })

    unified_hazard = pd.DataFrame(hazard_rows)
    save_csv(unified_hazard, out_dir / "processed" / "unified_hazard_events.csv")

    # 3. 应急资源统一表
    unified_resources = resources.copy()
    save_csv(unified_resources, out_dir / "processed" / "unified_resource_points.csv")

    # 4. 融合摘要
    summary_rows = [
        {"dataset": "weather_clean", "records": len(weather), "purpose": "气象监测"},
        {"dataset": "fema_disaster_clean", "records": len(fema), "purpose": "官方灾害声明"},
        {"dataset": "earthquake_clean", "records": len(earthquake), "purpose": "地震事件"},
        {"dataset": "population_svi_clean", "records": len(svi), "purpose": "人口脆弱性"},
        {"dataset": "emergency_resources_clean", "records": len(resources), "purpose": "应急资源"},
        {"dataset": "landslide_clean", "records": len(landslide), "purpose": "滑坡风险"},
        {"dataset": "roads_summary", "records": int(roads_summary["count"].sum()) if "count" in roads_summary.columns else len(roads_summary), "purpose": "交通道路"},
        {"dataset": "unified_monitoring_daily", "records": len(unified_monitoring), "purpose": "统一监测数据"},
        {"dataset": "unified_hazard_events", "records": len(unified_hazard), "purpose": "统一灾害事件"},
        {"dataset": "unified_resource_points", "records": len(unified_resources), "purpose": "统一资源点"},
    ]
    fusion_summary = pd.DataFrame(summary_rows)
    save_csv(fusion_summary, out_dir / "processed" / "data_fusion_summary.csv")

    return {
        "unified_monitoring": unified_monitoring,
        "unified_hazard": unified_hazard,
        "unified_resources": unified_resources,
        "fusion_summary": fusion_summary,
    }
