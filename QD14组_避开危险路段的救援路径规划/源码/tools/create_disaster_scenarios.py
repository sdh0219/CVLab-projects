from __future__ import annotations

import csv
import json
import math
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = ROOT / "data" / "amap"
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


EVENTS = [
    DisasterEvent(
        event_id="EQ1679-BJ-IMPACT-01",
        scenario="earthquake",
        disaster_type="earthquake",
        name="1679 Sanhe-Pinggu earthquake Beijing impact zone",
        event_date="1679-09-02",
        longitude=116.4100,
        latitude=39.9860,
        influence_radius_km=2.7,
        danger_type="collapse",
        severity="high",
        source_title="Public historical records: 1679 Sanhe-Pinggu earthquake",
        source_url="https://en.wikipedia.org/wiki/1679_Sanhe-Pinggu_earthquake",
        evidence=(
            "The 1679 Sanhe-Pinggu earthquake is a historical M8-class event in the "
            "Greater Beijing region. Public historical records describe severe shaking "
            "and damage in Beijing; the project maps a representative local impact "
            "area onto the AMap road network."
        ),
        mapping_note=(
            "Representative Beijing urban impact buffer. Roads whose line segment "
            "intersects the buffer are marked as collapse risk."
        ),
    ),
    DisasterEvent(
        event_id="FL2012-BJ-RAIN-01",
        scenario="flood",
        disaster_type="flood",
        name="2012 July 21 Beijing extreme rainstorm urban waterlogging impact zone",
        event_date="2012-07-21",
        longitude=116.4100,
        latitude=39.9860,
        influence_radius_km=2.7,
        danger_type="flood",
        severity="high",
        source_title="China Meteorological Data Service / public Beijing 7.21 rainstorm records",
        source_url="https://data.cma.cn/",
        evidence=(
            "The 2012 July 21 Beijing rainstorm caused citywide flooding and "
            "waterlogging. Public records report extreme precipitation and serious "
            "urban transport disruption; the project maps a representative urban "
            "waterlogging buffer onto the AMap road network."
        ),
        mapping_note=(
            "Representative urban waterlogging buffer. Roads whose line segment "
            "intersects the buffer are marked as flood risk."
        ),
    ),
]


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), reader.fieldnames or []


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_nodes() -> dict[str, tuple[float, float]]:
    rows, _ = read_csv(BASE_DIR / "nodes.csv")
    return {row["node_id"]: (float(row["x"]), float(row["y"])) for row in rows}


def base_congestion_type(edge: dict[str, str]) -> str:
    congestion = float(edge.get("congestion") or 0)
    return "congestion" if congestion >= 0.35 else "normal"


def km_per_degree(lon: float, lat: float, ref_lat: float) -> tuple[float, float]:
    x = lon * 111.320 * math.cos(math.radians(ref_lat))
    y = lat * 110.574
    return x, y


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
    closest_x = sx + t * dx
    closest_y = sy + t * dy
    return math.hypot(px - closest_x, py - closest_y)


def map_edges_for_scenario(
    base_edges: list[dict[str, str]],
    nodes: dict[str, tuple[float, float]],
    event: DisasterEvent,
) -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    mapped_edges: list[dict[str, str]] = []
    mapping_rows: list[dict[str, object]] = []

    for edge in base_edges:
        item = dict(edge)
        source_lon, source_lat = nodes[item["from"]]
        target_lon, target_lat = nodes[item["to"]]
        distance_to_event = segment_distance_km(
            event.longitude,
            event.latitude,
            source_lon,
            source_lat,
            target_lon,
            target_lat,
        )
        affected = distance_to_event <= event.influence_radius_km
        if affected:
            item["danger_type"] = event.danger_type
        else:
            item["danger_type"] = base_congestion_type(item)
        mapped_edges.append(item)
        if affected:
            mapping_rows.append(
                {
                    "edge_id": item["edge_id"],
                    "from": item["from"],
                    "to": item["to"],
                    "road_name": item.get("road_name", ""),
                    "scenario": event.scenario,
                    "event_id": event.event_id,
                    "event_name": event.name,
                    "danger_type": event.danger_type,
                    "distance_to_event_km": round(distance_to_event, 3),
                    "influence_radius_km": event.influence_radius_km,
                    "mapping_method": "edge segment intersects historical disaster influence buffer",
                    "source_url": event.source_url,
                }
            )

    return mapped_edges, mapping_rows


def write_event_files() -> None:
    rows = [asdict(event) for event in EVENTS]
    fieldnames = list(rows[0].keys())
    write_csv(HISTORICAL_DIR / "disaster_events.csv", rows, fieldnames)
    (HISTORICAL_DIR / "README.md").write_text(
        "\n".join(
            [
                "# Historical disaster data",
                "",
                "This folder records the public historical disaster events used by the project.",
                "The coordinates are used as representative impact-zone centers for a course-level",
                "spatial overlay experiment. They are not claimed to be official road-closure",
                "or street-level damage records.",
                "",
                "Workflow:",
                "1. AMap provides real route geometry, road names, distance, and traffic status.",
                "2. Public historical disaster records provide event type, date, broad location, and evidence.",
                "3. The project creates an influence buffer around the event impact center.",
                "4. Road segments intersecting the buffer are marked as flood or collapse risk.",
            ]
        ),
        encoding="utf-8",
    )


def write_dataset(name: str, event: DisasterEvent, edges: list[dict[str, str]], mapping_rows: list[dict[str, object]]) -> None:
    out_dir = ROOT / "data" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BASE_DIR / "nodes.csv", out_dir / "nodes.csv")

    with (BASE_DIR / "scenario.json").open("r", encoding="utf-8") as f:
        scenario = json.load(f)
    scenario.update(
        {
            "scenario_name": f"{event.scenario.title()} rescue route planning with AMap and historical disaster data",
            "disaster_type": event.scenario,
            "historical_event_id": event.event_id,
            "historical_event_name": event.name,
            "historical_event_date": event.event_date,
            "historical_event_source": event.source_url,
            "description": (
                "Road geometry comes from AMap Web Service. Disaster risk is generated by "
                "overlaying real historical disaster records with road segments using an "
                "influence-buffer mapping method."
            ),
        }
    )
    with (out_dir / "scenario.json").open("w", encoding="utf-8") as f:
        json.dump(scenario, f, ensure_ascii=False, indent=2)

    write_csv(out_dir / "disaster_events.csv", [asdict(event)], list(asdict(event).keys()))
    write_csv(out_dir / "road_disaster_mapping.csv", mapping_rows, list(mapping_rows[0].keys()) if mapping_rows else [
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
    ])
    write_csv(out_dir / "edges.csv", edges, list(edges[0].keys()))


def main() -> None:
    base_edges, _ = read_csv(BASE_DIR / "edges.csv")
    nodes = load_nodes()
    write_event_files()

    scenario_names = {
        "earthquake": "amap_earthquake",
        "flood": "amap_flood",
    }
    for event in EVENTS:
        mapped_edges, mapping_rows = map_edges_for_scenario(base_edges, nodes, event)
        write_dataset(scenario_names[event.scenario], event, mapped_edges, mapping_rows)
        print(
            f"Created data/{scenario_names[event.scenario]} with "
            f"{len(mapping_rows)} disaster-affected road segments."
        )


if __name__ == "__main__":
    main()
