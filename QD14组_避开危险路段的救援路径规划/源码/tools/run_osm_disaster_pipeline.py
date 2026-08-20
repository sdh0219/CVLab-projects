from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

DEFAULT_HIGHWAYS = {
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

DEFAULT_EXCLUDED_SERVICE = {"parking_aisle", "driveway", "private"}

EDGE_FIELDS = [
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
]


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


def out_of_china(lon: float, lat: float) -> bool:
    return lon < 72.004 or lon > 137.8347 or lat < 0.8293 or lat > 55.8271


def transform_lat(lon: float, lat: float) -> float:
    ret = -100.0 + 2.0 * lon + 3.0 * lat + 0.2 * lat * lat + 0.1 * lon * lat + 0.2 * math.sqrt(abs(lon))
    ret += (20.0 * math.sin(6.0 * lon * math.pi) + 20.0 * math.sin(2.0 * lon * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * math.pi) + 40.0 * math.sin(lat / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * math.pi) + 320.0 * math.sin(lat * math.pi / 30.0)) * 2.0 / 3.0
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


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def resolve_path(value: str | None, base_dir: Path) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = base_dir / path
    return path


def require_object(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"Config field '{name}' must be an object.")
    return value


def make_event(config: dict[str, Any]) -> DisasterEvent:
    scenario_id = str(config["scenario_id"])
    disaster = require_object(config, "disaster")
    return DisasterEvent(
        event_id=str(disaster.get("event_id", f"{scenario_id.upper()}-EVENT-01")),
        scenario=scenario_id,
        disaster_type=str(disaster["type"]),
        name=str(disaster["name"]),
        event_date=str(disaster.get("date", "")),
        longitude=float(disaster["lon"]),
        latitude=float(disaster["lat"]),
        influence_radius_km=float(disaster["influence_radius_km"]),
        danger_type=str(disaster.get("danger_type", disaster["type"])),
        severity=str(disaster.get("severity", "high")),
        source_title=str(disaster.get("source_title", "")),
        source_url=str(disaster.get("source_url", "")),
        evidence=str(disaster.get("evidence", "")),
        mapping_note=str(
            disaster.get(
                "mapping_note",
                "Road segments inside the historical disaster influence buffer are marked as risk roads.",
            )
        ),
    )


def bbox_from_config(config: dict[str, Any], event: DisasterEvent) -> tuple[float, float, float, float]:
    bbox_config = config.get("bbox", {})
    if all(key in bbox_config for key in ("south", "west", "north", "east")):
        return (
            float(bbox_config["south"]),
            float(bbox_config["west"]),
            float(bbox_config["north"]),
            float(bbox_config["east"]),
        )

    start = require_object(config, "start")
    target = require_object(config, "target")
    points = [
        (float(start["lon"]), float(start["lat"])),
        (float(target["lon"]), float(target["lat"])),
        (event.longitude, event.latitude),
    ]
    for row in bbox_config.get("extra_points", []):
        points.append((float(row["lon"]), float(row["lat"])))

    margin_km = float(bbox_config.get("margin_km", 1.5))
    wgs_points = [gcj02_to_wgs84(lon, lat) for lon, lat in points]
    min_lon = min(lon for lon, _ in wgs_points)
    max_lon = max(lon for lon, _ in wgs_points)
    min_lat = min(lat for _, lat in wgs_points)
    max_lat = max(lat for _, lat in wgs_points)
    center_lat = (min_lat + max_lat) / 2.0
    lat_margin = margin_km / 110.574
    lon_margin = margin_km / (111.320 * max(math.cos(math.radians(center_lat)), 0.2))
    return min_lat - lat_margin, min_lon - lon_margin, max_lat + lat_margin, max_lon + lon_margin


def fetch_overpass(
    bbox: tuple[float, float, float, float],
    cache_path: Path,
    highway_types: set[str],
    use_cache: bool,
    timeout_seconds: int,
) -> dict[str, Any]:
    if use_cache and cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    south, west, north, east = bbox
    highway_regex = "|".join(sorted(highway_types))
    query = f"""
[out:json][timeout:{timeout_seconds}];
(
  way["highway"~"^({highway_regex})$"]({south:.7f},{west:.7f},{north:.7f},{east:.7f});
);
out body;
>;
out skel qt;
"""
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    request = urllib.request.Request(
        OVERPASS_URL,
        data=data,
        headers={"User-Agent": "rescue-route-planning-course-project"},
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds + 40) as response:
        payload = json.loads(response.read().decode("utf-8"))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


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


def base_congestion_for_highway(highway: str, config: dict[str, Any]) -> float:
    defaults = {
        "motorway": 0.04,
        "trunk": 0.05,
        "primary": 0.08,
        "secondary": 0.08,
        "tertiary": 0.07,
        "residential": 0.05,
        "living_street": 0.05,
        "service": 0.04,
    }
    custom = config.get("base_congestion_by_highway", {})
    return float(custom.get(highway, defaults.get(highway, 0.05)))


def build_network(
    payload: dict[str, Any],
    config: dict[str, Any],
    event: DisasterEvent,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    osm_config = config.get("osm", {})
    allowed_highways = set(osm_config.get("highway_types", DEFAULT_HIGHWAYS))
    excluded_service = set(osm_config.get("exclude_service", DEFAULT_EXCLUDED_SERVICE))

    osm_nodes_raw: dict[int, tuple[float, float]] = {}
    ways: list[dict[str, Any]] = []
    for element in payload.get("elements", []):
        if element.get("type") == "node":
            osm_nodes_raw[int(element["id"])] = (float(element["lon"]), float(element["lat"]))
        elif element.get("type") == "way":
            tags = element.get("tags") or {}
            highway = tags.get("highway")
            if highway not in allowed_highways:
                continue
            if tags.get("access") in {"private", "no"}:
                continue
            if highway == "service" and tags.get("service") in excluded_service:
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
        nodes[node_id] = {
            "node_id": node_id,
            "x": round(lon_gcj, 7),
            "y": round(lat_gcj, 7),
            "label": "",
            "type": "normal",
        }

    edges: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for way in ways:
        tags = way.get("tags") or {}
        highway = str(tags.get("highway", "road"))
        road_name = str(tags.get("name") or tags.get("ref") or highway)
        way_nodes = [node_id for node_id in way.get("nodes", []) if node_id in nodes_by_osm]
        for source_osm, target_osm in zip(way_nodes, way_nodes[1:]):
            source = nodes_by_osm[source_osm]
            target = nodes_by_osm[target_osm]
            if source == target:
                continue
            key = (*sorted((source, target)), road_name, highway)
            if key in seen:
                continue
            seen.add(key)
            source_point = (float(nodes[source]["x"]), float(nodes[source]["y"]))
            target_point = (float(nodes[target]["x"]), float(nodes[target]["y"]))
            distance = haversine_km(source_point, target_point)
            if distance <= 0:
                continue

            event_distance = segment_distance_km(
                event.longitude,
                event.latitude,
                source_point[0],
                source_point[1],
                target_point[0],
                target_point[1],
            )
            danger_type = event.danger_type if event_distance <= event.influence_radius_km else "normal"
            edge_id = f"OSM{len(edges) + 1:05d}"
            edge = {
                "edge_id": edge_id,
                "from": source,
                "to": target,
                "distance": round(distance, 4),
                "danger_type": danger_type,
                "congestion": round(base_congestion_for_highway(highway, config), 3),
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

    add_virtual_connectors(nodes, edges, config)
    traffic_rows = apply_traffic_mapping(edges, config)
    return list(nodes.values()), edges, mapping_rows + traffic_rows["danger_rows"], traffic_rows["traffic_rows"]


def add_virtual_connectors(nodes: dict[str, dict[str, Any]], edges: list[dict[str, Any]], config: dict[str, Any]) -> None:
    start = require_object(config, "start")
    target = require_object(config, "target")
    connector_config = config.get("connectors", {})
    count = int(connector_config.get("count", 5))
    max_distance_km = float(connector_config.get("max_distance_km", 0.5))

    nodes["START"] = {
        "node_id": "START",
        "x": float(start["lon"]),
        "y": float(start["lat"]),
        "label": str(start.get("name", "Start")),
        "type": "start",
    }
    nodes["TARGET"] = {
        "node_id": "TARGET",
        "x": float(target["lon"]),
        "y": float(target["lat"]),
        "label": str(target.get("name", "Target")),
        "type": "target",
    }

    for connector_name, virtual_id, point in [
        ("start connector", "START", (float(start["lon"]), float(start["lat"]))),
        ("target connector", "TARGET", (float(target["lon"]), float(target["lat"]))),
    ]:
        linked = nearest_nodes(nodes, point, count=count, max_distance_km=max_distance_km)
        if not linked:
            raise ValueError(
                f"No OSM node found near {virtual_id}. Increase connectors.max_distance_km or bbox.margin_km."
            )
        for node_id, distance in linked:
            source_point = (float(nodes[virtual_id]["x"]), float(nodes[virtual_id]["y"]))
            target_point = (float(nodes[node_id]["x"]), float(nodes[node_id]["y"]))
            edges.append(
                {
                    "edge_id": f"OSM{len(edges) + 1:05d}",
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


def apply_traffic_mapping(edges: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    traffic_path = resolve_path(config.get("traffic_csv"), ROOT)
    if not traffic_path:
        return {"traffic_rows": [], "danger_rows": []}
    traffic_rows = read_csv(traffic_path)
    if not traffic_rows:
        return {"traffic_rows": [], "danger_rows": []}

    status_scores = {"0": 0.15, "1": 0.05, "2": 0.60, "3": 0.90}
    traffic_mappings: list[dict[str, Any]] = []
    danger_rows: list[dict[str, Any]] = []
    for edge in edges:
        edge_name = str(edge.get("road_name", ""))
        if not edge_name or edge["variant"] == "connector":
            continue
        candidates = [
            row
            for row in traffic_rows
            if row.get("road_name") and (row["road_name"] in edge_name or edge_name in row["road_name"])
        ]
        if not candidates:
            continue
        row = candidates[0]
        status = str(row.get("status", "0"))
        original = float(edge["congestion"])
        edge["congestion"] = round(max(original, status_scores.get(status, 0.15)), 3)
        if status in {"2", "3"} and edge["danger_type"] == "normal":
            edge["danger_type"] = "congestion"
            danger_rows.append(
                {
                    "edge_id": edge["edge_id"],
                    "from": edge["from"],
                    "to": edge["to"],
                    "road_name": edge_name,
                    "scenario": config["scenario_id"],
                    "event_id": "TRAFFIC",
                    "event_name": "Traffic congestion overlay",
                    "danger_type": "congestion",
                    "distance_to_event_km": "",
                    "influence_radius_km": "",
                    "mapping_method": "Matched traffic CSV by road name",
                    "source_url": str(config.get("traffic_source_url", "")),
                }
            )
        traffic_mappings.append(
            {
                "edge_id": edge["edge_id"],
                "from": edge["from"],
                "to": edge["to"],
                "road_name": edge_name,
                "traffic_road_name": row.get("road_name", ""),
                "traffic_status": status,
                "traffic_status_label": row.get("status_label", ""),
                "traffic_speed_kmh": row.get("speed_kmh", ""),
                "original_congestion": original,
                "mapped_congestion": edge["congestion"],
                "traffic_captured_at": row.get("captured_at", ""),
            }
        )
    return {"traffic_rows": traffic_mappings, "danger_rows": danger_rows}


def write_dataset(
    data_dir: Path,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    mapping_rows: list[dict[str, Any]],
    traffic_rows: list[dict[str, Any]],
    config: dict[str, Any],
    event: DisasterEvent,
    payload: dict[str, Any],
    bbox: tuple[float, float, float, float],
) -> None:
    start = require_object(config, "start")
    target = require_object(config, "target")
    data_dir.mkdir(parents=True, exist_ok=True)
    write_csv(data_dir / "nodes.csv", nodes, ["node_id", "x", "y", "label", "type"])
    write_csv(data_dir / "edges.csv", edges, EDGE_FIELDS)
    scenario = {
        "scenario_name": config.get("scenario_name", config["scenario_id"]),
        "start_node": "START",
        "target_node": "TARGET",
        "start_label": f"起点：{start.get('name', 'START')}",
        "target_label": f"终点：{target.get('name', 'TARGET')}",
        "risk_factors": config.get(
            "risk_factors",
            {"normal": 1.0, "congestion": 1.4, "flood": 2.2, "collapse": 4.0, "fire": 9.0},
        ),
        "congestion_weight": float(config.get("congestion_weight", 0.6)),
        "danger_fixed_costs": config.get("danger_fixed_costs", {}),
        "undirected": bool(config.get("undirected", True)),
        "disaster_type": event.disaster_type,
        "historical_event_id": event.event_id,
        "historical_event_name": event.name,
        "historical_event_date": event.event_date,
        "historical_event_source": event.source_url,
        "road_data_source": "OpenStreetMap / Overpass API regional highway extract",
        "traffic_data_source": config.get("traffic_data_source", ""),
        "description": config.get(
            "description",
            "The pipeline builds a regional OSM road network, overlays historical disaster risk, and runs Dijkstra.",
        ),
    }
    (data_dir / "scenario.json").write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(data_dir / "disaster_events.csv", [asdict(event)], list(asdict(event).keys()))
    write_csv(
        data_dir / "road_disaster_mapping.csv",
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
        data_dir / "road_traffic_mapping.csv",
        traffic_rows,
        [
            "edge_id",
            "from",
            "to",
            "road_name",
            "traffic_road_name",
            "traffic_status",
            "traffic_status_label",
            "traffic_speed_kmh",
            "original_congestion",
            "mapped_congestion",
            "traffic_captured_at",
        ],
    )
    metadata = {
        "scenario_id": config["scenario_id"],
        "bbox_wgs84": {"south": bbox[0], "west": bbox[1], "north": bbox[2], "east": bbox[3]},
        "overpass_elements": len(payload.get("elements", [])),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "disaster_affected_edge_count": len([row for row in mapping_rows if row.get("event_id") != "TRAFFIC"]),
        "traffic_mapped_edge_count": len(traffic_rows),
        "coordinate_note": "OSM WGS84 coordinates are converted to GCJ-02 so they align with Chinese map coordinates.",
    }
    (data_dir / "osm_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def run_command(command: list[str]) -> None:
    print("[run] " + " ".join(command))
    completed = subprocess.run(command, cwd=ROOT)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {completed.returncode}: {' '.join(command)}")


def run_planning(data_dir: Path, output_dir: Path) -> None:
    run_command(
        [
            sys.executable,
            str(ROOT / "src" / "rescue_planner.py"),
            "--data-dir",
            str(data_dir),
            "--output-dir",
            str(output_dir),
        ]
    )


def render_visual(data_dir: Path, output_dir: Path, scenario_label: str) -> Path | None:
    try:
        sys.path.insert(0, str(ROOT))
        from tools.create_abstract_route_maps import render_scene
    except Exception as exc:
        print(f"[warn] Abstract visual renderer unavailable: {exc}")
        return None
    return render_scene(data_dir, output_dir, scenario_label)


def load_results(output_dir: Path) -> list[dict[str, Any]]:
    path = output_dir / "path_results.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def write_pipeline_summary(
    output_dir: Path,
    data_dir: Path,
    config: dict[str, Any],
    event: DisasterEvent,
    visual_path: Path | None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = read_json(data_dir / "osm_metadata.json")
    results = load_results(output_dir)
    by_mode = {row["mode"]: row for row in results if row.get("algorithm") == "Dijkstra"}

    lines = [
        f"# {config.get('scenario_name', config['scenario_id'])} 流水线摘要",
        "",
        "## 数据来源",
        "- 道路数据：OpenStreetMap / Overpass API 区域路网抽取。",
        f"- 历史灾害：{event.source_title or event.name}。",
        f"- 灾害资料链接：{event.source_url or '未填写'}",
        "",
        "## 空间映射方法",
        f"- 灾害类型：{event.disaster_type}。",
        f"- 影响半径：{event.influence_radius_km} km。",
        f"- 映射规则：{event.mapping_note}",
        "- 道路坐标由 OSM 的 WGS84 转为 GCJ-02，再与灾害缓冲区做叠加判断。",
        "",
        "## 路网规模",
        f"- 节点数量：{metadata.get('node_count')}",
        f"- 道路边数量：{metadata.get('edge_count')}",
        f"- 灾害影响道路边数量：{metadata.get('disaster_affected_edge_count')}",
        f"- 交通匹配道路边数量：{metadata.get('traffic_mapped_edge_count')}",
        "",
        "## Dijkstra 结果",
    ]
    for mode, label in [("distance", "普通最短路径"), ("safe", "安全路径")]:
        row = by_mode.get(mode, {})
        lines.extend(
            [
                f"### {label}",
                f"- 距离：{row.get('total_distance', '-') } km",
                f"- 综合代价：{row.get('total_cost', '-')}",
                f"- 危险边数量：{row.get('dangerous_edge_count', '-')}",
                f"- 危险类型：{', '.join(row.get('danger_types', [])) or '无'}",
            ]
        )
    lines.extend(
        [
            "",
            "## 生成文件",
            f"- 数据目录：{data_dir}",
            f"- 结果目录：{output_dir}",
            f"- 路径结果：{output_dir / 'path_results.json'}",
            f"- 对比表：{output_dir / 'path_comparison.csv'}",
            f"- 可视化图：{visual_path if visual_path else '未生成'}",
        ]
    )
    (output_dir / "pipeline_summary.md").write_text("\n".join(lines), encoding="utf-8")


def prepare_dirs(config: dict[str, Any], overwrite: bool) -> tuple[Path, Path, Path]:
    scenario_id = str(config["scenario_id"])
    data_dir = ROOT / "data" / scenario_id
    output_dir = ROOT / "outputs" / scenario_id
    raw_dir = ROOT / "data" / f"{scenario_id}_raw"
    if not overwrite:
        for path in (data_dir, output_dir):
            if path.exists() and any(path.iterdir()):
                raise FileExistsError(f"{path} already exists. Use --overwrite if you really want to regenerate it.")
    return data_dir, output_dir, raw_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One-click OSM disaster rescue-route pipeline for new report scenarios.")
    parser.add_argument("--config", type=Path, required=True, help="JSON scenario config.")
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting an existing scenario data/output folder.")
    parser.add_argument("--no-cache", action="store_true", help="Fetch fresh Overpass data instead of using cached raw JSON.")
    parser.add_argument("--skip-fetch", action="store_true", help="Use cached Overpass raw JSON only.")
    parser.add_argument("--skip-planning", action="store_true", help="Only generate the dataset; do not run Dijkstra.")
    parser.add_argument("--skip-visual", action="store_true", help="Do not render route_map_abstract.png.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = read_json(args.config)
    if "scenario_id" not in config:
        raise ValueError("Config must include scenario_id.")

    event = make_event(config)
    data_dir, output_dir, raw_dir = prepare_dirs(config, overwrite=args.overwrite)
    bbox = bbox_from_config(config, event)
    osm_config = config.get("osm", {})
    highway_types = set(osm_config.get("highway_types", DEFAULT_HIGHWAYS))
    timeout_seconds = int(osm_config.get("timeout_seconds", 160))
    cache_path = raw_dir / "overpass_roads.json"

    if args.skip_fetch and not cache_path.exists():
        raise FileNotFoundError(f"--skip-fetch was used, but cache is missing: {cache_path}")

    payload = fetch_overpass(
        bbox,
        cache_path,
        highway_types=highway_types,
        use_cache=(not args.no_cache) or args.skip_fetch,
        timeout_seconds=timeout_seconds,
    )
    nodes, edges, disaster_mapping_rows, traffic_rows = build_network(payload, config, event)
    if not edges:
        raise RuntimeError("No OSM road edges were generated. Check bbox and highway_types.")

    write_dataset(data_dir, nodes, edges, disaster_mapping_rows, traffic_rows, config, event, payload, bbox)

    visual_path: Path | None = None
    if not args.skip_planning:
        run_planning(data_dir, output_dir)
        if not args.skip_visual:
            visual_path = render_visual(data_dir, output_dir, str(config.get("scenario_label", config["scenario_id"])))
        write_pipeline_summary(output_dir, data_dir, config, event, visual_path)

    print("")
    print("[ok] Pipeline finished.")
    print(f"Data: {data_dir}")
    print(f"Outputs: {output_dir}")
    if visual_path:
        print(f"Visual: {visual_path}")


if __name__ == "__main__":
    main()
