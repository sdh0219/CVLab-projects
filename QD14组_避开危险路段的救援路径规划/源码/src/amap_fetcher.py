from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "data" / "amap_request.json"
DEFAULT_EXAMPLE = PROJECT_ROOT / "data" / "amap_request.example.json"

AMAP_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"
AMAP_DRIVING_URL = "https://restapi.amap.com/v3/direction/driving"


def request_json(url: str, params: dict[str, Any], retries: int = 3) -> dict[str, Any]:
    query = urllib.parse.urlencode(params, doseq=True)
    for attempt in range(retries + 1):
        with urllib.request.urlopen(f"{url}?{query}", timeout=30) as response:
            data = response.read().decode("utf-8")
        payload = json.loads(data)
        if payload.get("status") == "1":
            return payload
        info = payload.get("info") or "Unknown AMap API error"
        infocode = payload.get("infocode") or "no infocode"
        if infocode == "10021" and attempt < retries:
            time.sleep(1.5 * (attempt + 1))
            continue
        raise RuntimeError(f"AMap API failed: {info} ({infocode})")
    raise RuntimeError("AMap API failed after retries.")


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Copy {DEFAULT_EXAMPLE.name} to {path.name}, then edit addresses and AMAP_KEY."
        )
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def coordinate_from_place(place: dict[str, Any], key: str) -> str:
    if "location" in place:
        return str(place["location"])
    address = place.get("address")
    if not address:
        raise ValueError("Place must contain either location or address.")
    params = {"key": key, "address": address}
    if place.get("city"):
        params["city"] = place["city"]
    payload = request_json(AMAP_GEOCODE_URL, params)
    geocodes = payload.get("geocodes") or []
    if not geocodes:
        raise RuntimeError(f"AMap geocode returned no location for address: {address}")
    return geocodes[0]["location"]


def coordinate_from_value(value: str | dict[str, Any], key: str) -> str:
    if isinstance(value, dict):
        return coordinate_from_place(value, key)
    return str(value)


def fetch_driving_route(
    origin: str,
    destination: str,
    strategy: int,
    key: str,
    waypoints: str | None = None,
) -> dict[str, Any]:
    params = {
        "key": key,
        "origin": origin,
        "destination": destination,
        "strategy": strategy,
        "extensions": "all",
        "output": "json",
    }
    if waypoints:
        params["waypoints"] = waypoints
    return request_json(AMAP_DRIVING_URL, params)


def parse_point(raw: str) -> tuple[float, float]:
    lon, lat = raw.split(",", 1)
    return float(lon), float(lat)


def first_last_polyline(polyline: str) -> tuple[tuple[float, float], tuple[float, float]]:
    points = [parse_point(item) for item in polyline.split(";") if item]
    if not points:
        raise ValueError("AMap step has empty polyline.")
    return points[0], points[-1]


def danger_type_for_step(step: dict[str, Any], rules: list[dict[str, Any]]) -> str:
    road_name = step.get("road") or step.get("instruction") or ""
    instruction = step.get("instruction") or ""
    for rule in rules:
        contains = str(rule.get("contains", ""))
        if not contains:
            continue
        field = rule.get("match_field", "road_name")
        value = road_name if field == "road_name" else instruction
        if contains in value:
            return str(rule.get("danger_type", "normal"))
    tmcs = step.get("tmcs") or []
    statuses = {item.get("status") for item in tmcs if isinstance(item, dict)}
    if statuses.intersection({"拥堵", "严重拥堵", "缓慢"}):
        return "congestion"
    return "normal"


def congestion_for_step(step: dict[str, Any]) -> float:
    tmcs = step.get("tmcs") or []
    status_scores = {"畅通": 0.05, "未知": 0.15, "缓慢": 0.45, "拥堵": 0.75, "严重拥堵": 0.95}
    scores = [status_scores.get(item.get("status"), 0.15) for item in tmcs if isinstance(item, dict)]
    if scores:
        return round(sum(scores) / len(scores), 3)
    return 0.1


def build_dataset(config: dict[str, Any], key: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    origin = coordinate_from_place(config["origin"], key)
    destination = coordinate_from_place(config["destination"], key)
    danger_rules = config.get("danger_rules") or []
    route_requests = build_route_requests(config, key)
    merge_route_nodes = bool(config.get("merge_route_nodes", False))
    use_step_polyline_nodes = bool(config.get("use_step_polyline_nodes", False))
    node_snap_decimals = int(config.get("node_snap_decimals", 6))

    node_by_location: dict[str, str] = {}
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    def node_id_for(
        location: tuple[float, float],
        label: str,
        node_type: str = "normal",
        key_override: str | None = None,
    ) -> str:
        key_location = key_override or f"{location[0]:.{node_snap_decimals}f},{location[1]:.{node_snap_decimals}f}"
        if key_location not in node_by_location:
            node_id = "N" + str(len(node_by_location) + 1).zfill(3)
            node_by_location[key_location] = node_id
            nodes.append(
                {
                    "node_id": node_id,
                    "x": location[0],
                    "y": location[1],
                    "label": label,
                    "type": node_type,
                }
            )
        return node_by_location[key_location]

    start_location = parse_point(origin)
    target_location = parse_point(destination)
    start_node = node_id_for(start_location, "AMap origin", "start")
    target_node = node_id_for(target_location, "AMap destination", "target")

    seen_edges: set[tuple[str, str, str]] = set()
    for request_index, route_request in enumerate(route_requests):
        strategy = int(route_request.get("strategy", 0))
        variant_name = route_request.get("name", f"strategy_{strategy}")
        request_origin = route_request.get("origin", origin)
        request_destination = route_request.get("destination", destination)
        waypoints = route_request.get("waypoints")
        request_start = (
            start_node
            if request_origin == origin
            else node_id_for(
                parse_point(request_origin),
                f"{variant_name} origin",
                "context",
                key_override=None if merge_route_nodes else f"request:{request_index}:origin",
            )
        )
        request_target = (
            target_node
            if request_destination == destination
            else node_id_for(
                parse_point(request_destination),
                f"{variant_name} destination",
                "context",
                key_override=None if merge_route_nodes else f"request:{request_index}:destination",
            )
        )
        payload = fetch_driving_route(request_origin, request_destination, strategy, key, waypoints=waypoints)
        time.sleep(0.8)
        paths = payload.get("route", {}).get("paths") or []
        for path_index, amap_path in enumerate(paths):
            steps = amap_path.get("steps") or []
            previous_node = request_start
            for step_index, step in enumerate(steps):
                polyline = step.get("polyline") or ""
                if not polyline:
                    continue
                source_location, target_location_step = first_last_polyline(polyline)
                source = (
                    previous_node
                    if not use_step_polyline_nodes
                    else (
                        request_start
                        if step_index == 0
                        else node_id_for(
                            source_location,
                            step.get("road") or "route point",
                            key_override=(
                                None
                                if merge_route_nodes
                                else (
                                    f"request:{request_index}:strategy:{strategy}:path:{path_index}:"
                                    f"step:{step_index}:source"
                                )
                            ),
                        )
                    )
                )
                target = (
                    request_target
                    if step_index == len(steps) - 1
                    else node_id_for(
                        target_location_step,
                        step.get("road") or "route point",
                        key_override=(
                            None
                            if merge_route_nodes
                            else (
                                f"request:{request_index}:strategy:{strategy}:path:{path_index}:"
                                f"step:{step_index}:target"
                            )
                        ),
                    )
                )
                if source == target:
                    continue
                road_name = step.get("road") or step.get("instruction") or "unnamed road"
                edge_key = tuple(sorted((source, target)) + [road_name])
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)
                edge_id = "AM" + str(len(edges) + 1).zfill(4)
                danger_type = danger_type_for_step(step, danger_rules)
                edges.append(
                    {
                        "edge_id": edge_id,
                        "from": source,
                        "to": target,
                        "distance": round(float(step.get("distance") or 0) / 1000.0, 3),
                        "danger_type": danger_type,
                        "congestion": congestion_for_step(step),
                        "passable": "true",
                        "road_name": road_name,
                        "instruction": step.get("instruction") or "",
                        "polyline": polyline,
                        "strategy": strategy,
                        "variant": variant_name,
                        "path_index": path_index,
                        "step_index": step_index,
                    }
                )
                previous_node = target

    scenario = {
        "scenario_name": "AMap real driving route rescue planning",
        "start_node": start_node,
        "target_node": target_node,
        "risk_factors": {
            "normal": 1.0,
            "congestion": 1.4,
            "flood": 2.2,
            "collapse": 4.0,
        },
        "congestion_weight": 0.6,
        "undirected": True,
        "description": "Road geometry and driving steps are fetched from AMap Web Service. Disaster labels are configured locally in danger_rules.",
        "amap_origin": origin,
        "amap_destination": destination,
    }
    return nodes, edges, scenario


def build_route_requests(config: dict[str, Any], key: str) -> list[dict[str, Any]]:
    explicit_requests = config.get("route_requests")
    if explicit_requests:
        requests: list[dict[str, Any]] = []
        for item in list(explicit_requests) + list(config.get("context_routes") or []):
            request = dict(item)
            if "origin" in request:
                request["origin"] = coordinate_from_value(request["origin"], key)
            if "destination" in request:
                request["destination"] = coordinate_from_value(request["destination"], key)
            waypoint_places = item.get("waypoint_places") or []
            if waypoint_places:
                request["waypoints"] = ";".join(coordinate_from_place(place, key) for place in waypoint_places)
            requests.append(request)
            time.sleep(0.6)
        return requests

    strategies = config.get("strategies") or [0, 2, 5]
    return [{"name": f"strategy_{strategy}", "strategy": strategy} for strategy in strategies]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_dataset(output_dir: Path, nodes: list[dict[str, Any]], edges: list[dict[str, Any]], scenario: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "nodes.csv", nodes, ["node_id", "x", "y", "label", "type"])
    write_csv(
        output_dir / "edges.csv",
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
    with (output_dir / "scenario.json").open("w", encoding="utf-8") as f:
        json.dump(scenario, f, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch real driving-route data from AMap Web Service.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    key_env = config.get("key_env", "AMAP_KEY")
    key = os.environ.get(key_env)
    if not key:
        print(f"Missing AMap API key. Set environment variable {key_env}, then rerun.", file=sys.stderr)
        sys.exit(2)
    output_dir = PROJECT_ROOT / config.get("output_data_dir", "data/amap")
    nodes, edges, scenario = build_dataset(config, key)
    write_dataset(output_dir, nodes, edges, scenario)
    print(f"Fetched AMap data: {len(nodes)} nodes, {len(edges)} edges")
    print(f"Data written to: {output_dir}")


if __name__ == "__main__":
    main()
