from __future__ import annotations

import csv
import json
import math
import os
import shutil
import urllib.parse
import urllib.request
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SIZE = (1024, 768)
SCALE = 2
IMAGE_SIZE = (SIZE[0] * SCALE, SIZE[1] * SCALE)
STATIC_MAP_URL = "https://restapi.amap.com/v3/staticmap"


@dataclass(frozen=True)
class Node:
    node_id: str
    lon: float
    lat: float
    label: str
    node_type: str


@dataclass(frozen=True)
class Edge:
    edge_id: str
    source: str
    target: str
    danger_type: str
    polyline: list[tuple[float, float]]


@dataclass(frozen=True)
class DisasterEvent:
    name: str
    lon: float
    lat: float
    radius_km: float
    danger_type: str


def read_nodes(path: Path) -> dict[str, Node]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return {
            row["node_id"]: Node(
                node_id=row["node_id"],
                lon=float(row["x"]),
                lat=float(row["y"]),
                label=row["label"],
                node_type=row["type"],
            )
            for row in csv.DictReader(f)
        }


def read_edges(path: Path) -> list[Edge]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [
            Edge(
                edge_id=row["edge_id"],
                source=row["from"],
                target=row["to"],
                danger_type=row.get("danger_type", "normal"),
                polyline=parse_polyline(row.get("polyline", "")),
            )
            for row in csv.DictReader(f)
        ]


def read_events(path: Path) -> list[DisasterEvent]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [
            DisasterEvent(
                name=row["name"],
                lon=float(row["longitude"]),
                lat=float(row["latitude"]),
                radius_km=float(row["influence_radius_km"]),
                danger_type=row["danger_type"],
            )
            for row in csv.DictReader(f)
        ]


def read_results(path: Path) -> dict[str, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    paths: dict[str, list[str]] = {}
    for item in data:
        if item.get("algorithm") != "Dijkstra":
            continue
        mode = item.get("mode")
        if mode in {"distance", "safe"}:
            paths[mode] = item.get("path", [])
    return paths


def parse_polyline(value: str) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for item in value.split(";"):
        if not item:
            continue
        try:
            lon_text, lat_text = item.split(",", 1)
            points.append((float(lon_text), float(lat_text)))
        except ValueError:
            continue
    return points


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / ("msyhbd.ttc" if bold else "msyh.ttc"),
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / ("simhei.ttf" if bold else "msyh.ttc"),
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf",
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
            except OSError:
                continue
    return ImageFont.load_default()


def mercator_world(lon: float, lat: float, zoom: int) -> tuple[float, float]:
    lat = max(min(lat, 85.05112878), -85.05112878)
    sin_lat = math.sin(math.radians(lat))
    world = 256 * (2**zoom)
    x = (lon + 180.0) / 360.0 * world
    y = (0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * world
    return x, y


def bbox_for(nodes: dict[str, Node], paths: dict[str, list[str]], events: list[DisasterEvent]) -> tuple[float, float, float, float]:
    points: list[tuple[float, float]] = []
    for path in paths.values():
        for node_id in path:
            if node_id in nodes:
                node = nodes[node_id]
                points.append((node.lon, node.lat))
    if not points:
        points = [(node.lon, node.lat) for node in nodes.values()]
    for event in events:
        lat_delta = event.radius_km / 111.32
        lon_delta = event.radius_km / (111.32 * max(math.cos(math.radians(event.lat)), 0.2))
        points.extend(
            [
                (event.lon - lon_delta, event.lat - lat_delta),
                (event.lon + lon_delta, event.lat + lat_delta),
            ]
        )
    min_lon = min(point[0] for point in points)
    max_lon = max(point[0] for point in points)
    min_lat = min(point[1] for point in points)
    max_lat = max(point[1] for point in points)
    pad_lon = max((max_lon - min_lon) * 0.12, 0.01)
    pad_lat = max((max_lat - min_lat) * 0.18, 0.01)
    return min_lon - pad_lon, min_lat - pad_lat, max_lon + pad_lon, max_lat + pad_lat


def choose_zoom(bbox: tuple[float, float, float, float]) -> int:
    min_lon, min_lat, max_lon, max_lat = bbox
    for zoom in range(17, 5, -1):
        x1, y1 = mercator_world(min_lon, max_lat, zoom)
        x2, y2 = mercator_world(max_lon, min_lat, zoom)
        if abs(x2 - x1) <= SIZE[0] * 0.82 and abs(y2 - y1) <= SIZE[1] * 0.74:
            return zoom
    return 6


def fetch_static_map(key: str, center: tuple[float, float], zoom: int) -> Image.Image:
    params = {
        "location": f"{center[0]:.6f},{center[1]:.6f}",
        "zoom": str(zoom),
        "size": f"{SIZE[0]}*{SIZE[1]}",
        "scale": str(SCALE),
        "traffic": "1",
        "key": key,
    }
    url = STATIC_MAP_URL + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=20) as response:
        data = response.read()
    if data.lstrip().startswith(b"{"):
        message = data.decode("utf-8", errors="replace")
        raise RuntimeError(f"AMap static map request failed: {message}")
    image = Image.open(BytesIO(data))
    return image.convert("RGBA")


def make_projector(center: tuple[float, float], zoom: int):
    center_x, center_y = mercator_world(center[0], center[1], zoom)

    def project(lon: float, lat: float) -> tuple[int, int]:
        x, y = mercator_world(lon, lat, zoom)
        return (
            int(round((x - center_x) * SCALE + IMAGE_SIZE[0] / 2)),
            int(round((y - center_y) * SCALE + IMAGE_SIZE[1] / 2)),
        )

    return project


def draw_points(
    draw: ImageDraw.ImageDraw,
    points: Iterable[tuple[float, float]],
    project,
    color: str,
    width: int,
    casing: str | None = None,
) -> None:
    screen_points = [project(lon, lat) for lon, lat in points]
    if len(screen_points) < 2:
        return
    if casing:
        draw.line(screen_points, fill=casing, width=width + 8, joint="curve")
    draw.line(screen_points, fill=color, width=width, joint="curve")


def path_edges(path: list[str]) -> set[frozenset[str]]:
    return {frozenset((a, b)) for a, b in zip(path, path[1:])}


def edge_lookup(edges: list[Edge]) -> dict[frozenset[str], Edge]:
    return {frozenset((edge.source, edge.target)): edge for edge in edges}


def route_points(nodes: dict[str, Node], edges_by_nodes: dict[frozenset[str], Edge], path: list[str]) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for source_id, target_id in zip(path, path[1:]):
        source = nodes[source_id]
        target = nodes[target_id]
        edge = edges_by_nodes.get(frozenset((source_id, target_id)))
        segment = edge.polyline if edge and edge.polyline else [(source.lon, source.lat), (target.lon, target.lat)]
        if edge and edge.source == target_id and edge.target == source_id:
            segment = list(reversed(segment))
        if points and segment:
            segment = segment[1:]
        points.extend(segment)
    return points


def draw_disaster_zones(image: Image.Image, events: list[DisasterEvent], project) -> None:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = load_font(24, bold=True)
    for event in events:
        cx, cy = project(event.lon, event.lat)
        lon_delta = event.radius_km / (111.32 * max(math.cos(math.radians(event.lat)), 0.2))
        rx, _ = project(event.lon + lon_delta, event.lat)
        radius = max(36, abs(rx - cx))
        if event.danger_type == "collapse":
            fill = (214, 69, 69, 66)
            outline = (214, 69, 69, 220)
            label = "历史地震影响区"
        else:
            fill = (31, 94, 255, 58)
            outline = (31, 94, 255, 220)
            label = "历史洪水影响区"
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=fill, outline=outline, width=5)
        draw.text((cx + 18, cy - radius - 34), label, fill=outline, font=font)
    image.alpha_composite(overlay)


def draw_markers(image: Image.Image, nodes: dict[str, Node], paths: dict[str, list[str]], project) -> None:
    draw = ImageDraw.Draw(image)
    font = load_font(25, bold=True)
    small = load_font(21)
    any_path = paths.get("safe") or paths.get("distance") or []
    if not any_path:
        return
    markers = [
        (any_path[0], "起点\n清华大学", "#178A4A"),
        (any_path[-1], "终点\n北京朝阳站", "#D64545"),
    ]
    for node_id, label, color in markers:
        node = nodes[node_id]
        x, y = project(node.lon, node.lat)
        draw.ellipse((x - 22, y - 22, x + 22, y + 22), fill=color, outline="#FFFFFF", width=5)
        draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill="#FFFFFF")
        draw.multiline_text((x + 32, y - 28), label, fill="#102033", font=font if "\n" not in label else small, spacing=3)


def draw_legend(image: Image.Image, scenario_label: str) -> None:
    draw = ImageDraw.Draw(image)
    title_font = load_font(32, bold=True)
    font = load_font(23)
    box = (42, 42, 560, 255)
    draw.rounded_rectangle(box, radius=18, fill=(255, 255, 255, 230), outline="#D9E2EC", width=2)
    draw.text((68, 62), f"救援路径规划结果（{scenario_label}）", fill="#102033", font=title_font)
    rows = [
        ("#1F5EFF", "普通最短路径"),
        ("#178A4A", "安全路径"),
        ("#D64545" if scenario_label == "地震场景" else "#1F5EFF", "历史灾害影响区"),
        ("#E58B25", "危险/拥堵路段"),
    ]
    y = 116
    for color, label in rows:
        draw.line((75, y + 14, 142, y + 14), fill=color, width=10)
        draw.text((160, y), label, fill="#102033", font=font)
        y += 34


def render_scene(data_dir: Path, output_dir: Path, scenario_label: str) -> Path:
    out_path = output_dir / "route_map_amap_static.png"
    fallback = output_dir / "route_map_context.png"
    output_dir.mkdir(parents=True, exist_ok=True)
    nodes = read_nodes(data_dir / "nodes.csv")
    edges = read_edges(data_dir / "edges.csv")
    events = read_events(data_dir / "disaster_events.csv")
    paths = read_results(output_dir / "path_results.json")

    key = os.environ.get("AMAP_KEY")
    if not key:
        if fallback.exists():
            shutil.copyfile(fallback, out_path)
        print(f"[skip] AMAP_KEY is not set; kept fallback image for {scenario_label}: {out_path}")
        return out_path

    bbox = bbox_for(nodes, paths, events)
    center = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
    zoom = choose_zoom(bbox)
    image = fetch_static_map(key, center, zoom)
    project = make_projector(center, zoom)

    draw_disaster_zones(image, events, project)
    draw = ImageDraw.Draw(image)

    shortest_edges = path_edges(paths.get("distance", []))
    safe_edges = path_edges(paths.get("safe", []))
    edges_by_nodes = edge_lookup(edges)
    for edge in edges:
        if edge.danger_type == "normal":
            continue
        key_pair = frozenset((edge.source, edge.target))
        if key_pair in shortest_edges or key_pair in safe_edges:
            continue
        color = "#D64545" if edge.danger_type == "collapse" else "#E58B25"
        if edge.danger_type == "flood":
            color = "#1F5EFF"
        if edge.polyline:
            draw_points(draw, edge.polyline, project, color, 8)
        else:
            source = nodes[edge.source]
            target = nodes[edge.target]
            draw.line((project(source.lon, source.lat), project(target.lon, target.lat)), fill=color, width=8)

    draw_points(draw, route_points(nodes, edges_by_nodes, paths.get("distance", [])), project, "#1F5EFF", 14, "#FFFFFF")
    draw_points(draw, route_points(nodes, edges_by_nodes, paths.get("safe", [])), project, "#178A4A", 16, "#FFFFFF")
    draw_markers(image, nodes, paths, project)
    draw_legend(image, scenario_label)

    image.convert("RGB").save(out_path, quality=95)
    print(f"[ok] {scenario_label}: {out_path} (zoom={zoom}, center={center[0]:.6f},{center[1]:.6f})")
    return out_path


def main() -> None:
    scenes = [
        ("地震场景", ROOT / "data" / "amap_earthquake", ROOT / "outputs" / "amap_earthquake"),
        ("洪水场景", ROOT / "data" / "amap_flood", ROOT / "outputs" / "amap_flood"),
    ]
    for label, data_dir, output_dir in scenes:
        render_scene(data_dir, output_dir, label)


if __name__ == "__main__":
    main()
