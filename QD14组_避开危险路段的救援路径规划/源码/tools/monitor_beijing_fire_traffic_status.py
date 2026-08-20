from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

from fetch_beijing_fire_traffic_status import DEFAULT_OUTPUT, fetch_traffic


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MONITOR_OUTPUT = ROOT / "data" / "amap_fire" / "traffic_monitor_beijing_fire.csv"


FIELDNAMES = [
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
    "sample_index",
]


def append_rows(path: Path, rows: list[dict], sample_index: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        for row in rows:
            item = dict(row)
            item["sample_index"] = sample_index
            writer.writerow(item)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append repeated AMap traffic-status samples for the Beijing fire scenario.")
    parser.add_argument("--location", default="116.280437,39.889128")
    parser.add_argument("--radius", type=int, default=3000)
    parser.add_argument("--level", type=int, default=5)
    parser.add_argument("--samples", type=int, default=13, help="Number of samples to collect.")
    parser.add_argument("--interval-seconds", type=int, default=300, help="Seconds between samples.")
    parser.add_argument("--output", type=Path, default=DEFAULT_MONITOR_OUTPUT)
    parser.add_argument("--latest-output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--key-env", default="AMAP_KEY")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    key = os.environ.get(args.key_env)
    if not key:
        print(f"Missing AMap API key. Set environment variable {args.key_env}, then rerun.", file=sys.stderr)
        sys.exit(2)
    for sample_index in range(1, args.samples + 1):
        trafficinfo, rows = fetch_traffic(key, args.location, args.radius, args.level)
        append_rows(args.output, rows, sample_index)
        if args.latest_output:
            latest_path = Path(args.latest_output)
            latest_path.parent.mkdir(parents=True, exist_ok=True)
            with latest_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=[name for name in FIELDNAMES if name != "sample_index"], extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
        evaluation = trafficinfo.get("evaluation") or {}
        print(
            f"sample {sample_index}/{args.samples}: {len(rows)} roads | "
            f"{evaluation.get('description', 'no evaluation')} | "
            f"saved to {args.output}"
        )
        if sample_index < args.samples:
            time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
