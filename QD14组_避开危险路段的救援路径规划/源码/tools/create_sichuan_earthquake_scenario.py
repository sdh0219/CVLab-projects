from __future__ import annotations

import csv
import json
import math
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = ROOT / "data" / "amap_sichuan_earthquake_base"
OUT_DIR = ROOT / "data" / "province_sichuan_earthquake"
HISTORICAL_DIR = ROOT / "data" / "historical_disasters"


@dataclass(frozen=True)
class DisasterEvent:
    event_id: str
    scenario: str
    disaster_type: str
    name: str
    event_date: str
    longitude: float
    latitude: float
    influence_radius_km: float
    danger_type: str
    severity: str
    source_title: str
    source_url: str
    evidence: str
    mapping_note: str


EVENT = DisasterEvent(
    event_id="EQ2008-SC-WENCHUAN-01",
    scenario="sichuan_earthquake",
    disaster_type="earthquake",
    name="2008 Wenchuan earthquake Yingxiu-Wenchuan road impact zone",
    event_date="2008-05-12",
    longitude=103.4890,
    latitude=31.0610,
    influence_radius_km=18.0,
    danger_type="collapse",
    severity="high",
    source_title="USGS / public records: 2008 Wenchuan earthquake",
    source_url="https://earthquake.usgs.gov/earthquakes/eventpage/usp000g650",
    evidence=(
        "The 2008 Wenchuan earthquake occurred in Sichuan on 2008-05-12. Public "
        "records describe severe shaking, landslides, road disruption, and heavy "
        "damage along the Longmenshan fault region. This project maps a representative "
        "Yingxiu-Wenchuan mountain-road impact buffer onto AMap road geometry."
    ),
    mapping_note=(
        "Road polyline segments intersecting the representative earthquake impact "
        "buffer are marked as collapse or interruption risk. This is a course-level "
        "spatial overlay, not an official street-level road closure record."
    ),
)


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), reader.fieldnames or []


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_polyline(value: str) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for item in value.split(";"):
        if not item:
            continue
        try:
            lon, lat = item.split(",", 1)
            points.append((float(lon), float(lat)))
        except ValueError:
            continue
    return points


def km_per_degree(lon: float, lat: float, ref_lat: float) -> tuple[float, float]:
    return lon * 111.320 * math.cos(math.radians(ref_lat)), lat * 110.574


def segment_distance_km(
    point_lon: float,
    point_lat: float,
    source_lon: float,
    source_lat: float,
    target_lon: float,
    target_lat: float,
) -> float:
    ref_lat = (point_lat + source_lat + target_lat) / 3.0
    px, py = km_per_degree(point_lon, point_lat, ref_lat)
    sx, sy = km_per_degree(source_lon, source_lat, ref_lat)
    tx, ty = km_per_degree(target_lon, target_lat, ref_lat)
    dx = tx - sx
    dy = ty - sy
    if dx == 0 and dy == 0:
        return math.hypot(px - sx, py - sy)
    t = ((px - sx) * dx + (py - sy) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (sx + t * dx), py - (sy + t * dy))


def edge_distance_to_event_km(edge: dict[str, str], nodes: dict[str, tuple[float, float]]) -> float:
    polyline = parse_polyline(edge.get("polyline", ""))
    if len(polyline) < 2:
        polyline = [nodes[edge["from"]], nodes[edge["to"]]]
    distances = [
        segment_distance_km(EVENT.longitude, EVENT.latitude, a[0], a[1], b[0], b[1])
        for a, b in zip(polyline, polyline[1:])
    ]
    return min(distances) if distances else float("inf")


def base_congestion_type(edge: dict[str, str]) -> str:
    congestion = float(edge.get("congestion") or 0)
    return "congestion" if congestion >= 0.35 else "normal"


def map_edges() -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    nodes_rows, _ = read_csv(BASE_DIR / "nodes.csv")
    edges_rows, _ = read_csv(BASE_DIR / "edges.csv")
    nodes = {row["node_id"]: (float(row["x"]), float(row["y"])) for row in nodes_rows}
    mapped_edges: list[dict[str, str]] = []
    mapping_rows: list[dict[str, object]] = []

    for edge in edges_rows:
        item = dict(edge)
        distance = edge_distance_to_event_km(item, nodes)
        affected = distance <= EVENT.influence_radius_km
        item["danger_type"] = EVENT.danger_type if affected else base_congestion_type(item)
        mapped_edges.append(item)
        if affected:
            mapping_rows.append(
                {
                    "edge_id": item["edge_id"],
                    "from": item["from"],
                    "to": item["to"],
                    "road_name": item.get("road_name", ""),
                    "scenario": EVENT.scenario,
                    "event_id": EVENT.event_id,
                    "event_name": EVENT.name,
                    "danger_type": EVENT.danger_type,
                    "distance_to_event_km": round(distance, 3),
                    "influence_radius_km": EVENT.influence_radius_km,
                    "mapping_method": "road polyline intersects historical earthquake influence buffer",
                    "source_url": EVENT.source_url,
                }
            )
    return mapped_edges, mapping_rows


def write_dataset() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BASE_DIR / "nodes.csv", OUT_DIR / "nodes.csv")
    with (BASE_DIR / "scenario.json").open("r", encoding="utf-8") as f:
        scenario = json.load(f)
    scenario.update(
        {
            "scenario_name": "Sichuan Wenchuan earthquake rescue route planning with AMap data",
            "start_label": "起点：成都市区",
            "target_label": "终点：汶川县城",
            "disaster_type": "earthquake",
            "historical_event_id": EVENT.event_id,
            "historical_event_name": EVENT.name,
            "historical_event_date": EVENT.event_date,
            "historical_event_source": EVENT.source_url,
            "description": (
                "Road geometry comes from AMap Web Service. Earthquake collapse risk "
                "is generated by overlaying a representative Wenchuan earthquake "
                "impact buffer with road polylines."
            ),
            "risk_design_note": (
                "For this mountainous earthquake scenario, collapse risk is treated "
                "as near-interruption risk rather than ordinary congestion, so the "
                "collapse factor is set higher than urban scenarios."
            ),
        }
    )
    risk_factors = dict(scenario.get("risk_factors", {}))
    risk_factors["collapse"] = 8.0
    scenario["risk_factors"] = risk_factors
    with (OUT_DIR / "scenario.json").open("w", encoding="utf-8") as f:
        json.dump(scenario, f, ensure_ascii=False, indent=2)

    mapped_edges, mapping_rows = map_edges()
    write_csv(OUT_DIR / "edges.csv", mapped_edges, list(mapped_edges[0].keys()))
    write_csv(OUT_DIR / "disaster_events.csv", [asdict(EVENT)], list(asdict(EVENT).keys()))
    mapping_fields = [
        "edge_id",
        "from",
        "to",
        "road_name",
        "scenario",
        "event_id",
        "event_name",
        "danger_type",
        "distance_to_event_km",
        "influence_radius_km",
        "mapping_method",
        "source_url",
    ]
    write_csv(OUT_DIR / "road_disaster_mapping.csv", mapping_rows, mapping_fields)
    write_csv(HISTORICAL_DIR / "sichuan_wenchuan_earthquake_event.csv", [asdict(EVENT)], list(asdict(EVENT).keys()))
    print(f"Created {OUT_DIR} with {len(mapping_rows)} earthquake-affected road segments.")


def main() -> None:
    if not (BASE_DIR / "edges.csv").exists():
        raise FileNotFoundError("Missing base AMap data. Run src/amap_fetcher.py with data/amap_request_sichuan_earthquake.json first.")
    write_dataset()


if __name__ == "__main__":
    main()
