from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
WIDTH = 1800
HEIGHT = 1120
LEFT = 90
RIGHT = 440
TOP = 120
BOTTOM = 105


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
    distance: float
    danger_type: str
    congestion: float
    road_name: str
    variant: str
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


def read_edges(path: Path) -> list[Edge]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [
            Edge(
                edge_id=row["edge_id"],
                source=row["from"],
                target=row["to"],
                distance=float(row["distance"]),
                danger_type=row.get("danger_type", "normal"),
                congestion=float(row.get("congestion", 0) or 0),
                road_name=row.get("road_name", ""),
                variant=row.get("variant", ""),
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


def read_results(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["mode"]: item for item in data if item.get("algorithm") == "Dijkstra"}


def read_scenario(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts") / ("msyhbd.ttc" if bold else "msyh.ttc"),
        Path("C:/Windows/Fonts") / ("simhei.ttf" if bold else "simsun.ttc"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
            except OSError:
                continue
    return ImageFont.load_default()


def geo_to_km(lon: float, lat: float, center_lon: float, center_lat: float) -> tuple[float, float]:
    x = (lon - center_lon) * 111.32 * math.cos(math.radians(center_lat))
    y = (lat - center_lat) * 111.32
    return x, y


def collect_geo_points(nodes: dict[str, Node], edges: list[Edge], events: list[DisasterEvent]) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for edge in edges:
        if edge.polyline:
            points.extend(edge.polyline)
        else:
            source = nodes[edge.source]
            target = nodes[edge.target]
            points.extend([(source.lon, source.lat), (target.lon, target.lat)])
    for event in events:
        lat_delta = event.radius_km / 111.32
        lon_delta = event.radius_km / (111.32 * max(math.cos(math.radians(event.lat)), 0.2))
        points.extend(
            [
                (event.lon - lon_delta, event.lat - lat_delta),
                (event.lon + lon_delta, event.lat + lat_delta),
            ]
        )
    return points


def expand_geo_bounds(points: list[tuple[float, float]], pad_km: float) -> list[tuple[float, float]]:
    if not points:
        return points
    min_lon = min(lon for lon, _ in points)
    max_lon = max(lon for lon, _ in points)
    min_lat = min(lat for _, lat in points)
    max_lat = max(lat for _, lat in points)
    center_lat = (min_lat + max_lat) / 2.0
    lat_delta = pad_km / 111.32
    lon_delta = pad_km / (111.32 * max(math.cos(math.radians(center_lat)), 0.2))
    return [
        (min_lon - lon_delta, min_lat - lat_delta),
        (max_lon + lon_delta, max_lat + lat_delta),
    ]


def disaster_bounds(events: list[DisasterEvent], pad_factor: float = 1.05) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for event in events:
        radius = max(event.radius_km * pad_factor, 0.05)
        lat_delta = radius / 111.32
        lon_delta = radius / (111.32 * max(math.cos(math.radians(event.lat)), 0.2))
        points.extend(
            [
                (event.lon - lon_delta, event.lat - lat_delta),
                (event.lon + lon_delta, event.lat + lat_delta),
            ]
        )
    return points


def build_projector(
    nodes: dict[str, Node],
    edges: list[Edge],
    events: list[DisasterEvent],
    zoom: float = 1.0,
    focus_points: list[tuple[float, float]] | None = None,
):
    geo_points = collect_geo_points(nodes, edges, events)
    bounds_points = focus_points if focus_points else geo_points
    center_lon = sum(lon for lon, _ in bounds_points) / len(bounds_points)
    center_lat = sum(lat for _, lat in bounds_points) / len(bounds_points)
    km_points = [geo_to_km(lon, lat, center_lon, center_lat) for lon, lat in bounds_points]
    min_x = min(x for x, _ in km_points)
    max_x = max(x for x, _ in km_points)
    min_y = min(y for _, y in km_points)
    max_y = max(y for _, y in km_points)
    pad_x = max((max_x - min_x) * 0.08, 1.0)
    pad_y = max((max_y - min_y) * 0.08, 1.0)
    min_x -= pad_x
    max_x += pad_x
    min_y -= pad_y
    max_y += pad_y
    map_width = WIDTH - LEFT - RIGHT
    map_height = HEIGHT - TOP - BOTTOM
    scale = min(map_width / max(max_x - min_x, 0.001), map_height / max(max_y - min_y, 0.001)) * zoom
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    screen_center_x = LEFT + map_width / 2.0
    screen_center_y = TOP + map_height / 2.0

    def project(lon: float, lat: float) -> tuple[int, int]:
        x, y = geo_to_km(lon, lat, center_lon, center_lat)
        sx = screen_center_x + (x - center_x) * scale
        sy = screen_center_y - (y - center_y) * scale
        return int(round(sx)), int(round(sy))

    return project, scale


def edge_lookup(edges: list[Edge]) -> dict[frozenset[str], Edge]:
    return {frozenset((edge.source, edge.target)): edge for edge in edges}


def path_edge_keys(path: list[str]) -> set[frozenset[str]]:
    return {frozenset((a, b)) for a, b in zip(path, path[1:])}


def route_points(nodes: dict[str, Node], lookup: dict[frozenset[str], Edge], path: list[str]) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for source_id, target_id in zip(path, path[1:]):
        source = nodes[source_id]
        target = nodes[target_id]
        edge = lookup.get(frozenset((source_id, target_id)))
        segment = edge.polyline if edge and edge.polyline else [(source.lon, source.lat), (target.lon, target.lat)]
        if edge and edge.source == target_id and edge.target == source_id:
            segment = list(reversed(segment))
        if points and segment:
            segment = segment[1:]
        points.extend(segment)
    return points


def stable_bucket(value: str, modulus: int) -> int:
    total = 0
    for index, char in enumerate(value):
        total += (index + 1) * ord(char)
    return total % max(1, modulus)


def edge_rank(edge: Edge) -> int:
    variant = edge.variant.lower()
    road_name = edge.road_name.lower()
    text = f"{variant} {road_name}"
    if "motorway" in text or "trunk" in text:
        return 5
    if "primary" in text:
        return 4
    if "secondary" in text:
        return 3
    if "tertiary" in text:
        return 2
    if "connector" in text:
        return 2
    return 1


def should_draw_background_edge(edge: Edge, edge_count: int, route_keys: set[frozenset[str]]) -> bool:
    if frozenset((edge.source, edge.target)) in route_keys:
        return False
    if edge.variant == "connector":
        return True

    rank = edge_rank(edge)
    if edge_count > 250_000:
        keep_by_rank = {5: 1, 4: 2, 3: 9, 2: 18, 1: 36}
    elif edge_count > 70_000:
        keep_by_rank = {5: 1, 4: 1, 3: 4, 2: 9, 1: 18}
    elif edge_count > 25_000:
        keep_by_rank = {5: 1, 4: 1, 3: 2, 2: 5, 1: 10}
    else:
        keep_by_rank = {5: 1, 4: 1, 3: 1, 2: 3, 1: 6}
    return stable_bucket(edge.edge_id, keep_by_rank.get(rank, 12)) == 0


def should_draw_danger_edge(edge: Edge, edge_count: int, route_keys: set[frozenset[str]]) -> bool:
    if frozenset((edge.source, edge.target)) in route_keys:
        return False
    if edge_count <= 25_000:
        return True
    if edge.danger_type in {"fire", "flood"}:
        return stable_bucket(edge.edge_id, 2) == 0
    if edge_count > 250_000:
        return stable_bucket(edge.edge_id, 7) == 0
    return stable_bucket(edge.edge_id, 3) == 0


def draw_geo_line(
    draw: ImageDraw.ImageDraw,
    points: Iterable[tuple[float, float]],
    project,
    fill: str | tuple[int, int, int, int],
    width: int,
    casing: str | tuple[int, int, int, int] | None = None,
    smooth: int = 1,
    image: Image.Image | None = None,
    antialias: bool = False,
    casing_extra: int = 8,
) -> None:
    screen = [project(lon, lat) for lon, lat in points]
    if len(screen) < 2:
        return
    if smooth > 0:
        screen = smooth_screen_points(screen, iterations=smooth)
    if antialias and image is not None:
        draw_antialiased_line(image, screen, fill, width, casing, casing_extra)
        return
    if casing:
        draw.line(screen, fill=casing, width=width + casing_extra, joint="curve")
    draw.line(screen, fill=fill, width=width, joint="curve")


def draw_antialiased_line(
    image: Image.Image,
    points: list[tuple[float, float]],
    fill: str | tuple[int, int, int, int],
    width: int,
    casing: str | tuple[int, int, int, int] | None = None,
    casing_extra: int = 8,
) -> None:
    factor = 3
    large_size = (image.size[0] * factor, image.size[1] * factor)
    layer = Image.new("RGBA", large_size, (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    scaled = [(x * factor, y * factor) for x, y in points]
    if casing:
        layer_draw.line(scaled, fill=casing, width=(width + casing_extra) * factor, joint="curve")
        draw_round_caps(layer_draw, scaled, casing, (width + casing_extra) * factor)
    layer_draw.line(scaled, fill=fill, width=width * factor, joint="curve")
    draw_round_caps(layer_draw, scaled, fill, width * factor)
    layer = layer.resize(image.size, Image.Resampling.LANCZOS)
    image.alpha_composite(layer)


def draw_antialiased_lines(
    image: Image.Image,
    lines: list[tuple[list[tuple[float, float]], str | tuple[int, int, int, int], int]],
) -> None:
    if not lines:
        return
    factor = 3
    large_size = (image.size[0] * factor, image.size[1] * factor)
    layer = Image.new("RGBA", large_size, (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    for points, fill, width in lines:
        if len(points) < 2:
            continue
        scaled = [(x * factor, y * factor) for x, y in points]
        layer_draw.line(scaled, fill=fill, width=width * factor, joint="curve")
        draw_round_caps(layer_draw, scaled, fill, width * factor)
    layer = layer.resize(image.size, Image.Resampling.LANCZOS)
    image.alpha_composite(layer)


def bridge_nearby_line_endpoints(
    lines: list[tuple[list[tuple[float, float]], str | tuple[int, int, int, int], int]],
    max_gap: float = 24.0,
) -> list[tuple[list[tuple[float, float]], str | tuple[int, int, int, int], int]]:
    bridged = list(lines)
    endpoints: list[tuple[int, int, tuple[float, float], str | tuple[int, int, int, int], int]] = []
    for index, (points, color, width) in enumerate(lines):
        if len(points) < 2:
            continue
        endpoints.append((index, 0, points[0], color, width))
        endpoints.append((index, 1, points[-1], color, width))
    used: set[tuple[int, int]] = set()
    for i, (line_i, end_i, point_i, color_i, width_i) in enumerate(endpoints):
        if (line_i, end_i) in used:
            continue
        best: tuple[float, int, int, tuple[float, float], int] | None = None
        for line_j, end_j, point_j, color_j, width_j in endpoints[i + 1 :]:
            if line_i == line_j or color_i != color_j or (line_j, end_j) in used:
                continue
            gap = math.hypot(point_i[0] - point_j[0], point_i[1] - point_j[1])
            if 2.5 < gap <= max_gap and (best is None or gap < best[0]):
                best = (gap, line_j, end_j, point_j, width_j)
        if best is None:
            continue
        _, line_j, end_j, point_j, width_j = best
        bridged.append(([point_i, point_j], color_i, min(width_i, width_j)))
        used.add((line_i, end_i))
        used.add((line_j, end_j))
    return bridged


def draw_round_caps(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[float, float]],
    fill: str | tuple[int, int, int, int],
    width: int,
) -> None:
    radius = width / 2
    for x, y in (points[0], points[-1]):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def smooth_screen_points(points: list[tuple[int, int]], iterations: int = 1) -> list[tuple[float, float]]:
    if len(points) < 3:
        return points
    tolerance = 5.5 if iterations >= 4 else 2.0
    working = simplify_screen_points([(float(x), float(y)) for x, y in points], tolerance=tolerance)
    for _ in range(iterations):
        next_points: list[tuple[float, float]] = [working[0]]
        for p0, p1 in zip(working, working[1:]):
            q = (0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1])
            r = (0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1])
            next_points.extend([q, r])
        next_points.append(working[-1])
        working = next_points
    return working


def simplify_screen_points(points: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return points
    keep = [False] * len(points)
    keep[0] = True
    keep[-1] = True

    def mark(start: int, end: int) -> None:
        if end <= start + 1:
            return
        max_distance = -1.0
        index = start
        for i in range(start + 1, end):
            distance = point_line_distance(points[i], points[start], points[end])
            if distance > max_distance:
                max_distance = distance
                index = i
        if max_distance > tolerance:
            keep[index] = True
            mark(start, index)
            mark(index, end)

    mark(0, len(points) - 1)
    simplified = [point for point, should_keep in zip(points, keep) if should_keep]
    return simplified if len(simplified) >= 2 else points


def point_line_distance(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> float:
    px, py = point
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    projection = (x1 + t * dx, y1 + t * dy)
    return math.hypot(px - projection[0], py - projection[1])


def catmull_rom_spline(points: list[tuple[float, float]], samples: int = 8) -> list[tuple[float, float]]:
    if len(points) < 4:
        return points
    curve: list[tuple[float, float]] = [points[0]]
    extended = [points[0], *points, points[-1]]
    for i in range(1, len(extended) - 2):
        p0, p1, p2, p3 = extended[i - 1], extended[i], extended[i + 1], extended[i + 2]
        for step in range(1, samples + 1):
            t = step / samples
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * (
                (2 * p1[0])
                + (-p0[0] + p2[0]) * t
                + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                (2 * p1[1])
                + (-p0[1] + p2[1]) * t
                + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
            )
            curve.append((x, y))
    curve.append(points[-1])
    return curve


def draw_disaster_zones(image: Image.Image, events: list[DisasterEvent], project, scale: float) -> None:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = load_font(25, bold=True)
    for event in events:
        cx, cy = project(event.lon, event.lat)
        radius = max(34, int(round(event.radius_km * scale)))
        if event.danger_type == "collapse":
            fill = (214, 69, 69, 58)
            outline = (214, 69, 69, 210)
            label = "历史地震影响区"
        elif event.danger_type == "fire":
            fill = (245, 124, 32, 58)
            outline = (230, 92, 24, 220)
            label = "历史火灾影响区"
        else:
            fill = (31, 94, 255, 52)
            outline = (31, 94, 255, 210)
            label = "历史洪水影响区"
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=fill, outline=outline, width=4)
        draw.text((cx + 16, cy - radius - 34), label, fill=outline, font=font)
    image.alpha_composite(overlay)


def draw_background_context(draw: ImageDraw.ImageDraw) -> None:
    grid_color = "#E7EDF3"
    for i in range(7):
        x = LEFT + i * (WIDTH - LEFT - RIGHT) / 6
        draw.line((x, TOP + 20, x, HEIGHT - BOTTOM), fill=grid_color, width=1)
    for i in range(5):
        y = TOP + 20 + i * (HEIGHT - TOP - BOTTOM - 20) / 4
        draw.line((LEFT, y, WIDTH - RIGHT - 20, y), fill=grid_color, width=1)


def expand_box(box: tuple[int, int, int, int], padding: int) -> tuple[int, int, int, int]:
    return (box[0] - padding, box[1] - padding, box[2] + padding, box[3] + padding)


def boxes_overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def box_overlaps_any(box: tuple[int, int, int, int], boxes: list[tuple[int, int, int, int]]) -> bool:
    return any(boxes_overlap(box, other) for other in boxes)


def box_inside_map(box: tuple[int, int, int, int]) -> bool:
    return box[0] >= LEFT and box[1] >= TOP and box[2] <= WIDTH - RIGHT - 20 and box[3] <= HEIGHT - BOTTOM


def box_too_close_to_path(
    box: tuple[int, int, int, int],
    path_points: list[tuple[float, float]] | None,
    threshold: float,
) -> bool:
    if not path_points:
        return False
    points = [
        ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2),
        (box[0], box[1]),
        (box[2], box[1]),
        (box[0], box[3]),
        (box[2], box[3]),
    ]
    sample_step = max(1, len(path_points) // 260)
    for px, py in points:
        for ax, ay in path_points[::sample_step]:
            if math.hypot(px - ax, py - ay) <= threshold:
                return True
    return False


def draw_context_labels(
    draw: ImageDraw.ImageDraw,
    nodes: dict[str, Node],
    project,
    scenario_label: str,
    avoid_points: list[tuple[float, float]] | None = None,
) -> None:
    if scenario_label not in {"地震场景", "洪水场景"}:
        return
    font = load_font(19)
    labels = [
        ("N001", "清华大学周边", 28, -60),
        ("N034", "西直门桥 / 北展片区", -105, -45),
        ("N035", "北二环沿线", -10, -56),
        ("N040", "四元桥片区", 18, -52),
        ("N054", "望京 / 望和桥片区", -80, -52),
        ("N002", "北京朝阳站周边", -145, 38),
    ]
    used: set[str] = set()
    placed_boxes: list[tuple[int, int, int, int]] = []
    for node_id, label, dx, dy in labels:
        if node_id not in nodes or label in used:
            continue
        node = nodes[node_id]
        x, y = project(node.lon, node.lat)
        if too_close_to_path((x, y), avoid_points, threshold=34):
            continue
        bbox = draw.textbbox((x + dx, y + dy), label, font=font)
        padded = expand_box((bbox[0] - 8, bbox[1] - 5, bbox[2] + 8, bbox[3] + 5), 10)
        if not box_inside_map(padded) or box_overlaps_any(padded, placed_boxes):
            continue
        draw.rounded_rectangle(
            (bbox[0] - 8, bbox[1] - 5, bbox[2] + 8, bbox[3] + 5),
            radius=8,
            fill="#F8FAFC",
            outline="#E2E8F0",
            width=1,
        )
        draw.text((x + dx, y + dy), label, fill="#94A3B8", font=font)
        placed_boxes.append(padded)
        used.add(label)


def draw_road_labels(
    draw: ImageDraw.ImageDraw,
    edges: list[Edge],
    project,
    scenario_label: str,
    avoid_points: list[tuple[float, float]] | None = None,
    event_points: list[tuple[float, float]] | None = None,
) -> None:
    font = load_font(15)
    seen: set[str] = set()
    placed_boxes: list[tuple[int, int, int, int]] = []
    preferred_names: list[str] = []
    max_labels = 7
    min_distance = 0.85
    if "上海火灾" in scenario_label:
        preferred_names = [
            "武宁路桥",
            "长寿路",
            "胶州路",
            "武宁路",
            "江宁路",
            "北京西路",
            "陕西北路",
            "谈家渡路",
            "普雄路",
            "曹杨路",
            "愚园路",
            "康定路",
        ]
        max_labels = 10
        min_distance = 0.12
        label_offsets = [
            (12, -30),
            (12, 22),
            (-88, -30),
            (-88, 22),
            (24, -48),
            (-108, -48),
            (24, 42),
            (-108, 42),
            (38, -66),
            (-122, -66),
            (38, 58),
            (-122, 58),
        ]
        route_clearance = 30
        event_clearance = 18
    else:
        label_offsets = [
            (18, -58),
            (18, 34),
            (-132, -58),
            (-132, 34),
            (34, -86),
            (-148, -86),
            (34, 62),
            (-148, 62),
            (58, -118),
            (-172, -118),
            (58, 94),
            (-172, 94),
        ]
        route_clearance = 48
        event_clearance = 26

    def label_rank(edge: Edge) -> tuple[int, float]:
        if edge.road_name in preferred_names:
            return preferred_names.index(edge.road_name), -edge.distance
        return len(preferred_names) + (0 if edge.danger_type != "normal" else 1), -edge.distance

    candidates = sorted(
        [
            edge
            for edge in edges
            if edge.road_name
            and not edge.road_name.startswith("向")
            and edge.distance >= min_distance
            and edge.polyline
        ],
        key=label_rank,
    )
    for edge in candidates:
        if edge.road_name in seen or len(seen) >= max_labels:
            continue
        point = edge.polyline[len(edge.polyline) // 2]
        x, y = project(point[0], point[1])
        label = edge.road_name[:10]
        placed: tuple[int, int, int, int] | None = None
        text_xy = (0, 0)
        for dx, dy in label_offsets:
            bbox = draw.textbbox((x + dx, y + dy), label, font=font)
            padded = expand_box((bbox[0] - 5, bbox[1] - 3, bbox[2] + 5, bbox[3] + 3), 8)
            if not box_inside_map(padded):
                continue
            if box_overlaps_any(padded, placed_boxes):
                continue
            if box_too_close_to_path(padded, avoid_points, threshold=route_clearance):
                continue
            if box_too_close_to_path(padded, event_points, threshold=event_clearance):
                continue
            placed = padded
            text_xy = (x + dx, y + dy)
            break
        if placed is None:
            continue
        bbox = draw.textbbox(text_xy, label, font=font)
        label_center = ((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2)
        draw.line((x, y, label_center[0], label_center[1]), fill="#C6D1DD", width=1)
        draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill="#A8B6C8")
        draw.rounded_rectangle(
            (bbox[0] - 5, bbox[1] - 3, bbox[2] + 5, bbox[3] + 3),
            radius=6,
            fill="#F9FBFD",
            outline="#E2E8F0",
            width=1,
        )
        draw.text(text_xy, label, fill="#9AA8B8", font=font)
        placed_boxes.append(placed)
        seen.add(edge.road_name)


def too_close_to_path(
    point: tuple[float, float],
    path_points: list[tuple[float, float]] | None,
    threshold: float,
) -> bool:
    if not path_points:
        return False
    px, py = point
    for ax, ay in path_points[:: max(1, len(path_points) // 220)]:
        if math.hypot(px - ax, py - ay) <= threshold:
            return True
    return False


def projected_route_points(
    nodes: dict[str, Node],
    lookup: dict[frozenset[str], Edge],
    path: list[str],
    project,
) -> list[tuple[float, float]]:
    return [project(lon, lat) for lon, lat in route_points(nodes, lookup, path)]


def multiline(draw: ImageDraw.ImageDraw, xy: tuple[int, int], lines: list[str], font, fill: str, spacing: int = 10) -> None:
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + spacing


def draw_side_panel(draw: ImageDraw.ImageDraw, scenario_label: str, results: dict[str, dict]) -> None:
    x = WIDTH - RIGHT + 35
    panel = (WIDTH - RIGHT + 20, TOP, WIDTH - 65, HEIGHT - BOTTOM)
    draw.rounded_rectangle(panel, radius=18, fill="#FFFFFF", outline="#D9E2EC", width=2)
    title_font = load_font(31, bold=True)
    font = load_font(23)
    small = load_font(20)
    draw.text((x, TOP + 30), "图例与结果", font=title_font, fill="#102033")

    disaster_color = "#D64545" if "地震" in scenario_label else "#E65C18" if "火灾" in scenario_label else "#1F5EFF"
    rows = [
        ("#E4EAF2", "周边背景道路"),
        ("#7F91AA", "其他候选路线"),
        ("#1F5EFF", "普通最短路径"),
        ("#178A4A", "安全路径"),
        (disaster_color, "历史灾害影响区"),
        ("#E58B25", "危险/拥堵路段"),
    ]
    y = TOP + 88
    for color, label in rows:
        draw.line((x, y + 14, x + 72, y + 14), fill=color, width=10)
        draw.text((x + 88, y), label, font=small, fill="#102033")
        y += 43

    distance = results.get("distance", {})
    safe = results.get("safe", {})
    y += 18
    draw.text((x, y), "普通最短路径", font=font, fill="#1F5EFF")
    y += 38
    multiline(
        draw,
        (x, y),
        [
            f"距离：{distance.get('total_distance', '-')} km",
            f"危险类型：{', '.join(distance.get('danger_types', [])) or '无'}",
        ],
        small,
        "#334155",
        8,
    )
    y += 95
    draw.text((x, y), "安全路径", font=font, fill="#178A4A")
    y += 38
    multiline(
        draw,
        (x, y),
        [
            f"距离：{safe.get('total_distance', '-')} km",
            f"综合代价：{safe.get('total_cost', '-')}",
            f"危险类型：{', '.join(safe.get('danger_types', [])) or '无'}",
        ],
        small,
        "#334155",
        8,
    )
    y += 130
    draw.rounded_rectangle((x, y, WIDTH - 95, y + 150), radius=14, fill="#F1F5F9", outline="#D9E2EC")
    multiline(
        draw,
        (x + 18, y + 18),
        [
            "说明：本图不是手绘路网，",
            "而是把高德返回的真实",
            "道路轨迹抽象成二维图。",
            "目的是突出 Dijkstra",
            "避开灾害路段的效果。",
        ],
        load_font(18),
        "#475569",
        6,
    )


def draw_markers(
    draw: ImageDraw.ImageDraw,
    nodes: dict[str, Node],
    path: list[str],
    project,
    start_label: str,
    target_label: str,
) -> None:
    if not path:
        return
    font = load_font(24, bold=True)
    start_node = nodes[path[0]]
    target_node = nodes[path[-1]]
    start_xy = project(start_node.lon, start_node.lat)
    target_xy = project(target_node.lon, target_node.lat)
    markers_are_close = math.hypot(start_xy[0] - target_xy[0], start_xy[1] - target_xy[1]) < 260
    for node_id, label, fill, side in [
        (path[0], start_label, "#178A4A", "right"),
        (path[-1], target_label, "#D64545", "left"),
    ]:
        node = nodes[node_id]
        x, y = project(node.lon, node.lat)
        draw.ellipse((x - 19, y - 19, x + 19, y + 19), fill=fill, outline="#FFFFFF", width=5)
        bbox = draw.textbbox((0, 0), label, font=font)
        text_width = bbox[2] - bbox[0]
        if markers_are_close and node_id == path[0]:
            text_x = min(WIDTH - RIGHT - text_width - 45, x + 25)
            text_y = max(TOP + 8, y - 64)
        elif markers_are_close and node_id == path[-1]:
            text_x = max(LEFT, x - text_width - 28)
            text_y = min(HEIGHT - BOTTOM - 42, y + 28)
        elif side == "left":
            bbox = draw.textbbox((0, 0), label, font=font)
            text_width = bbox[2] - bbox[0]
            text_x = max(LEFT, x - text_width - 28)
            text_y = y - 22
        else:
            text_x = x + 25
            text_y = y - 22
        bbox = draw.textbbox((text_x, text_y), label, font=font)
        draw.rounded_rectangle(
            (bbox[0] - 10, bbox[1] - 7, bbox[2] + 10, bbox[3] + 7),
            radius=10,
            fill="#FFFFFF",
            outline="#D9E2EC",
            width=1,
        )
        draw.text((text_x, text_y), label, font=font, fill="#102033")


def render_scene(data_dir: Path, output_dir: Path, scenario_label: str) -> Path:
    scenario = read_scenario(data_dir / "scenario.json")
    nodes = read_nodes(data_dir / "nodes.csv")
    edges = read_edges(data_dir / "edges.csv")
    events = read_events(data_dir / "disaster_events.csv")
    results = read_results(output_dir / "path_results.json")
    road_source = scenario.get("road_data_source", "AMap Web Service")
    is_osm_scene = (
        "OSM" in scenario_label
        or "OpenStreetMap" in road_source
        or any(edge.variant.startswith("osm_") for edge in edges[:200])
    )
    zoom = 1.34 if "上海火灾OSM" in scenario_label else 1.42 if "上海火灾" in scenario_label else 1.0
    lookup = edge_lookup(edges)
    shortest_path = results.get("distance", {}).get("path", [])
    safe_path = results.get("safe", {}).get("path", [])
    focus_points: list[tuple[float, float]] | None = None
    if is_osm_scene:
        route_focus = route_points(nodes, lookup, shortest_path)
        route_focus.extend(route_points(nodes, lookup, safe_path))
        route_focus.extend(disaster_bounds(events, pad_factor=1.15))
        focus_pad_km = 0.12 if "上海" in scenario_label else 0.9
        focus_points = expand_geo_bounds(route_focus, pad_km=focus_pad_km)
    if is_osm_scene:
        zoom = 1.55 if "上海" in scenario_label else 1.02
    project, scale = build_projector(nodes, edges, events, zoom=zoom, focus_points=focus_points)
    route_keys = path_edge_keys(shortest_path) | path_edge_keys(safe_path)
    route_avoid_points = projected_route_points(nodes, lookup, shortest_path, project)
    route_avoid_points.extend(projected_route_points(nodes, lookup, safe_path, project))

    image = Image.new("RGBA", (WIDTH, HEIGHT), "#F8FAFC")
    draw = ImageDraw.Draw(image)
    title_font = load_font(38, bold=True)
    subtitle_font = load_font(21)
    draw.text((LEFT, 44), f"救援路径规划结果（{scenario_label} · 真实道路二维抽象图）", font=title_font, fill="#102033")
    road_source = scenario.get("road_data_source", "高德 Web 服务")
    draw.text(
        (LEFT, 92),
        f"道路轨迹来自{road_source}，去除复杂地图底图后保留真实坐标形态，便于观察 Dijkstra 路径选择。",
        font=subtitle_font,
        fill="#64748B",
    )

    draw_background_context(draw)
    event_avoid_points: list[tuple[float, float]] = []
    for event in events:
        cx, cy = project(event.lon, event.lat)
        radius = max(34, int(round(event.radius_km * scale)))
        for angle in range(0, 360, 18):
            radians = math.radians(angle)
            event_avoid_points.append((cx + math.cos(radians) * radius, cy + math.sin(radians) * radius))
        event_avoid_points.append((cx, cy))

    draw_context_labels(draw, nodes, project, scenario_label, route_avoid_points)
    draw_disaster_zones(image, events, project, scale)
    draw = ImageDraw.Draw(image)

    edge_count = len(edges)
    for edge in edges:
        if not should_draw_background_edge(edge, edge_count, route_keys):
            continue
        points = edge.polyline
        if not points:
            source = nodes[edge.source]
            target = nodes[edge.target]
            points = [(source.lon, source.lat), (target.lon, target.lat)]
        if is_osm_scene and edge.variant.startswith("osm_"):
            rank = edge_rank(edge)
            line_color = "#CAD4E1" if rank <= 2 else "#B8C5D4"
            line_width = 1 if edge_count > 25_000 else 2
        elif is_osm_scene and edge.variant == "connector":
            line_color = "#DDE5EF"
            line_width = 1
        elif edge.variant.startswith("context_"):
            line_color = "#E4EAF2"
            line_width = 1
        else:
            line_color = "#AEBBCC"
            line_width = 2
        draw_geo_line(draw, points, project, line_color, line_width, smooth=1)

    draw_road_labels(draw, edges, project, scenario_label, route_avoid_points, event_avoid_points)

    danger_lines: list[tuple[list[tuple[float, float]], str | tuple[int, int, int, int], int]] = []
    for edge in edges:
        if edge.danger_type == "normal" or frozenset((edge.source, edge.target)) in route_keys:
            continue
        if not should_draw_danger_edge(edge, edge_count, route_keys):
            continue
        if "上海火灾" in scenario_label and edge.variant.startswith("context_"):
            continue
        points = edge.polyline
        if not points:
            source = nodes[edge.source]
            target = nodes[edge.target]
            points = [(source.lon, source.lat), (target.lon, target.lat)]
        color = (
            "#D64545"
            if edge.danger_type == "collapse"
            else "#4E7DFF"
            if edge.danger_type == "flood"
            else "#E65C18"
            if edge.danger_type == "fire"
            else "#E58B25"
        )
        screen = [project(lon, lat) for lon, lat in points]
        if len(screen) >= 2:
            smooth_iterations = 1 if "上海火灾" in scenario_label else 2
            danger_width = 2 if is_osm_scene else 4
            danger_lines.append((smooth_screen_points(screen, iterations=smooth_iterations), color, danger_width))
    if "上海火灾" in scenario_label:
        danger_lines = bridge_nearby_line_endpoints(danger_lines, max_gap=30.0)
    draw_antialiased_lines(image, danger_lines)
    draw = ImageDraw.Draw(image)

    is_attached_route_scene = is_osm_scene or scenario_label in {"地震场景", "洪水场景"}
    route_casing = "#6F7F95" if is_attached_route_scene else "#FFFFFF"
    shortest_width = 3 if is_attached_route_scene else 7
    safe_width = 4 if is_attached_route_scene else 8
    route_smooth = 0 if is_attached_route_scene else 4
    route_casing_extra = 3 if is_attached_route_scene else 8

    draw_geo_line(
        draw,
        route_points(nodes, lookup, shortest_path),
        project,
        "#1F5EFF",
        shortest_width,
        route_casing,
        smooth=route_smooth,
        image=image,
        antialias=True,
        casing_extra=route_casing_extra,
    )
    draw_geo_line(
        draw,
        route_points(nodes, lookup, safe_path),
        project,
        "#178A4A",
        safe_width,
        route_casing,
        smooth=route_smooth,
        image=image,
        antialias=True,
        casing_extra=route_casing_extra,
    )
    draw = ImageDraw.Draw(image)
    draw_markers(
        draw,
        nodes,
        safe_path or shortest_path,
        project,
        scenario.get("start_label", "起点：清华大学"),
        scenario.get("target_label", "终点：北京朝阳站"),
    )
    draw_side_panel(draw, scenario_label, results)

    draw.rectangle((0, 0, WIDTH, TOP), fill="#F8FAFC")
    draw.text((LEFT, 44), f"救援路径规划结果（{scenario_label} · 真实道路二维抽象图）", font=title_font, fill="#102033")
    draw.text(
        (LEFT, 92),
        f"道路轨迹来自{road_source}，去除复杂地图底图后保留真实坐标形态，便于观察 Dijkstra 路径选择。",
        font=subtitle_font,
        fill="#64748B",
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "route_map_abstract.png"
    image.convert("RGB").save(out_path, quality=95)
    print(f"[ok] {scenario_label}: {out_path}")
    return out_path


def main() -> None:
    scenes = [
        ("地震场景", ROOT / "data" / "amap_earthquake", ROOT / "outputs" / "amap_earthquake"),
        ("洪水场景", ROOT / "data" / "amap_flood", ROOT / "outputs" / "amap_flood"),
        ("地震OSM路网场景", ROOT / "data" / "osm_beijing_earthquake", ROOT / "outputs" / "osm_beijing_earthquake"),
        ("洪水OSM路网场景", ROOT / "data" / "osm_beijing_flood", ROOT / "outputs" / "osm_beijing_flood"),
        ("四川地震场景", ROOT / "data" / "province_sichuan_earthquake", ROOT / "outputs" / "province_sichuan_earthquake"),
        ("北京火灾场景", ROOT / "data" / "amap_fire", ROOT / "outputs" / "amap_fire"),
        ("上海火灾场景", ROOT / "data" / "amap_shanghai_fire", ROOT / "outputs" / "amap_shanghai_fire"),
        ("上海火灾OSM路网场景", ROOT / "data" / "osm_shanghai_fire", ROOT / "outputs" / "osm_shanghai_fire"),
    ]
    for label, data_dir, output_dir in scenes:
        if (data_dir / "nodes.csv").exists() and (output_dir / "path_results.json").exists():
            render_scene(data_dir, output_dir, label)


def render_pipeline_steps(data_dir: Path, output_dir: Path, scenario_label: str) -> list[str]:
    """生成 7 张渐进步骤图，返回相对路径列表。"""
    scenario = read_scenario(data_dir / "scenario.json")
    nodes = read_nodes(data_dir / "nodes.csv")
    edges = read_edges(data_dir / "edges.csv")
    events = read_events(data_dir / "disaster_events.csv")
    results = read_results(output_dir / "path_results.json")
    road_source = scenario.get("road_data_source", "高德 Web 服务")
    is_osm_scene = (
        "OSM" in scenario_label
        or "OpenStreetMap" in road_source
        or any(edge.variant.startswith("osm_") for edge in edges[:200])
    )
    base_zoom = 1.34 if "上海火灾OSM" in scenario_label else 1.42 if "上海火灾" in scenario_label else 1.0
    lookup = edge_lookup(edges)
    shortest_path = results.get("distance", {}).get("path", [])
    safe_path = results.get("safe", {}).get("path", [])
    focus_points: list[tuple[float, float]] | None = None
    if is_osm_scene:
        route_focus = route_points(nodes, lookup, shortest_path)
        route_focus.extend(route_points(nodes, lookup, safe_path))
        route_focus.extend(disaster_bounds(events, pad_factor=1.15))
        focus_pad_km = 0.12 if "上海" in scenario_label else 0.9
        focus_points = expand_geo_bounds(route_focus, pad_km=focus_pad_km)
    zoom = 1.55 if (is_osm_scene and "上海" in scenario_label) else 1.02 if is_osm_scene else base_zoom
    project, scale = build_projector(nodes, edges, events, zoom=zoom, focus_points=focus_points)
    route_keys = path_edge_keys(shortest_path) | path_edge_keys(safe_path)
    route_avoid_points = projected_route_points(nodes, lookup, shortest_path, project)
    route_avoid_points.extend(projected_route_points(nodes, lookup, safe_path, project))

    title_font = load_font(38, bold=True)
    subtitle_font = load_font(21)
    step_title_font = load_font(28, bold=True)
    big_font = load_font(60, bold=True)

    edge_count = len(edges)

    def _base_layer(title_line: str) -> Image.Image:
        """创建每张步骤图的公共底图——白背景 + 标题 + 参考网格。"""
        img = Image.new("RGBA", (WIDTH, HEIGHT), "#F8FAFC")
        d = ImageDraw.Draw(img)
        d.text((LEFT, 44), f"救援路径规划 - {scenario_label}", font=title_font, fill="#102033")
        d.text((LEFT, 92), title_line, font=subtitle_font, fill="#94A3B8")
        draw_background_context(d)
        return img

    def _make_step(step_index: int, step_title: str, draw_fn) -> Path:
        """执行单张步骤图的生成、保存。"""
        subtitle = f"步骤 {step_index}/7 — {step_title}"
        img = _base_layer(subtitle)
        d = ImageDraw.Draw(img)

        # 步骤大号标题（居中）
        step_label = f"第 {step_index} 步"
        d.text((WIDTH // 2 - 110, HEIGHT - 80), step_label, font=big_font, fill="#E2E8F0")
        d.text((WIDTH // 2 + 42, HEIGHT - 55), step_title, font=step_title_font, fill="#334155")

        draw_fn(img, d)

        out_file = output_dir / f"pipeline_step_{step_index}.png"
        output_dir.mkdir(parents=True, exist_ok=True)
        img.convert("RGB").save(out_file, quality=95)
        return out_file

    # ------------------------------------------------------------------
    # 共享辅助函数（在闭包内部定义，可访问外围变量）
    # ------------------------------------------------------------------

    def _draw_background_roads(img: Image.Image, d: ImageDraw.ImageDraw) -> None:
        """只画背景道路（灰色底图），不含灾害区和路径。"""
        for edge in edges:
            if not should_draw_background_edge(edge, edge_count, route_keys):
                continue
            points = edge.polyline
            if not points:
                s, t = nodes[edge.source], nodes[edge.target]
                points = [(s.lon, s.lat), (t.lon, t.lat)]
            if is_osm_scene and edge.variant.startswith("osm_"):
                r = edge_rank(edge)
                line_color = "#CAD4E1" if r <= 2 else "#B8C5D4"
                line_width = 1 if edge_count > 25_000 else 2
            elif is_osm_scene and edge.variant == "connector":
                line_color = "#DDE5EF"
                line_width = 1
            elif edge.variant.startswith("context_"):
                line_color = "#E4EAF2"
                line_width = 1
            else:
                line_color = "#AEBBCC"
                line_width = 2
            draw_geo_line(d, points, project, line_color, line_width, smooth=1)

    def _draw_danger_lines(img: Image.Image) -> None:
        """在 road network + disaster zones 之上画被影响的危险道路。"""
        danger_lines: list[tuple[list[tuple[float, float]], str | tuple[int, int, int, int], int]] = []
        for edge in edges:
            if edge.danger_type == "normal" or frozenset((edge.source, edge.target)) in route_keys:
                continue
            if not should_draw_danger_edge(edge, edge_count, route_keys):
                continue
            if "上海火灾" in scenario_label and edge.variant.startswith("context_"):
                continue
            pts = edge.polyline
            if not pts:
                s, t = nodes[edge.source], nodes[edge.target]
                pts = [(s.lon, s.lat), (t.lon, t.lat)]
            color = (
                "#D64545" if edge.danger_type == "collapse"
                else "#4E7DFF" if edge.danger_type == "flood"
                else "#E65C18" if edge.danger_type == "fire"
                else "#E58B25"
            )
            screen = [project(lon, lat) for lon, lat in pts]
            if len(screen) >= 2:
                smooth_iter = 1 if "上海火灾" in scenario_label else 2
                dw = 2 if is_osm_scene else 4
                danger_lines.append((smooth_screen_points(screen, iterations=smooth_iter), color, dw))
        if "上海火灾" in scenario_label:
            danger_lines = bridge_nearby_line_endpoints(danger_lines, max_gap=30.0)
        draw_antialiased_lines(img, danger_lines)

    def _draw_step1_overview(img: Image.Image, d: ImageDraw.ImageDraw) -> None:
        # 极淡背景道路
        for edge in edges:
            if not should_draw_background_edge(edge, edge_count, route_keys):
                continue
            points = edge.polyline
            if not points:
                s, t = nodes[edge.source], nodes[edge.target]
                points = [(s.lon, s.lat), (t.lon, t.lat)]
            line_color = "#E8EDF3"
            line_width = 1
            draw_geo_line(d, points, project, line_color, line_width, smooth=1)

        # 起点和终点
        path = shortest_path or safe_path
        if path:
            draw_markers(d, nodes, path, project,
                         scenario.get("start_label", "起点"), scenario.get("target_label", "终点"))

        # 灾害事件信息框
        if events:
            evt = events[0]
            box_x = WIDTH // 2 - 200
            box_y = TOP + 40
            info_f = load_font(22, bold=True)
            detail_f = load_font(19)
            lines = [
                f"灾害类型：{evt.danger_type}",
                f"事件名称：{evt.name}",
                f"影响半径：{evt.radius_km} km",
                f"数据来源：历史灾害公开资料",
            ]
            max_w = max(d.textlength(line, detail_f) for line in lines)
            box_w = max_w + 36
            box_h = 24 + 32 + len(lines) * 28
            d.rounded_rectangle(
                (box_x, box_y, box_x + box_w, box_y + box_h),
                radius=14, fill="#FEFCE8", outline="#FDE68A", width=2,
            )
            d.text((box_x + 16, box_y + 14), "历史灾害事件", font=info_f, fill="#92400E")
            for j, line in enumerate(lines):
                d.text((box_x + 16, box_y + 50 + j * 26), line, font=detail_f, fill="#78716C")

    def _draw_step2_roads(img: Image.Image, d: ImageDraw.ImageDraw) -> None:
        """步骤 2：只显示真实 OSM 道路网络，不含灾害区、不含路径。"""
        _draw_background_roads(img, d)
        # 起点和终点
        path = shortest_path or safe_path
        if path:
            draw_markers(d, nodes, path, project,
                         scenario.get("start_label", "起点"), scenario.get("target_label", "终点"))

    def _draw_step3_disaster_zones(img: Image.Image, _d: ImageDraw.ImageDraw) -> None:
        """步骤 3：叠加历史灾害影响区并识别危险路段。"""
        _draw_background_roads(img, _d)
        draw_disaster_zones(img, events, project, scale)
        _draw_danger_lines(img)

    def _draw_step4_congestion(img: Image.Image, _d: ImageDraw.ImageDraw) -> None:
        """步骤 4：保留灾害区和危险路段，叠加交通拥堵。"""
        _draw_background_roads(img, _d)
        draw_disaster_zones(img, events, project, scale)
        _draw_danger_lines(img)
        # 橙色拥堵额外标注
        d2 = ImageDraw.Draw(img)
        path = shortest_path or safe_path
        if path:
            draw_markers(d2, nodes, path, project,
                         scenario.get("start_label", "起点"), scenario.get("target_label", "终点"))

    def _draw_shortest_path_step(img: Image.Image, _d: ImageDraw.ImageDraw) -> None:
        """步骤 5：底图 + 灾害区 + 危险边 + 蓝色最短路径，安全路径不显示。"""
        _draw_background_roads(img, _d)
        draw_disaster_zones(img, events, project, scale)
        _draw_danger_lines(img)
        d2 = ImageDraw.Draw(img)
        casing = "#6F7F95" if (is_osm_scene or scenario_label in {"地震场景", "洪水场景"}) else "#FFFFFF"
        sw = 3 if (is_osm_scene or scenario_label in {"地震场景", "洪水场景"}) else 7
        rs = 0 if (is_osm_scene or scenario_label in {"地震场景", "洪水场景"}) else 4
        ce = 3 if (is_osm_scene or scenario_label in {"地震场景", "洪水场景"}) else 8
        draw_geo_line(
            d2, route_points(nodes, lookup, shortest_path), project,
            "#1F5EFF", sw, casing, smooth=rs, image=img, antialias=True, casing_extra=ce,
        )
        draw_markers(d2, nodes, shortest_path or safe_path, project,
                     scenario.get("start_label", "起点"), scenario.get("target_label", "终点"))

        # 距离信息
        dist = results.get("distance", {})
        dist_val = dist.get("total_distance", "-")
        panel_x = WIDTH - RIGHT - 290
        panel_y = TOP + 20
        info_f = load_font(20)
        d2.rounded_rectangle(
            (panel_x, panel_y, panel_x + 260, panel_y + 50),
            radius=10, fill="#EFF6FF", outline="#93C5FD", width=2,
        )
        d2.text((panel_x + 14, panel_y + 12), f"Dijkstra 最短距离：{dist_val} km", font=info_f, fill="#1E40AF")

    def _draw_safe_path_step(img: Image.Image, _d: ImageDraw.ImageDraw) -> None:
        """步骤 6：只突出绿色安全路径，蓝色最短路径用淡虚线参考。"""
        _draw_background_roads(img, _d)
        draw_disaster_zones(img, events, project, scale)
        _draw_danger_lines(img)
        d2 = ImageDraw.Draw(img)
        is_attached = is_osm_scene or scenario_label in {"地震场景", "洪水场景"}

        # 淡化的蓝色最短路径（半透明虚线参考）
        if len(shortest_path) >= 2:
            short_pts = route_points(nodes, lookup, shortest_path)
            if is_attached:
                draw_geo_line(
                    d2, short_pts, project,
                    (31, 94, 255, 90), 1,
                    smooth=0, image=img, antialias=True, casing_extra=2,
                )
            else:
                draw_geo_line(
                    d2, short_pts, project,
                    (31, 94, 255, 70), 2,
                    smooth=1, image=img, antialias=True, casing_extra=4,
                )

        # 突出的绿色安全路径
        safe_w = 7 if is_attached else 10
        safe_casing = "#2D7A44" if is_attached else "#FFFFFF"
        ce = 6 if is_attached else 10
        draw_geo_line(
            d2, route_points(nodes, lookup, safe_path), project,
            "#178A4A", safe_w, safe_casing, smooth=0 if is_attached else 4,
            image=img, antialias=True, casing_extra=ce,
        )

        d3 = ImageDraw.Draw(img)
        draw_markers(d3, nodes, safe_path or shortest_path, project,
                     scenario.get("start_label", "起点"), scenario.get("target_label", "终点"))

        # 在右下角加公式信息框
        box_x = WIDTH - RIGHT - 280
        box_y = HEIGHT - BOTTOM - 140
        info_font = load_font(20)
        small_font = load_font(17)
        d3.rounded_rectangle(
            (box_x, box_y, WIDTH - RIGHT + 180, HEIGHT - BOTTOM - 10),
            radius=14, fill="#F0FDF4", outline="#86EFAC", width=2,
        )
        d3.text((box_x + 16, box_y + 12), "安全权重 Dijkstra", font=load_font(22, bold=True), fill="#166534")
        lines = [
            "安全权重 = 距离 × 灾害风险系数",
            "          × 拥堵修正系数",
            "Dijkstra 选择综合代价最低路径",
        ]
        for i, line in enumerate(lines):
            d3.text((box_x + 16, box_y + 48 + i * 24), line, font=small_font if i < 2 else info_font, fill="#14532D")

    def _draw_final_overview(img: Image.Image, _d: ImageDraw.ImageDraw) -> None:
        """步骤 7：最终完整对比图，含双路径 + 图例 + 对比数据。"""
        _draw_background_roads(img, _d)
        draw_disaster_zones(img, events, project, scale)
        _draw_danger_lines(img)
        d2 = ImageDraw.Draw(img)
        is_attached = is_osm_scene or scenario_label in {"地震场景", "洪水场景"}
        casing = "#6F7F95" if is_attached else "#FFFFFF"
        sw = 3 if is_attached else 7
        rs = 0 if is_attached else 4
        ce = 3 if is_attached else 8

        # 蓝色最短路径
        draw_geo_line(
            d2, route_points(nodes, lookup, shortest_path), project,
            "#1F5EFF", sw, casing, smooth=rs, image=img, antialias=True, casing_extra=ce,
        )
        # 绿色安全路径
        safe_w = 4 if is_attached else 8
        draw_geo_line(
            d2, route_points(nodes, lookup, safe_path), project,
            "#178A4A", safe_w, casing, smooth=rs, image=img, antialias=True, casing_extra=ce,
        )

        d3 = ImageDraw.Draw(img)
        draw_markers(d3, nodes, safe_path or shortest_path, project,
                     scenario.get("start_label", "起点"), scenario.get("target_label", "终点"))

        # 添加对比信息小面板
        dist_result = results.get("distance", {})
        safe_result = results.get("safe", {})
        panel_x = WIDTH - RIGHT + 35
        panel_y = TOP + 30
        panel_w = 310
        panel_h = 220
        d3.rounded_rectangle(
            (panel_x, panel_y, panel_x + panel_w, panel_y + panel_h),
            radius=14, fill="#FFFFFF", outline="#D9E2EC", width=2,
        )
        d3.text((panel_x + 14, panel_y + 10), "路径对比", font=load_font(26, bold=True), fill="#102033")

        rows = [
            ("普通最短路径", f"{dist_result.get('total_distance', '-')} km", "#1F5EFF"),
            ("安全路径", f"{safe_result.get('total_distance', '-')} km", "#178A4A"),
            ("综合代价", f"{safe_result.get('total_cost', '-')}", "#178A4A"),
            ("危险类型", ", ".join(safe_result.get("danger_types", []) or []), "#E58B25"),
        ]
        small_f = load_font(19)
        for j, (label, value, color) in enumerate(rows):
            y = panel_y + 52 + j * 34
            d3.text((panel_x + 14, y), label, font=small_f, fill="#64748B")
            d3.text((panel_x + panel_w - 14, y), str(value), font=small_f, fill=color, anchor="ra")

        d3.text(
            (panel_x + 14, panel_y + panel_h - 26),
            "Dijkstra 完整对比结果",
            font=load_font(16), fill="#94A3B8",
        )

    steps: list[tuple[str, Callable[[Image.Image, ImageDraw.ImageDraw], None]]] = [
        ("选择灾害事件和起终点", _draw_step1_overview),
        ("加载真实道路网络", _draw_step2_roads),
        ("叠加灾害影响区", _draw_step3_disaster_zones),
        ("标记危险和拥堵路段", _draw_step4_congestion),
        ("Dijkstra · 普通最短路径", _draw_shortest_path_step),
        ("Dijkstra · 安全救援路径", _draw_safe_path_step),
        ("路径对比与最终结果", _draw_final_overview),
    ]

    out_paths: list[str] = []
    for i, (step_title, draw_fn) in enumerate(steps, start=1):
        out_file = _make_step(i, step_title, draw_fn)
        try:
            rel = out_file.resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            rel = ""
        out_paths.append(rel)
        print(f"[pipeline] step {i}/7: {step_title} -> {rel}")

    return out_paths


if __name__ == "__main__":
    main()
