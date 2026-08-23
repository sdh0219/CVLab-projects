# -*- coding: utf-8 -*-
from __future__ import annotations

import random
from typing import Dict, Any, List

from .utils import LA_BBOX, feature_collection, point_feature, polygon_feature


def make_svi_fallback(n: int = 120) -> Dict[str, Any]:
    """生成与 SVI 相似的 GeoJSON 面数据。仅用于真实文件缺失时兜底。"""
    west, south, east, north = LA_BBOX
    cols = 12
    rows = max(1, n // cols)
    dx = (east - west) / cols
    dy = (north - south) / rows
    rng = random.Random(202401)

    features: List[Dict[str, Any]] = []
    idx = 0
    for r in range(rows):
        for c in range(cols):
            if idx >= n:
                break
            x0 = west + c * dx
            y0 = south + r * dy
            x1 = x0 + dx * 0.85
            y1 = y0 + dy * 0.85
            totpop = rng.randint(800, 8000)
            props = {
                "GEOID": f"SIM06037{idx:06d}",
                "FIPS": f"06037{idx:06d}",
                "LOCATION": f"Simulated LA County tract {idx:03d}",
                "E_TOTPOP": totpop,
                "EP_POV150": round(rng.uniform(3, 35), 2),
                "EP_UNEMP": round(rng.uniform(2, 18), 2),
                "EP_AGE65": round(rng.uniform(5, 28), 2),
                "EP_DISABL": round(rng.uniform(4, 22), 2),
                "RPL_THEMES": round(rng.random(), 4),
                "SPL_THEMES": round(rng.uniform(0, 12), 3),
                "source": "SIMULATED_FALLBACK",
                "is_simulated": 1,
            }
            coords = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
            features.append(polygon_feature(coords, props))
            idx += 1
    return feature_collection(features)


def make_resource_fallback(kind: str, n: int) -> Dict[str, Any]:
    """生成医院/消防站同格式点数据。仅用于真实文件缺失时兜底。"""
    west, south, east, north = LA_BBOX
    rng = random.Random(202402 if kind == "hospital" else 202403)
    features = []
    for i in range(n):
        lon = rng.uniform(west, east)
        lat = rng.uniform(south, north)
        if kind == "hospital":
            name = f"Simulated Hospital {i+1:02d}"
            cat = "Hospitals and Medical Centers"
        else:
            name = f"Simulated Fire/EMS Station {i+1:02d}"
            cat = "Fire and EMS Stations"
        props = {
            "OBJECTID": i + 1,
            "NAME": name,
            "name": name,
            "cat2": cat,
            "resource_type": kind,
            "source": "SIMULATED_FALLBACK",
            "is_simulated": 1,
        }
        features.append(point_feature(lon, lat, props))
    return feature_collection(features)


def make_landslide_fallback(n: int = 80) -> Dict[str, Any]:
    """生成 CGS 滑坡清单相似点数据。仅用于真实文件缺失或 SSL 下载失败时兜底。"""
    west, south, east, north = LA_BBOX
    rng = random.Random(202404)
    types = ["Landslide", "Debris Flow", "Rockfall", "Earthflow"]
    confidence = ["High", "Moderate", "Low"]

    features = []
    for i in range(n):
        lon = rng.uniform(west, east)
        lat = rng.uniform(south, north)
        props = {
            "OBJECTID": i + 1,
            "LS_ID": f"SIM-LS-{i+1:05d}",
            "TYPE": rng.choice(types),
            "MOVEMENT": rng.choice(types),
            "CONFIDENCE": rng.choice(confidence),
            "SOURCE": "CGS format simulated fallback",
            "source": "SIMULATED_FALLBACK",
            "is_simulated": 1,
        }
        features.append(point_feature(lon, lat, props))
    return feature_collection(features)
