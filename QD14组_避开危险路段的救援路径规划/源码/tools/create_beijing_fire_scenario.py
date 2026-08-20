from __future__ import annotations

import csv
import json
import math
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = ROOT / "data" / "amap_fire_base"
OUT_DIR = ROOT / "data" / "amap_fire"
HISTORICAL_DIR = ROOT / "data" / "historical_disasters"
TRAFFIC_STATUS_FILE = BASE_DIR / "traffic_status_circle.csv"


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
    event_id="FIRE2023-BJ-CHANGFENG-01",
    scenario="beijing_fire",
    disaster_type="fire",
    name="2023 Beijing Changfeng Hospital urban fire response zone",
    event_date="2023-04-18",
    longitude=116.280437,
    latitude=39.889128,
    influence_radius_km=0.8,
    danger_type="fire",
    severity="high",
    source_title="Public records: 2023 Beijing Changfeng Hospital fire",
    source_url="https://zh.wikipedia.org/wiki/%E5%8C%97%E4%BA%AC%E9%95%BF%E5%B3%B0%E5%8C%BB%E9%99%A2%E7%81%AB%E7%81%BE",
    evidence=(
        "The Beijing Changfeng Hospital fire occurred on 2023-04-18 at Changfeng "
        "Hospital in Fengtai District, Beijing. This scenario uses the hospital "
        "location as the fire response target and models nearby road-control and "
        "emergency-operation influence as a local buffer."
    ),
    mapping_note=(
        "Road polyline segments intersecting the fire response buffer are marked "
        "as fire risk. The destination remains reachable because a fire rescue "
        "vehicle must approach the incident site rather than avoid it completely."
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


def polyline_distance_km(a_points: list[tuple[float, float]], b_points: list[tuple[float, float]]) -> float:
    if len(a_points) < 2 or len(b_points) < 2:
        return float("inf")
    distances: list[float] = []
    for a, b in zip(a_points, a_points[1:]):
        for c, d in zip(b_points, b_points[1:]):
            distances.append(segment_to_segment_distance_km(a, b, c, d))
    return min(distances) if distances else float("inf")


def segment_to_segment_distance_km(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> float:
    return min(
        segment_distance_km(a[0], a[1], c[0], c[1], d[0], d[1]),
        segment_distance_km(b[0], b[1], c[0], c[1], d[0], d[1]),
        segment_distance_km(c[0], c[1], a[0], a[1], b[0], b[1]),
        segment_distance_km(d[0], d[1], a[0], a[1], b[0], b[1]),
    )


def traffic_status_score(status: str) -> float:
    return {
        "0": 0.15,
        "1": 0.05,
        "2": 0.55,
        "3": 0.85,
    }.get(status, 0.15)


def base_congestion_type(edge: dict[str, str]) -> str:
    congestion = float(edge.get("congestion") or 0)
    return "congestion" if congestion >= 0.35 else "normal"


def read_traffic_status() -> list[dict[str, str]]:
    if not TRAFFIC_STATUS_FILE.exists():
        return []
    rows, _ = read_csv(TRAFFIC_STATUS_FILE)
    return [row for row in rows if row.get("polyline")]


def apply_traffic_status(edge: dict[str, str], traffic_rows: list[dict[str, str]]) -> dict[str, object] | None:
    edge_points = parse_polyline(edge.get("polyline", ""))
    if len(edge_points) < 2:
        return None
    edge_name = edge.get("road_name", "")
    best: tuple[float, dict[str, str]] | None = None
    for row in traffic_rows:
        road_name = row.get("road_name", "")
        road_points = parse_polyline(row.get("polyline", ""))
        if len(road_points) < 2:
            continue
        distance = polyline_distance_km(edge_points, road_points)
        name_matches = road_name and edge_name and (road_name in edge_name or edge_name in road_name)
        if not name_matches and distance > 0.04:
            continue
        if name_matches and distance > 0.18:
            continue
        if best is None or distance < best[0]:
            best = (distance, row)
    if best is None:
        return None
    distance, row = best
    score = traffic_status_score(row.get("status", "0"))
    original = float(edge.get("congestion") or 0)
    if score > original:
        edge["congestion"] = str(round(score, 3))
    return {
        "edge_id": edge["edge_id"],
        "from": edge["from"],
        "to": edge["to"],
        "road_name": edge_name,
        "traffic_road_name": row.get("road_name", ""),
        "traffic_status": row.get("status", ""),
        "traffic_status_label": row.get("status_label", ""),
        "traffic_speed_kmh": row.get("speed_kmh", ""),
        "matched_distance_km": round(distance, 4),
        "original_congestion": original,
        "mapped_congestion": edge["congestion"],
        "traffic_captured_at": row.get("captured_at", ""),
    }


def map_edges() -> tuple[list[dict[str, str]], list[dict[str, object]], list[dict[str, object]]]:
    nodes_rows, _ = read_csv(BASE_DIR / "nodes.csv")
    edges_rows, _ = read_csv(BASE_DIR / "edges.csv")
    nodes = {row["node_id"]: (float(row["x"]), float(row["y"])) for row in nodes_rows}
    traffic_rows = read_traffic_status()
    mapped_edges: list[dict[str, str]] = []
    mapping_rows: list[dict[str, object]] = []
    traffic_mapping_rows: list[dict[str, object]] = []

    for edge in edges_rows:
        item = dict(edge)
        traffic_mapping = apply_traffic_status(item, traffic_rows)
        if traffic_mapping:
            traffic_mapping_rows.append(traffic_mapping)
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
                    "mapping_method": "road polyline intersects historical urban-fire response buffer",
                    "source_url": EVENT.source_url,
                }
            )
    return mapped_edges, mapping_rows, traffic_mapping_rows


def write_dataset() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BASE_DIR / "nodes.csv", OUT_DIR / "nodes.csv")
    with (BASE_DIR / "scenario.json").open("r", encoding="utf-8") as f:
        scenario = json.load(f)
    scenario.update(
        {
            "scenario_name": "Beijing Changfeng Hospital urban fire rescue route planning with AMap data",
            "start_label": "起点：卢沟桥消防救援站",
            "target_label": "终点：长峰医院火灾点",
            "disaster_type": "fire",
            "historical_event_id": EVENT.event_id,
            "historical_event_name": EVENT.name,
            "historical_event_date": EVENT.event_date,
            "historical_event_source": EVENT.source_url,
            "description": (
                "Road geometry and traffic status come from AMap Web Service. Fire "
                "risk is generated by overlaying a Changfeng Hospital urban-fire "
                "response buffer with road polylines. Congestion is weighted more "
                "strongly than in earthquake and flood examples."
            ),
            "risk_design_note": (
                "For urban fire response, the destination is inside the incident "
                "area, so fire-affected road segments are penalized but remain "
                "passable to allow fire engines to reach the scene."
            ),
        }
    )
    risk_factors = dict(scenario.get("risk_factors", {}))
    risk_factors.update({"fire": 5.0, "congestion": 1.8})
    scenario["risk_factors"] = risk_factors
    scenario["congestion_weight"] = 1.2
    with (OUT_DIR / "scenario.json").open("w", encoding="utf-8") as f:
        json.dump(scenario, f, ensure_ascii=False, indent=2)

    mapped_edges, mapping_rows, traffic_mapping_rows = map_edges()
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
    traffic_fields = [
        "edge_id",
        "from",
        "to",
        "road_name",
        "traffic_road_name",
        "traffic_status",
        "traffic_status_label",
        "traffic_speed_kmh",
        "matched_distance_km",
        "original_congestion",
        "mapped_congestion",
        "traffic_captured_at",
    ]
    write_csv(OUT_DIR / "road_traffic_mapping.csv", traffic_mapping_rows, traffic_fields)
    if TRAFFIC_STATUS_FILE.exists():
        shutil.copyfile(TRAFFIC_STATUS_FILE, OUT_DIR / "traffic_status_circle.csv")
    write_csv(HISTORICAL_DIR / "beijing_changfeng_fire_event.csv", [asdict(EVENT)], list(asdict(EVENT).keys()))
    print(
        f"Created {OUT_DIR} with {len(mapping_rows)} fire-affected road segments "
        f"and {len(traffic_mapping_rows)} traffic-mapped road segments."
    )


def main() -> None:
    if not (BASE_DIR / "edges.csv").exists():
        raise FileNotFoundError("Missing base AMap data. Run src/amap_fetcher.py with data/amap_request_beijing_fire.json first.")
    write_dataset()


if __name__ == "__main__":
    main()
