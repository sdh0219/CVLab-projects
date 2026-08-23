# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Iterable, List, Optional, Dict, Any, Tuple

import pandas as pd


LA_BBOX = (-118.95, 32.75, -117.65, 34.83)  # west, south, east, north


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _is_generated_output_path(path: Path) -> bool:
    """避免把上次运行生成的 outputs/outputs_test 当成新的真实输入。"""
    lower_parts = {part.lower() for part in path.parts}
    return "outputs" in lower_parts or "outputs_test" in lower_parts


def find_first(data_dir: Path, candidate_names: Iterable[str]) -> Optional[Path]:
    """递归查找第一个匹配文件。支持精确文件名和通配符，并跳过 outputs 目录。"""
    names = list(candidate_names)
    for name in names:
        matches = [p for p in sorted(data_dir.rglob(name)) if not _is_generated_output_path(p)]
        if matches:
            return matches[0]
    return None


def find_all(data_dir: Path, candidate_names: Iterable[str]) -> List[Path]:
    result = []
    for name in candidate_names:
        result.extend([p for p in sorted(data_dir.rglob(name)) if not _is_generated_output_path(p)])
    # 去重并保持顺序
    seen = set()
    unique = []
    for p in result:
        if p.resolve() not in seen:
            seen.add(p.resolve())
            unique.append(p)
    return unique


def read_csv_safely(path: Path) -> pd.DataFrame:
    encodings = ["utf-8-sig", "utf-8", "gbk", "latin1"]
    last_error = None
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception as e:
            last_error = e
    raise RuntimeError(f"无法读取 CSV: {path}, error={last_error}")


def to_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.date.astype("string")


def to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def save_csv(df: pd.DataFrame, path: Path) -> None:
    ensure_dir(path.parent)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def load_geojson(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_geojson(data: Dict[str, Any], path: Path) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def feature_collection(features: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}


def point_feature(lon: float, lat: float, props: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": props,
    }


def polygon_feature(coords: List[List[float]], props: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [coords]},
        "properties": props,
    }


def representative_point_from_geometry(geometry: Dict[str, Any]) -> Tuple[float, float]:
    """从 Point/Polygon/MultiPolygon 中粗略提取代表点，不依赖 GIS 库。"""
    if not geometry:
        return (None, None)
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")

    if gtype == "Point" and coords:
        return (coords[0], coords[1])

    pts = []

    def collect(x):
        if isinstance(x, list):
            if len(x) >= 2 and all(isinstance(v, (int, float)) for v in x[:2]):
                pts.append((x[0], x[1]))
            else:
                for item in x:
                    collect(item)

    collect(coords)
    if not pts:
        return (None, None)
    lon = sum(p[0] for p in pts) / len(pts)
    lat = sum(p[1] for p in pts) / len(pts)
    return (lon, lat)


def random_point_in_la(seed: int = None) -> Tuple[float, float]:
    rng = random.Random(seed)
    west, south, east, north = LA_BBOX
    return (rng.uniform(west, east), rng.uniform(south, north))


def status_row(data_type: str, source_file: str, source_kind: str, records: int, note: str) -> Dict[str, Any]:
    return {
        "data_type": data_type,
        "source_file": source_file,
        "source_kind": source_kind,
        "records": records,
        "note": note,
    }
