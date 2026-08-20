from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "amap_fire_base" / "traffic_status_circle.csv"
TRAFFIC_CIRCLE_URL = "https://restapi.amap.com/v3/traffic/status/circle"


STATUS_LABELS = {
    "0": "unknown",
    "1": "expedite",
    "2": "congested",
    "3": "blocked",
}


def request_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    with urllib.request.urlopen(f"{url}?{query}", timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("status") != "1":
        info = payload.get("info") or "Unknown AMap API error"
        infocode = payload.get("infocode") or "no infocode"
        raise RuntimeError(f"AMap traffic API failed: {info} ({infocode})")
    return payload


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fetch_traffic(key: str, location: str, radius: int, level: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = request_json(
        TRAFFIC_CIRCLE_URL,
        {
            "key": key,
            "location": location,
            "radius": str(radius),
            "level": str(level),
            "extensions": "all",
            "output": "json",
        },
    )
    trafficinfo = payload.get("trafficinfo") or {}
    evaluation = trafficinfo.get("evaluation") or {}
    captured_at = datetime.now().isoformat(timespec="seconds")
    rows: list[dict[str, Any]] = []
    for index, road in enumerate(trafficinfo.get("roads") or [], start=1):
        status = str(road.get("status", "0"))
        rows.append(
            {
                "record_id": f"TR{index:04d}",
                "captured_at": captured_at,
                "query_location": location,
                "query_radius_m": radius,
                "query_level": level,
                "area_description": trafficinfo.get("description", ""),
                "evaluation_status": evaluation.get("status", ""),
                "evaluation_description": evaluation.get("description", ""),
                "evaluation_expedite": evaluation.get("expedite", ""),
                "evaluation_congested": evaluation.get("congested", ""),
                "evaluation_blocked": evaluation.get("blocked", ""),
                "evaluation_unknown": evaluation.get("unknown", ""),
                "road_name": road.get("name", ""),
                "status": status,
                "status_label": STATUS_LABELS.get(status, "unknown"),
                "direction": road.get("direction", ""),
                "angle": road.get("angle", ""),
                "speed_kmh": road.get("speed", ""),
                "lcodes": road.get("lcodes", ""),
                "polyline": road.get("polyline", ""),
            }
        )
    return trafficinfo, rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch AMap real-time traffic status near the Beijing fire scenario.")
    parser.add_argument("--location", default="116.280437,39.889128")
    parser.add_argument("--radius", type=int, default=3000)
    parser.add_argument("--level", type=int, default=5)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--key-env", default="AMAP_KEY")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    key = os.environ.get(args.key_env)
    if not key:
        print(f"Missing AMap API key. Set environment variable {args.key_env}, then rerun.", file=sys.stderr)
        sys.exit(2)
    trafficinfo, rows = fetch_traffic(key, args.location, args.radius, args.level)
    if not rows:
        raise RuntimeError("AMap traffic API returned no road status rows.")
    fieldnames = [
        "record_id",
        "captured_at",
        "query_location",
        "query_radius_m",
        "query_level",
        "area_description",
        "evaluation_status",
        "evaluation_description",
        "evaluation_expedite",
        "evaluation_congested",
        "evaluation_blocked",
        "evaluation_unknown",
        "road_name",
        "status",
        "status_label",
        "direction",
        "angle",
        "speed_kmh",
        "lcodes",
        "polyline",
    ]
    write_csv(args.output, rows, fieldnames)
    evaluation = trafficinfo.get("evaluation") or {}
    print(
        "Fetched traffic status: "
        f"{len(rows)} roads | {evaluation.get('description', 'no evaluation')} | "
        f"output: {args.output}"
    )


if __name__ == "__main__":
    main()
