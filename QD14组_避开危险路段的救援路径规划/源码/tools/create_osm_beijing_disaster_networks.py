from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "osm_beijing_disaster_raw"
HISTORICAL_DIR = ROOT / "data" / "historical_disasters"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

START_GCJ = (116.326936, 40.003213)
TARGET_GCJ = (116.508410, 39.944819)

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


SCENARIOS = {
    "earthquake": {
        "source_dir": ROOT / "data" / "amap_earthquake",
        "out_dir": ROOT / "data" / "osm_beijing_earthquake",
        "cache": RAW_DIR / "overpass_beijing_earthquake.json",
        "scenario_name": "Beijing earthquake rescue planning with OSM regional road network",
        "disaster_type": "earthquake",
        "risk_factors": {"normal": 1.0, "congestion": 1.4, "flood": 2.2, "collapse": 4.0},
        "congestion_weight": 0.6,
        "description": (
            "The routing graph uses a continuous OSM regional road network between "
            "Tsinghua University and Beijing Chaoyang Railway Station. Historical "
            "earthquake impact is mapped to road segments by buffer overlay before "
            "Dijkstra route planning."
        ),
    },
    "flood": {
        "source_dir": ROOT / "data" / "amap_flood",
        "out_dir": ROOT / "data" / "osm_beijing_flood",
        "cache": RAW_DIR / "overpass_beijing_flood.json",
        "scenario_name": "Beijing flood rescue planning with OSM regional road network",
        "disaster_type": "flood",
        "risk_factors": {"normal": 1.0, "congestion": 1.4, "flood": 2.2, "collapse": 4.0},
        "congestion_weight": 0.6,
        "description": (
            "The routing graph uses a continuous OSM regional road network between "
            "Tsinghua University and Beijing Chaoyang Railway Station. Historical "
            "rainstorm and waterlogging impact is mapped to road segments by buffer "
            "overlay before Dijkstra route planning."
        ),
    },
}


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
    t = max(0.0, min(1.0, ((px - sx) * dx + (py - sy) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (sx + t * dx), py - (sy + t * dy))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_event(source_dir: Path, scenario_name: str) -> DisasterEvent:
    rows = read_csv(source_dir / "disaster_events.csv")
    if not rows:
        raise ValueError(f"No disaster event found in {source_dir}")
    row = rows[0]
    return DisasterEvent(
        event_id=f"{row['event_id']}-OSM",
        scenario=f"osm_beijing_{scenario_name}",
        disaster_type=row["disaster_type"],
        name=f"{row['name']} with OSM regional road network",
        event_date=row["event_date"],
        longitude=float(row["longitude"]),
        latitude=float(row["latitude"]),
        influence_radius_km=float(row["influence_radius_km"]),
        danger_type=row["danger_type"],
        severity=row["severity"],
        source_title=row["source_title"],
        source_url=row["source_url"],
        evidence=row["evidence"],
        mapping_note=f"OSM road segments inside the {row['danger_type']} influence buffer are marked as risk roads.",
    )


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
[out:json][timeout:120];
(
  way["highway"]({south:.7f},{west:.7f},{north:.7f},{east:.7f});
);
out body;
>;
out skel qt;
"""
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    request = urllib.request.Request(OVERPASS_URL, data=data, headers={"User-Agent": "rescue-route-planning-course-project"})
    with urllib.request.urlopen(request, timeout=160) as response:
        payload = json.loads(response.read().decode("utf-8"))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def nearest_nodes(nodes: dict[str, dict[str, Any]], point: tuple[float, float], count: int, max_distance_km: float) -> list[tuple[str, float]]:
    candidates = [
        (node_id, haversine_km(point, (float(row["x"]), float(row["y"]))))
        for node_id, row in nodes.items()
        if row.get("type") == "normal"
    ]
    candidates.sort(key=lambda item: item[1])
    return [(node_id, distance) for node_id, distance in candidates[:count] if distance <= max_distance_km]


def build_network(payload: dict[str, Any], event: DisasterEvent, connect_radius_km: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
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
        lon_gcj, lat_gcj = wgs84_to_gcj02(*osm_nodes_raw[osm_id])
        node_id = f"O{osm_id}"
        nodes_by_osm[osm_id] = node_id
        nodes[node_id] = {"node_id": node_id, "x": round(lon_gcj, 7), "y": round(lat_gcj, 7), "label": "", "type": "normal"}

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
            key = tuple(sorted((source, target)) + [road_name])
            if source == target or key in seen:
                continue
            seen.add(key)
            source_point = (float(nodes[source]["x"]), float(nodes[source]["y"]))
            target_point = (float(nodes[target]["x"]), float(nodes[target]["y"]))
            distance = haversine_km(source_point, target_point)
            if distance <= 0:
                continue
            event_distance = segment_distance_km(event.longitude, event.latitude, source_point[0], source_point[1], target_point[0], target_point[1])
            danger_type = event.danger_type if event_distance <= event.influence_radius_km else "normal"
            edge_id = f"OSM{len(edges) + 1:05d}"
            edge = {
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
            edges.append(edge)
            if danger_type != "normal":
                mapping_rows.append(
                    {
                        "edge_id": edge_id,
                        "from": source,
                        "to": target,
                        "road_name": road_name,
                        "scenario": event.scenario,
                        "event_id": event.event_id,
                        "event_name": event.name,
                        "danger_type": danger_type,
                        "distance_to_event_km": round(event_distance, 4),
                        "influence_radius_km": event.influence_radius_km,
                        "mapping_method": "OSM road segment intersects historical disaster influence buffer",
                        "source_url": event.source_url,
                    }
                )

    nodes["START"] = {"node_id": "START", "x": START_GCJ[0], "y": START_GCJ[1], "label": "Tsinghua University", "type": "start"}
    nodes["TARGET"] = {"node_id": "TARGET", "x": TARGET_GCJ[0], "y": TARGET_GCJ[1], "label": "Beijing Chaoyang Railway Station", "type": "target"}
    for connector_name, virtual_id, point in [
        ("start connector", "START", START_GCJ),
        ("target connector", "TARGET", TARGET_GCJ),
    ]:
        for node_id, distance in nearest_nodes(nodes, point, count=5, max_distance_km=connect_radius_km):
            source_point = (float(nodes[virtual_id]["x"]), float(nodes[virtual_id]["y"]))
            target_point = (float(nodes[node_id]["x"]), float(nodes[node_id]["y"]))
            edge_id = f"OSM{len(edges) + 1:05d}"
            edges.append(
                {
                    "edge_id": edge_id,
                    "from": virtual_id,
                    "to": node_id,
                    "distance": round(distance, 4),
                    "danger_type": "normal",
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
            )

    return list(nodes.values()), edges, mapping_rows


def write_dataset(config: dict[str, Any], event: DisasterEvent, nodes: list[dict[str, Any]], edges: list[dict[str, Any]], mapping_rows: list[dict[str, Any]], payload: dict[str, Any], bbox: tuple[float, float, float, float]) -> None:
    out_dir: Path = config["out_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "nodes.csv", nodes, ["node_id", "x", "y", "label", "type"])
    write_csv(
        out_dir / "edges.csv",
        edges,
        ["edge_id", "from", "to", "distance", "danger_type", "congestion", "passable", "road_name", "instruction", "polyline", "strategy", "variant", "path_index", "step_index"],
    )
    scenario = {
        "scenario_name": config["scenario_name"],
        "start_node": "START",
        "target_node": "TARGET",
        "start_label": "起点：清华大学",
        "target_label": "终点：北京朝阳站",
        "risk_factors": config["risk_factors"],
        "congestion_weight": config["congestion_weight"],
        "undirected": True,
        "disaster_type": config["disaster_type"],
        "historical_event_id": event.event_id,
        "historical_event_name": event.name,
        "historical_event_date": event.event_date,
        "historical_event_source": event.source_url,
        "road_data_source": "OpenStreetMap / Overpass API regional highway extract",
        "description": config["description"],
    }
    (out_dir / "scenario.json").write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out_dir / "disaster_events.csv", [asdict(event)], list(asdict(event).keys()))
    write_csv(
        out_dir / "road_disaster_mapping.csv",
        mapping_rows,
        ["edge_id", "from", "to", "road_name", "scenario", "event_id", "event_name", "danger_type", "distance_to_event_km", "influence_radius_km", "mapping_method", "source_url"],
    )
    write_csv(HISTORICAL_DIR / f"{event.scenario}_event.csv", [asdict(event)], list(asdict(event).keys()))
    metadata = {
        "bbox_wgs84": {"south": bbox[0], "west": bbox[1], "north": bbox[2], "east": bbox[3]},
        "overpass_elements": len(payload.get("elements", [])),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "disaster_affected_edge_count": len(mapping_rows),
        "coordinate_note": "OSM WGS84 coordinates are converted to GCJ-02 for consistency with AMap and existing project visuals.",
    }
    (out_dir / "osm_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def build_scenario(name: str, margin_km: float, connect_radius_km: float, use_cache: bool) -> None:
    config = SCENARIOS[name]
    event = load_event(config["source_dir"], name)
    bbox = bbox_from_gcj_points([START_GCJ, TARGET_GCJ, (event.longitude, event.latitude)], margin_km)
    payload = fetch_overpass(bbox, config["cache"], use_cache=use_cache)
    nodes, edges, mapping_rows = build_network(payload, event, connect_radius_km)
    if not edges:
        print(f"No OSM road edges were generated for {name}.", file=sys.stderr)
        sys.exit(1)
    write_dataset(config, event, nodes, edges, mapping_rows, payload, bbox)
    print(f"Created {config['out_dir']} from OSM: {len(nodes)} nodes, {len(edges)} edges, {len(mapping_rows)} disaster-affected edges.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create Beijing earthquake/flood scenarios from OSM regional road-network extracts.")
    parser.add_argument("--scenario", choices=["earthquake", "flood", "all"], default="all")
    parser.add_argument("--margin-km", type=float, default=1.6)
    parser.add_argument("--connect-radius-km", type=float, default=0.45)
    parser.add_argument("--no-cache", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    names = ["earthquake", "flood"] if args.scenario == "all" else [args.scenario]
    for name in names:
        build_scenario(name, args.margin_km, args.connect_radius_km, use_cache=not args.no_cache)


if __name__ == "__main__":
    main()
