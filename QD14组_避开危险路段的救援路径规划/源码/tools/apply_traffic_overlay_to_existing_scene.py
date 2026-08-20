from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

STATUS_SCORES = {
    "0": 0.15,
    "1": 0.05,
    "2": 0.60,
    "3": 0.90,
}


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


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def normalize_name(name: str) -> str:
    return (
        name.strip()
        .replace(" ", "")
        .replace("（", "(")
        .replace("）", ")")
    )


def find_traffic_row(edge_name: str, traffic_rows: list[dict[str, str]]) -> dict[str, str] | None:
    edge_name = normalize_name(edge_name)
    if not edge_name:
        return None
    for row in traffic_rows:
        traffic_name = normalize_name(row.get("road_name", ""))
        if not traffic_name:
            continue
        if traffic_name in edge_name or edge_name in traffic_name:
            return row
    return None


def apply_overlay(data_dir: Path, traffic_csvs: list[Path], source_url: str) -> dict[str, int]:
    edges_path = data_dir / "edges.csv"
    mapping_path = data_dir / "road_disaster_mapping.csv"
    traffic_mapping_path = data_dir / "road_traffic_mapping.csv"
    scenario_path = data_dir / "scenario.json"

    traffic_rows: list[dict[str, str]] = []
    for path in traffic_csvs:
        traffic_rows.extend(read_csv(path))
    if not traffic_rows:
        raise RuntimeError("No traffic rows found. Check --traffic-csv paths.")

    edges = read_csv(edges_path)
    if not edges:
        raise RuntimeError(f"No edges found: {edges_path}")

    traffic_mappings: list[dict[str, Any]] = []
    traffic_danger_rows: list[dict[str, Any]] = []
    matched = congested = blocked = 0

    for edge in edges:
        edge_name = edge.get("road_name", "")
        if not edge_name or edge.get("variant") == "connector":
            continue
        row = find_traffic_row(edge_name, traffic_rows)
        if row is None:
            continue

        matched += 1
        status = str(row.get("status", "0"))
        original = float(edge.get("congestion") or 0)
        mapped = max(original, STATUS_SCORES.get(status, 0.15))
        edge["congestion"] = f"{mapped:.3f}".rstrip("0").rstrip(".")

        if status == "2":
            congested += 1
        elif status == "3":
            blocked += 1

        if status in {"2", "3"} and edge.get("danger_type") == "normal":
            edge["danger_type"] = "congestion"
            traffic_danger_rows.append(
                {
                    "edge_id": edge.get("edge_id", ""),
                    "from": edge.get("from", ""),
                    "to": edge.get("to", ""),
                    "road_name": edge_name,
                    "scenario": data_dir.name,
                    "event_id": "TRAFFIC",
                    "event_name": "Traffic congestion overlay",
                    "danger_type": "congestion",
                    "distance_to_event_km": "",
                    "influence_radius_km": "",
                    "mapping_method": "Matched AMap traffic CSV by road name",
                    "source_url": source_url,
                }
            )

        traffic_mappings.append(
            {
                "edge_id": edge.get("edge_id", ""),
                "from": edge.get("from", ""),
                "to": edge.get("to", ""),
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

    edge_fields = list(read_csv_header(edges_path))
    write_csv(edges_path, edges, edge_fields)

    existing_mapping = [row for row in read_csv(mapping_path) if row.get("event_id") != "TRAFFIC"]
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
    write_csv(mapping_path, existing_mapping + traffic_danger_rows, mapping_fields)

    traffic_fields = [
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
    ]
    write_csv(traffic_mapping_path, traffic_mappings, traffic_fields)

    if scenario_path.exists():
        scenario = read_json(scenario_path)
        scenario["traffic_data_source"] = "AMap traffic status circle API, matched to existing OSM edges by road name"
        scenario["traffic_source_url"] = source_url
        write_json(scenario_path, scenario)

    return {
        "traffic_rows": len(traffic_rows),
        "matched_edges": matched,
        "congested_edges": congested,
        "blocked_edges": blocked,
        "new_congestion_danger_edges": len(traffic_danger_rows),
    }


def read_csv_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        return next(reader)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Overlay AMap traffic CSV onto an existing OSM scene.")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--traffic-csv", type=Path, action="append", required=True)
    parser.add_argument(
        "--source-url",
        default="https://lbs.amap.com/api/webservice/guide/api-advanced/traffic-situation-inquiry",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir
    traffic_csvs = [path if path.is_absolute() else ROOT / path for path in args.traffic_csv]
    stats = apply_overlay(data_dir, traffic_csvs, args.source_url)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
