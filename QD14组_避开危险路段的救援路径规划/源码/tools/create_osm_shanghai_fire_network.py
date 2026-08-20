from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "osm_shanghai_fire"
RAW_DIR = ROOT / "data" / "osm_shanghai_fire_raw"
HISTORICAL_DIR = ROOT / "data" / "historical_disasters"
AMAP_TRAFFIC_FILE = ROOT / "data" / "amap_shanghai_fire_base" / "traffic_status_circle.csv"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

START_GCJ = (121.426226, 31.237003)
TARGET_GCJ = (121.439175, 31.235771)
FIRE_GCJ = (121.439175, 31.235771)

ALLOWED_HIGHWAYS = {
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "unclassified",
    "residential",
    "living_street",
    "service",
    "road",
}

EXCLUDED_SERVICE = {"parking_aisle", "driveway", "private"}

STATUS_LABELS = {
    "0": "unknown",
    "1": "expedite",
    "2": "congested",
    "3": "blocked",
}


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
    event_id="FIRE2010-SH-JIAOZHOU-OSM-01",
    scenario="osm_shanghai_fire",
    disaster_type="fire",
    name="2010 Shanghai Jiaozhou Road fire response zone with OSM road network",
    event_date="2010-11-15",
    longitude=FIRE_GCJ[0],
    latitude=FIRE_GCJ[1],
    influence_radius_km=0.45,
    danger_type="fire",
    severity="very_high",
    source_title="Public records: Shanghai Jiaozhou Road 11.15 major fire",
    source_url="https://zh.wikipedia.org/wiki/%E4%B8%8A%E6%B5%B7%E2%80%9C11%C2%B715%E2%80%9D%E7%89%B9%E5%88%AB%E9%87%8D%E5%A4%A7%E7%81%AB%E7%81%BE",
    evidence=(
        "The Shanghai Jiaozhou Road 11.15 major fire occurred on 2010-11-15 "
        "at Jiaozhou Road 728 in Jing'an District, Shanghai. This OSM scenario "
        "uses the historical fire location as the emergency target and a local "
        "road-network extract as the graph for Dijkstra planning."
    ),
    mapping_note=(
        "Road segments inside the fire response buffer are marked as fire risk. "
        "AMap traffic status is optionally matched to OSM edges by road name and "
        "polyline proximity, while the primary road topology comes from OSM."
    ),
)


def out_of_china(lon: float, lat: float) -> bool:
    return lon < 72.004 or lon > 137.8347 or lat < 0.8293 or lat > 55.8271


def transform_lat(lon: float, lat: float) -> float:
    ret = -100.0 + 2.0 * lon + 3.0 * lat + 0.2 * lat * lat + 0.1 * lon * lat + 0.2 * math.sqrt(abs(lon))
    ret += (20.0 * math.sin(6.0 * lon * math.pi) + 20.0 * math.sin(2.0 * lon * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * math.pi) + 40.0 * math.sin(lat / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * math.pi) + 320 * math.sin(lat * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def transform_lon(lon: float, lat: float) -> float:
    ret = 300.0 + lon + 2.0 * lat + 0.1 * lon * lon + 0.1 * lon * lat + 0.1 * math.sqrt(abs(lon))
    ret += (20.0 * math.sin(6.0 * lon * math.pi) + 20.0 * math.sin(2.0 * lon * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lon * math.pi) + 40.0 * math.sin(lon / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lon / 12.0 * math.pi) + 300.0 * math.sin(lon / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lon: float, lat: float) -> tuple[float, float]:
    if out_of_china(lon, lat):
        return lon, lat
    a = 6378245.0
    ee = 0.00669342162296594323
    dlat = transform_lat(lon - 105.0, lat - 35.0)
    dlon = transform_lon(lon - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlon = (dlon * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    return lon + dlon, lat + dlat


def gcj02_to_wgs84(lon: float, lat: float) -> tuple[float, float]:
    if out_of_china(lon, lat):
        return lon, lat
    wlon, wlat = lon, lat
    for _ in range(8):
        glon, glat = wgs84_to_gcj02(wlon, wlat)
        wlon -= glon - lon
        wlat -= glat - lat
    return wlon, wlat


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1 = a
    lon2, lat2 = b
    radius = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def segment_distance_km(
    point_lon: float,
    point_lat: float,
    source_lon: float,
    source_lat: float,
    target_lon: float,
    target_lat: float,
) -> float:
    ref_lat = (point_lat + source_lat + target_lat) / 3.0
    px = point_lon * 111.320 * math.cos(math.radians(ref_lat))
    py = point_lat * 110.574
    sx = source_lon * 111.320 * math.cos(math.radians(ref_lat))
    sy = source_lat * 110.574
    tx = target_lon * 111.320 * math.cos(math.radians(ref_lat))
    ty = target_lat * 110.574
    dx = tx - sx
    dy = ty - sy
    if dx == 0 and dy == 0:
        return math.hypot(px - sx, py - sy)
    t = ((px - sx) * dx + (py - sy) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (sx + t * dx), py - (sy + t * dy))


def polyline_distance_km(a_points: list[tuple[float, float]], b_points: list[tuple[float, float]]) -> float:
    if len(a_points) < 2 or len(b_points) < 2:
        return float("inf")
    best = float("inf")
    for a, b in zip(a_points, a_points[1:]):
        for c, d in zip(b_points, b_points[1:]):
            best = min(
                best,
                segment_distance_km(a[0], a[1], c[0], c[1], d[0], d[1]),
                segment_distance_km(b[0], b[1], c[0], c[1], d[0], d[1]),
                segment_distance_km(c[0], c[1], a[0], a[1], b[0], b[1]),
                segment_distance_km(d[0], d[1], a[0], a[1], b[0], b[1]),
            )
    return best


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


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def bbox_from_gcj_points(points: list[tuple[float, float]], margin_km: float) -> tuple[float, float, float, float]:
    wgs_points = [gcj02_to_wgs84(lon, lat) for lon, lat in points]
    min_lon = min(lon for lon, _ in wgs_points)
    max_lon = max(lon for lon, _ in wgs_points)
    min_lat = min(lat for _, lat in wgs_points)
    max_lat = max(lat for _, lat in wgs_points)
    center_lat = (min_lat + max_lat) / 2.0
    lat_margin = margin_km / 110.574
    lon_margin = margin_km / (111.320 * math.cos(math.radians(center_lat)))
    return min_lat - lat_margin, min_lon - lon_margin, max_lat + lat_margin, max_lon + lon_margin


def fetch_overpass(bbox: tuple[float, float, float, float], cache_path: Path, use_cache: bool) -> dict[str, Any]:
    if use_cache and cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    south, west, north, east = bbox
    query = f"""
[out:json][timeout:90];
(
  way["highway"]({south:.7f},{west:.7f},{north:.7f},{east:.7f});
);
out body;
>;
out skel qt;
"""
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    request = urllib.request.Request(OVERPASS_URL, data=data, headers={"User-Agent": "rescue-route-planning-course-project"})
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def traffic_status_score(status: str) -> float:
    return {
        "0": 0.15,
        "1": 0.05,
        "2": 0.60,
        "3": 0.90,
    }.get(status, 0.15)


def match_traffic(
    edge: dict[str, Any],
    traffic_rows: list[dict[str, str]],
) -> dict[str, Any] | None:
    edge_points = parse_polyline(str(edge.get("polyline", "")))
    edge_name = str(edge.get("road_name", ""))
    if len(edge_points) < 2 or not edge_name:
        return None
    best: tuple[float, dict[str, str]] | None = None
    for row in traffic_rows:
        road_name = row.get("road_name", "")
        if not road_name or not (road_name in edge_name or edge_name in road_name):
            continue
        road_points = parse_polyline(row.get("polyline", ""))
        if len(road_points) < 2:
            continue
        distance = polyline_distance_km(edge_points, road_points)
        if distance <= 0.10 and (best is None or distance < best[0]):
            best = (distance, row)
    if best is None:
        return None
    distance, row = best
    original = float(edge["congestion"])
    mapped = max(original, traffic_status_score(row.get("status", "0")))
    edge["congestion"] = round(mapped, 3)
    if row.get("status") in {"2", "3"} and edge["danger_type"] == "normal":
        edge["danger_type"] = "congestion"
    return {
        "edge_id": edge["edge_id"],
        "from": edge["from"],
        "to": edge["to"],
        "road_name": edge_name,
        "traffic_road_name": row.get("road_name", ""),
        "traffic_status": row.get("status", ""),
        "traffic_status_label": row.get("status_label", STATUS_LABELS.get(row.get("status", ""), "")),
        "traffic_speed_kmh": row.get("speed_kmh", ""),
        "matched_distance_km": round(distance, 4),
        "original_congestion": original,
        "mapped_congestion": edge["congestion"],
        "traffic_captured_at": row.get("captured_at", ""),
    }


def nearest_nodes(
    nodes: dict[str, dict[str, Any]],
    point: tuple[float, float],
    count: int,
    max_distance_km: float,
) -> list[tuple[str, float]]:
    candidates = [
        (node_id, haversine_km(point, (float(row["x"]), float(row["y"]))))
        for node_id, row in nodes.items()
        if row.get("type") == "normal"
    ]
    candidates.sort(key=lambda item: item[1])
    return [(node_id, distance) for node_id, distance in candidates[:count] if distance <= max_distance_km]


def build_network(payload: dict[str, Any], connect_radius_km: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    osm_nodes_raw: dict[int, tuple[float, float]] = {}
    ways: list[dict[str, Any]] = []
    for element in payload.get("elements", []):
        if element.get("type") == "node":
            osm_nodes_raw[int(element["id"])] = (float(element["lon"]), float(element["lat"]))
        elif element.get("type") == "way":
            tags = element.get("tags") or {}
            highway = tags.get("highway")
            if highway not in ALLOWED_HIGHWAYS:
                continue
            if tags.get("access") in {"private", "no"}:
                continue
            if highway == "service" and tags.get("service") in EXCLUDED_SERVICE:
                continue
            if tags.get("area") == "yes":
                continue
            ways.append(element)

    used_node_ids = {node_id for way in ways for node_id in way.get("nodes", [])}
    nodes_by_osm: dict[int, str] = {}
    nodes: dict[str, dict[str, Any]] = {}
    for osm_id in sorted(used_node_ids):
        if osm_id not in osm_nodes_raw:
            continue
        lon_wgs, lat_wgs = osm_nodes_raw[osm_id]
        lon_gcj, lat_gcj = wgs84_to_gcj02(lon_wgs, lat_wgs)
        node_id = f"O{osm_id}"
        nodes_by_osm[osm_id] = node_id
        nodes[node_id] = {
            "node_id": node_id,
            "x": round(lon_gcj, 7),
            "y": round(lat_gcj, 7),
            "label": "",
            "type": "normal",
        }

    edges: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for way in ways:
        tags = way.get("tags") or {}
        road_name = tags.get("name") or tags.get("ref") or tags.get("highway", "unnamed road")
        highway = tags.get("highway", "")
        way_nodes = [node_id for node_id in way.get("nodes", []) if node_id in nodes_by_osm]
        for source_osm, target_osm in zip(way_nodes, way_nodes[1:]):
            source = nodes_by_osm[source_osm]
            target = nodes_by_osm[target_osm]
            if source == target:
                continue
            key = tuple(sorted((source, target)) + [road_name])
            if key in seen:
                continue
            seen.add(key)
            source_point = (float(nodes[source]["x"]), float(nodes[source]["y"]))
            target_point = (float(nodes[target]["x"]), float(nodes[target]["y"]))
            distance = haversine_km(source_point, target_point)
            if distance <= 0:
                continue
            fire_distance = segment_distance_km(EVENT.longitude, EVENT.latitude, source_point[0], source_point[1], target_point[0], target_point[1])
            danger_type = "fire" if fire_distance <= EVENT.influence_radius_km else "normal"
            edge_id = f"OSM{len(edges) + 1:05d}"
            edges.append(
                {
                    "edge_id": edge_id,
                    "from": source,
                    "to": target,
                    "distance": round(distance, 4),
                    "danger_type": danger_type,
                    "congestion": 0.08 if highway in {"primary", "secondary", "tertiary"} else 0.05,
                    "passable": "true",
                    "road_name": road_name,
                    "instruction": f"OSM {highway} way {way['id']}",
                    "polyline": f"{source_point[0]:.7f},{source_point[1]:.7f};{target_point[0]:.7f},{target_point[1]:.7f}",
                    "strategy": "osm",
                    "variant": f"osm_{highway}",
                    "path_index": way["id"],
                    "step_index": len(edges),
                }
            )
            if danger_type == "fire":
                mapping_rows.append(
                    {
                        "edge_id": edge_id,
                        "from": source,
                        "to": target,
                        "road_name": road_name,
                        "scenario": EVENT.scenario,
                        "event_id": EVENT.event_id,
                        "event_name": EVENT.name,
                        "danger_type": "fire",
                        "distance_to_event_km": round(fire_distance, 4),
                        "influence_radius_km": EVENT.influence_radius_km,
                        "mapping_method": "OSM road segment intersects historical urban-fire response buffer",
                        "source_url": EVENT.source_url,
                    }
                )

    nodes["START"] = {
        "node_id": "START",
        "x": START_GCJ[0],
        "y": START_GCJ[1],
        "label": "Putuo Wuning Fire Rescue Station",
        "type": "start",
    }
    nodes["TARGET"] = {
        "node_id": "TARGET",
        "x": TARGET_GCJ[0],
        "y": TARGET_GCJ[1],
        "label": "Shanghai Jiaozhou Road 728 fire site",
        "type": "target",
    }
    connector_rows: list[dict[str, Any]] = []
    for connector_name, virtual_id, point, max_distance in [
        ("start connector", "START", START_GCJ, connect_radius_km),
        ("fire site connector", "TARGET", TARGET_GCJ, connect_radius_km),
    ]:
        for node_id, distance in nearest_nodes(nodes, point, count=5, max_distance_km=max_distance):
            source_point = (float(nodes[virtual_id]["x"]), float(nodes[virtual_id]["y"]))
            target_point = (float(nodes[node_id]["x"]), float(nodes[node_id]["y"]))
            danger_type = "fire" if virtual_id == "TARGET" else "normal"
            edge_id = f"OSM{len(edges) + 1:05d}"
            edge = {
                "edge_id": edge_id,
                "from": virtual_id,
                "to": node_id,
                "distance": round(distance, 4),
                "danger_type": danger_type,
                "congestion": 0.05,
                "passable": "true",
                "road_name": connector_name,
                "instruction": connector_name,
                "polyline": f"{source_point[0]:.7f},{source_point[1]:.7f};{target_point[0]:.7f},{target_point[1]:.7f}",
                "strategy": "connector",
                "variant": "connector",
                "path_index": 0,
                "step_index": len(edges),
            }
            edges.append(edge)
            connector_rows.append(edge)

    ordered_nodes = list(nodes.values())
    return ordered_nodes, edges, mapping_rows, connector_rows


def apply_traffic(edges: list[dict[str, Any]], traffic_file: Path) -> list[dict[str, Any]]:
    traffic_rows = read_csv(traffic_file)
    mappings: list[dict[str, Any]] = []
    if not traffic_rows:
        return mappings
    for edge in edges:
        mapping = match_traffic(edge, traffic_rows)
        if mapping:
            mappings.append(mapping)
    return mappings


def write_dataset(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], mapping_rows: list[dict[str, Any]], traffic_mapping_rows: list[dict[str, Any]], payload: dict[str, Any], bbox: tuple[float, float, float, float]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(OUT_DIR / "nodes.csv", nodes, ["node_id", "x", "y", "label", "type"])
    write_csv(
        OUT_DIR / "edges.csv",
        edges,
        [
            "edge_id",
            "from",
            "to",
            "distance",
            "danger_type",
            "congestion",
            "passable",
            "road_name",
            "instruction",
            "polyline",
            "strategy",
            "variant",
            "path_index",
            "step_index",
        ],
    )
    scenario = {
        "scenario_name": "Shanghai Jiaozhou Road fire rescue planning with OSM regional road network",
        "start_node": "START",
        "target_node": "TARGET",
        "start_label": "\u8d77\u70b9\uff1a\u6b66\u5b81\u6d88\u9632\u7ad9",
        "target_label": "\u7ec8\u70b9\uff1a\u80f6\u5dde\u8def728\u53f7",
        "risk_factors": {
            "normal": 1.0,
            "congestion": 2.0,
            "fire": 9.0,
            "flood": 2.2,
            "collapse": 4.0,
        },
        "congestion_weight": 1.25,
        "danger_fixed_costs": {"fire": 1.5, "congestion": 8.0},
        "undirected": True,
        "disaster_type": "fire",
        "historical_event_id": EVENT.event_id,
        "historical_event_name": EVENT.name,
        "historical_event_date": EVENT.event_date,
        "historical_event_source": EVENT.source_url,
        "road_data_source": "OpenStreetMap / Overpass API regional highway extract",
        "traffic_data_source": "AMap traffic status circle API, matched by road name and polyline proximity when available",
        "description": (
            "The main routing graph uses a continuous regional OSM road network around "
            "the Shanghai Jiaozhou Road fire site. Historical fire risk and AMap traffic "
            "status are overlaid onto the road segments before Dijkstra planning."
        ),
    }
    (OUT_DIR / "scenario.json").write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(OUT_DIR / "disaster_events.csv", [asdict(EVENT)], list(asdict(EVENT).keys()))
    write_csv(
        OUT_DIR / "road_disaster_mapping.csv",
        mapping_rows,
        [
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
        ],
    )
    write_csv(
        OUT_DIR / "road_traffic_mapping.csv",
        traffic_mapping_rows,
        [
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
        ],
    )
    write_csv(HISTORICAL_DIR / "shanghai_jiaozhou_fire_osm_event.csv", [asdict(EVENT)], list(asdict(EVENT).keys()))
    metadata = {
        "bbox_wgs84": {
            "south": bbox[0],
            "west": bbox[1],
            "north": bbox[2],
            "east": bbox[3],
        },
        "overpass_elements": len(payload.get("elements", [])),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "fire_affected_edge_count": len(mapping_rows),
        "traffic_mapped_edge_count": len(traffic_mapping_rows),
        "coordinate_note": "OSM WGS84 coordinates are converted to GCJ-02 for consistency with AMap traffic and existing project visuals.",
    }
    (OUT_DIR / "osm_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create Shanghai fire scenario from an OSM regional road-network extract.")
    parser.add_argument("--margin-km", type=float, default=2.2)
    parser.add_argument("--connect-radius-km", type=float, default=0.35)
    parser.add_argument("--no-cache", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bbox = bbox_from_gcj_points([START_GCJ, TARGET_GCJ, (121.459621, 31.237824), (121.432151, 31.224689)], args.margin_km)
    cache_path = RAW_DIR / "overpass_shanghai_fire.json"
    payload = fetch_overpass(bbox, cache_path, use_cache=not args.no_cache)
    nodes, edges, mapping_rows, _connector_rows = build_network(payload, connect_radius_km=args.connect_radius_km)
    if not edges:
        print("No OSM road edges were generated. Check Overpass response or bbox.", file=sys.stderr)
        sys.exit(1)
    traffic_mapping_rows = apply_traffic(edges, AMAP_TRAFFIC_FILE)
    write_dataset(nodes, edges, mapping_rows, traffic_mapping_rows, payload, bbox)
    print(
        f"Created {OUT_DIR} from OSM: {len(nodes)} nodes, {len(edges)} edges, "
        f"{len(mapping_rows)} fire-affected edges, {len(traffic_mapping_rows)} traffic-mapped edges."
    )


if __name__ == "__main__":
    main()
