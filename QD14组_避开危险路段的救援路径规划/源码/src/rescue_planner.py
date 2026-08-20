from __future__ import annotations

import argparse
import csv
import heapq
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"


@dataclass(frozen=True)
class Node:
    node_id: str
    x: float
    y: float
    label: str
    type: str


@dataclass(frozen=True)
class Edge:
    edge_id: str
    source: str
    target: str
    distance: float
    danger_type: str
    congestion: float
    passable: bool
    safe_weight: float
    road_name: str = ""
    variant: str = ""
    background_only: bool = False


@dataclass
class PathResult:
    algorithm: str
    mode: str
    path: list[str]
    total_distance: float
    total_cost: float
    dangerous_edge_count: int
    dangerous_edges: list[str]
    danger_types: list[str]
    rescue_assessment: str


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


def load_nodes(path: Path) -> dict[str, Node]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = csv.DictReader(f)
        return {
            row["node_id"]: Node(
                node_id=row["node_id"],
                x=float(row["x"]),
                y=float(row["y"]),
                label=row["label"],
                type=row["type"],
            )
            for row in rows
        }


def load_scenario(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_disaster_events(path: Path) -> list[DisasterEvent]:
    if not path.exists():
        return []
    events: list[DisasterEvent] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            events.append(
                DisasterEvent(
                    event_id=row["event_id"],
                    scenario=row["scenario"],
                    disaster_type=row["disaster_type"],
                    name=row["name"],
                    event_date=row["event_date"],
                    longitude=float(row["longitude"]),
                    latitude=float(row["latitude"]),
                    influence_radius_km=float(row["influence_radius_km"]),
                    danger_type=row["danger_type"],
                    severity=row["severity"],
                    source_title=row["source_title"],
                    source_url=row["source_url"],
                    evidence=row["evidence"],
                    mapping_note=row["mapping_note"],
                )
            )
    return events


def compute_safe_weight(distance: float, danger_type: str, congestion: float, scenario: dict) -> float:
    risk_factor = float(scenario["risk_factors"].get(danger_type, 1.0))
    congestion_weight = float(scenario.get("congestion_weight", 0.6))
    fixed_costs = scenario.get("danger_fixed_costs", {})
    fixed_cost = float(fixed_costs.get(danger_type, 0.0))
    return distance * risk_factor * (1.0 + congestion_weight * congestion) + fixed_cost


def load_edges(path: Path, scenario: dict) -> list[Edge]:
    edges: list[Edge] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = csv.DictReader(f)
        for row in rows:
            distance = float(row["distance"])
            danger_type = row["danger_type"]
            congestion = float(row["congestion"])
            variant = row.get("variant", "")
            edges.append(
                Edge(
                    edge_id=row["edge_id"],
                    source=row["from"],
                    target=row["to"],
                    distance=distance,
                    danger_type=danger_type,
                    congestion=congestion,
                    passable=row["passable"].strip().lower() == "true",
                    safe_weight=compute_safe_weight(distance, danger_type, congestion, scenario),
                    road_name=row.get("road_name", ""),
                    variant=variant,
                    background_only=variant.startswith("context_"),
                )
            )
    return edges


def build_graph(edges: Iterable[Edge], undirected: bool = True) -> dict[str, list[tuple[str, Edge]]]:
    graph: dict[str, list[tuple[str, Edge]]] = {}
    for edge in edges:
        if not edge.passable or edge.background_only:
            continue
        graph.setdefault(edge.source, []).append((edge.target, edge))
        graph.setdefault(edge.target, [])
        if undirected:
            graph.setdefault(edge.target, []).append((edge.source, edge))
            graph.setdefault(edge.source, [])
    return graph


def edge_cost(edge: Edge, mode: str) -> float:
    if mode == "distance":
        return edge.distance
    if mode == "safe":
        return edge.safe_weight
    raise ValueError(f"Unknown mode: {mode}")


def dijkstra(
    graph: dict[str, list[tuple[str, Edge]]],
    start: str,
    target: str,
    mode: str,
) -> tuple[list[str], float]:
    queue: list[tuple[float, str]] = [(0.0, start)]
    best_cost: dict[str, float] = {start: 0.0}
    previous: dict[str, str] = {}

    while queue:
        current_cost, node_id = heapq.heappop(queue)
        if current_cost > best_cost.get(node_id, math.inf):
            continue
        if node_id == target:
            return reconstruct_path(previous, start, target), current_cost
        for neighbor, edge in graph.get(node_id, []):
            new_cost = current_cost + edge_cost(edge, mode)
            if new_cost < best_cost.get(neighbor, math.inf):
                best_cost[neighbor] = new_cost
                previous[neighbor] = node_id
                heapq.heappush(queue, (new_cost, neighbor))

    return [], math.inf


def reconstruct_path(previous: dict[str, str], start: str, target: str) -> list[str]:
    if start == target:
        return [start]
    if target not in previous:
        return []
    path = [target]
    while path[-1] != start:
        path.append(previous[path[-1]])
    path.reverse()
    return path


def edge_lookup(edges: Iterable[Edge]) -> dict[frozenset[str], Edge]:
    return {frozenset((edge.source, edge.target)): edge for edge in edges if not edge.background_only}


def edges_for_path(path: list[str], lookup: dict[frozenset[str], Edge]) -> list[Edge]:
    path_edges: list[Edge] = []
    for source, target in zip(path, path[1:]):
        edge = lookup.get(frozenset((source, target)))
        if edge is None:
            raise ValueError(f"No edge found between {source} and {target}")
        path_edges.append(edge)
    return path_edges


def summarize_path(algorithm: str, mode: str, path: list[str], cost: float, edges: list[Edge]) -> PathResult:
    if not path:
        return PathResult(
            algorithm=algorithm,
            mode=mode,
            path=[],
            total_distance=math.inf,
            total_cost=math.inf,
            dangerous_edge_count=0,
            dangerous_edges=[],
            danger_types=[],
            rescue_assessment="不可达：当前可通行道路无法连接起点和受灾点。",
        )

    dangerous_edges = [edge for edge in edges if edge.danger_type != "normal"]
    danger_types = sorted({edge.danger_type for edge in dangerous_edges})
    total_distance = sum(edge.distance for edge in edges)
    assessment = build_assessment(mode, total_distance, cost, dangerous_edges)
    return PathResult(
        algorithm=algorithm,
        mode=mode,
        path=path,
        total_distance=round(total_distance, 3),
        total_cost=round(cost, 3),
        dangerous_edge_count=len(dangerous_edges),
        dangerous_edges=[edge.edge_id for edge in dangerous_edges],
        danger_types=danger_types,
        rescue_assessment=assessment,
    )


def build_assessment(mode: str, total_distance: float, total_cost: float, dangerous_edges: list[Edge]) -> str:
    if mode == "distance":
        if dangerous_edges:
            return "距离较短，但经过危险路段，不宜直接作为灾害救援首选路线。"
        return "距离较短且未经过危险路段，可作为救援路线候选。"
    if dangerous_edges:
        return "综合代价较低，但仍包含部分风险路段，需要现场确认后通行。"
    return "绕开主要危险路段，安全性更高，适合作为救援推荐路线。"


def run_planning(data_dir: Path, output_dir: Path) -> list[PathResult]:
    nodes = load_nodes(data_dir / "nodes.csv")
    scenario = load_scenario(data_dir / "scenario.json")
    disaster_events = load_disaster_events(data_dir / "disaster_events.csv")
    edges = load_edges(data_dir / "edges.csv", scenario)
    graph = build_graph(edges, undirected=bool(scenario.get("undirected", True)))
    lookup = edge_lookup(edges)
    start = scenario["start_node"]
    target = scenario["target_node"]

    planners: list[tuple[str, Callable[[str], tuple[list[str], float]]]] = [
        ("Dijkstra", lambda mode: dijkstra(graph, start, target, mode)),
    ]
    results: list[PathResult] = []
    for algorithm, planner in planners:
        for mode in ("distance", "safe"):
            path, cost = planner(mode)
            path_edges = edges_for_path(path, lookup) if path else []
            results.append(summarize_path(algorithm, mode, path, cost, path_edges))

    output_dir.mkdir(parents=True, exist_ok=True)
    write_edge_weights(output_dir / "edge_weights.csv", edges)
    write_results(output_dir, results)
    render_network_map(output_dir / "route_map.png", nodes, edges, results, disaster_events)
    render_presentation_map(output_dir / "route_map_clean.png", nodes, edges, results, disaster_events)
    render_context_map(output_dir / "route_map_context.png", nodes, edges, results, disaster_events)
    return results


def write_edge_weights(path: Path, edges: list[Edge]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "edge_id",
            "from",
            "to",
            "distance",
            "danger_type",
            "congestion",
            "passable",
            "safe_weight",
            "variant",
            "background_only",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for edge in edges:
            writer.writerow(
                {
                    "edge_id": edge.edge_id,
                    "from": edge.source,
                    "to": edge.target,
                    "distance": edge.distance,
                    "danger_type": edge.danger_type,
                    "congestion": edge.congestion,
                    "passable": edge.passable,
                    "safe_weight": round(edge.safe_weight, 3),
                    "variant": edge.variant,
                    "background_only": edge.background_only,
                }
            )


def write_results(output_dir: Path, results: list[PathResult]) -> None:
    json_path = output_dir / "path_results.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump([asdict(result) for result in results], f, ensure_ascii=False, indent=2)

    csv_path = output_dir / "path_comparison.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "algorithm",
            "mode",
            "path",
            "total_distance",
            "total_cost",
            "dangerous_edge_count",
            "danger_types",
            "rescue_assessment",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "algorithm": result.algorithm,
                    "mode": result.mode,
                    "path": " -> ".join(result.path),
                    "total_distance": result.total_distance,
                    "total_cost": result.total_cost,
                    "dangerous_edge_count": result.dangerous_edge_count,
                    "danger_types": ", ".join(result.danger_types),
                    "rescue_assessment": result.rescue_assessment,
                }
            )


def render_network_map(
    path: Path,
    nodes: dict[str, Node],
    edges: list[Edge],
    results: list[PathResult],
    disaster_events: list[DisasterEvent] | None = None,
) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        render_network_svg(path.with_suffix(".svg"), nodes, edges, results)
        return

    width, height = 1100, 700
    margin = 90
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = load_display_font(13)

    xs = [node.x for node in nodes.values()]
    ys = [node.y for node in nodes.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    def point(node_id: str, y_offset: int = 0) -> tuple[int, int]:
        node = nodes[node_id]
        x = margin + (node.x - min_x) / (max_x - min_x) * (width - 2 * margin)
        y = height - margin - (node.y - min_y) / (max_y - min_y) * (height - 2 * margin)
        return int(x), int(y + y_offset)

    def geo_point(lon: float, lat: float) -> tuple[int, int]:
        x = margin + (lon - min_x) / (max_x - min_x) * (width - 2 * margin)
        y = height - margin - (lat - min_y) / (max_y - min_y) * (height - 2 * margin)
        return int(x), int(y)

    for event in disaster_events or []:
        cx, cy = geo_point(event.longitude, event.latitude)
        radius_lon = event.influence_radius_km / (111.320 * max(math.cos(math.radians(event.latitude)), 0.01))
        rx, _ = geo_point(event.longitude + radius_lon, event.latitude)
        radius_px = max(18, abs(rx - cx))
        color = (210, 65, 65) if event.danger_type == "collapse" else (50, 130, 220)
        draw.ellipse([cx - radius_px, cy - radius_px, cx + radius_px, cy + radius_px], outline=color, width=3)
        draw.text((cx + 8, cy - radius_px - 18), event.disaster_type, fill=color, font=font)

    edge_colors = {
        "normal": (175, 175, 175),
        "congestion": (230, 150, 40),
        "flood": (50, 130, 220),
        "collapse": (210, 65, 65),
    }
    for edge in edges:
        p1 = point(edge.source)
        p2 = point(edge.target)
        color = edge_colors.get(edge.danger_type, (130, 130, 130))
        width_px = 2 if edge.passable else 1
        draw.line([p1, p2], fill=color, width=width_px)
        mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
        label = f"{edge.edge_id}:{edge.distance:g}"
        draw.text((mid[0] + 4, mid[1] + 4), label, fill=(80, 80, 80), font=font)
        if not edge.passable:
            draw.text((mid[0] - 12, mid[1] - 14), "closed", fill=(180, 0, 0), font=font)

    dijkstra_distance = next(r for r in results if r.algorithm == "Dijkstra" and r.mode == "distance")
    dijkstra_safe = next(r for r in results if r.algorithm == "Dijkstra" and r.mode == "safe")
    draw_path(draw, dijkstra_distance.path, point, (30, 90, 210), 7, -7)
    draw_path(draw, dijkstra_safe.path, point, (20, 150, 70), 7, 7)

    for node in nodes.values():
        x, y = point(node.node_id)
        fill = (50, 140, 70) if node.type == "start" else (190, 50, 50) if node.type == "target" else (245, 245, 245)
        outline = (30, 30, 30)
        draw.ellipse([x - 14, y - 14, x + 14, y + 14], fill=fill, outline=outline, width=2)
        draw.text((x - 4, y - 5), node.node_id, fill=(0, 0, 0), font=font)
        draw.text((x - 35, y + 18), node.label, fill=(35, 35, 35), font=font)

    draw.text((margin, 25), "Rescue Route Planning: shortest path vs safe path", fill=(20, 20, 20), font=font)
    legend_x, legend_y = width - 340, 35
    legend_items = [
        ((30, 90, 210), "Shortest path"),
        ((20, 150, 70), "Safe path"),
        ((210, 65, 65), "Collapse road"),
        ((50, 130, 220), "Flooded road"),
        ((230, 150, 40), "Congested road"),
    ]
    for index, (color, label) in enumerate(legend_items):
        y = legend_y + index * 24
        draw.line([(legend_x, y + 8), (legend_x + 42, y + 8)], fill=color, width=5)
        draw.text((legend_x + 52, y), label, fill=(20, 20, 20), font=font)

    image.save(path)


def load_display_font(size: int):
    try:
        from PIL import ImageFont
    except ImportError:
        return None

    font_candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ]
    for font_path in font_candidates:
        if font_path.exists():
            try:
                return ImageFont.truetype(str(font_path), size)
            except OSError:
                continue
    return ImageFont.load_default()


def draw_path(draw, path: list[str], point_func: Callable[[str, int], tuple[int, int]], color, width: int, offset: int) -> None:
    if len(path) < 2:
        return
    points = [point_func(node_id, offset) for node_id in path]
    draw.line(points, fill=color, width=width, joint="curve")


def render_network_svg(path: Path, nodes: dict[str, Node], edges: list[Edge], results: list[PathResult]) -> None:
    width, height = 1100, 700
    margin = 90
    xs = [node.x for node in nodes.values()]
    ys = [node.y for node in nodes.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    def point(node_id: str, y_offset: int = 0) -> tuple[float, float]:
        node = nodes[node_id]
        x = margin + (node.x - min_x) / (max_x - min_x) * (width - 2 * margin)
        y = height - margin - (node.y - min_y) / (max_y - min_y) * (height - 2 * margin)
        return x, y + y_offset

    colors = {"normal": "#b0b0b0", "congestion": "#e69628", "flood": "#3282dc", "collapse": "#d24141"}
    shortest = next(r for r in results if r.algorithm == "Dijkstra" and r.mode == "distance").path
    safe = next(r for r in results if r.algorithm == "Dijkstra" and r.mode == "safe").path

    def svg_polyline(path_nodes: list[str], color: str, offset: int) -> str:
        if len(path_nodes) < 2:
            return ""
        points = " ".join(f"{x:.1f},{y:.1f}" for x, y in (point(node_id, offset) for node_id in path_nodes))
        return f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="7" stroke-linecap="round" />'

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white" />',
        '<text x="90" y="35" font-size="20" font-family="Arial">Rescue Route Planning: shortest path vs safe path</text>',
    ]
    for edge in edges:
        x1, y1 = point(edge.source)
        x2, y2 = point(edge.target)
        stroke_dash = ' stroke-dasharray="8 6"' if not edge.passable else ""
        lines.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{colors.get(edge.danger_type, "#888")}" stroke-width="2"{stroke_dash} />'
        )
    lines.append(svg_polyline(shortest, "#1e5ad2", -7))
    lines.append(svg_polyline(safe, "#149646", 7))
    for node in nodes.values():
        x, y = point(node.node_id)
        fill = "#328c46" if node.type == "start" else "#be3232" if node.type == "target" else "#f5f5f5"
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="14" fill="{fill}" stroke="#222" stroke-width="2" />')
        lines.append(f'<text x="{x - 5:.1f}" y="{y + 5:.1f}" font-size="14" font-family="Arial">{node.node_id}</text>')
    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def render_presentation_map(
    path: Path,
    nodes: dict[str, Node],
    edges: list[Edge],
    results: list[PathResult],
    disaster_events: list[DisasterEvent] | None = None,
) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return

    width, height = 1500, 900
    margin = 110
    image = Image.new("RGB", (width, height), "#F7FAFC")
    draw = ImageDraw.Draw(image)
    title_font = load_display_font(34)
    label_font = load_display_font(22)
    small_font = load_display_font(18)

    xs = [node.x for node in nodes.values()]
    ys = [node.y for node in nodes.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    pad_x = max((max_x - min_x) * 0.08, 0.01)
    pad_y = max((max_y - min_y) * 0.08, 0.01)
    min_x -= pad_x
    max_x += pad_x
    min_y -= pad_y
    max_y += pad_y

    def point(node_id: str) -> tuple[int, int]:
        node = nodes[node_id]
        x = margin + (node.x - min_x) / (max_x - min_x) * (width - 2 * margin)
        y = height - margin - (node.y - min_y) / (max_y - min_y) * (height - 2 * margin)
        return int(x), int(y)

    def geo_point(lon: float, lat: float) -> tuple[int, int]:
        x = margin + (lon - min_x) / (max_x - min_x) * (width - 2 * margin)
        y = height - margin - (lat - min_y) / (max_y - min_y) * (height - 2 * margin)
        return int(x), int(y)

    def draw_disaster_events() -> None:
        if not disaster_events:
            return
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        for event in disaster_events:
            cx, cy = geo_point(event.longitude, event.latitude)
            radius_lon = event.influence_radius_km / (111.320 * max(math.cos(math.radians(event.latitude)), 0.01))
            rx, _ = geo_point(event.longitude + radius_lon, event.latitude)
            radius_px = max(28, abs(rx - cx))
            if event.danger_type == "collapse":
                fill = (214, 69, 69, 48)
                outline = (214, 69, 69, 210)
                label = "历史地震影响区"
            else:
                fill = (31, 94, 255, 42)
                outline = (31, 94, 255, 210)
                label = "历史洪水影响区"
            overlay_draw.ellipse(
                [cx - radius_px, cy - radius_px, cx + radius_px, cy + radius_px],
                fill=fill,
                outline=outline,
                width=4,
            )
            overlay_draw.text((cx + 14, cy - radius_px - 26), label, fill=outline, font=small_font)
        composed = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
        image.paste(composed)

    def path_edges(path_nodes: list[str]) -> set[frozenset[str]]:
        return {frozenset((a, b)) for a, b in zip(path_nodes, path_nodes[1:])}

    shortest = next(r for r in results if r.algorithm == "Dijkstra" and r.mode == "distance")
    safe = next(r for r in results if r.algorithm == "Dijkstra" and r.mode == "safe")
    avoided = avoided_danger_label(shortest, safe)
    shortest_edges = path_edges(shortest.path)
    safe_edges = path_edges(safe.path)
    relevant_edges = shortest_edges | safe_edges
    lookup = edge_lookup(edges)

    draw.text((margin, 42), "救援路径规划结果（汇报简化图）", fill="#102033", font=title_font)
    draw.text((margin, 90), "只展示普通最短路径与安全路径主线，隐藏密集道路节点，便于课堂汇报说明。", fill="#5B677A", font=small_font)

    draw_disaster_events()

    # Light context: only route-related edges, no labels.
    for edge_key in relevant_edges:
        edge = lookup.get(edge_key)
        if not edge:
            continue
        p1 = point(edge.source)
        p2 = point(edge.target)
        color = "#D0DAE6"
        if edge.danger_type == "flood":
            color = "#82B8FF"
        elif edge.danger_type == "collapse":
            color = "#F09595"
        elif edge.danger_type == "congestion":
            color = "#F0B86A"
        draw.line([p1, p2], fill=color, width=3)

    def draw_route(path_nodes: list[str], color: str, width_px: int, offset_y: int = 0) -> None:
        if len(path_nodes) < 2:
            return
        raw_points = [(x, y + offset_y) for x, y in (point(node_id) for node_id in path_nodes)]
        points = simplify_polyline(raw_points, epsilon=34.0)
        draw.line(points, fill=color, width=width_px, joint="curve")

    draw_route(shortest.path, "#1F5EFF", 9, -6)
    draw_route(safe.path, "#178A4A", 11, 8)

    start = shortest.path[0] if shortest.path else safe.path[0]
    target = shortest.path[-1] if shortest.path else safe.path[-1]
    start_xy = point(start)
    target_xy = point(target)
    for node_id, label, fill in [(start, "起点\n清华大学", "#178A4A"), (target, "终点\n北京朝阳站", "#D64545")]:
        x, y = point(node_id)
        draw.ellipse([x - 22, y - 22, x + 22, y + 22], fill=fill, outline="#102033", width=3)
        draw.text((x + 28, y - 24), label, fill="#102033", font=label_font)

    # Add callouts at rough midpoints.
    draw_callout(draw, (120, 240), "普通最短路径", f"距离 {shortest.total_distance} km\n经过 {', '.join(shortest.danger_types) or 'normal'}", "#EAF2FF", "#1F5EFF", label_font, small_font)
    draw_callout(draw, (390, 700), "安全路径", f"距离 {safe.total_distance} km\n{avoided}", "#E8F6EE", "#178A4A", label_font, small_font)

    legend_x, legend_y = width - 420, 55
    legend = [
        ("#1F5EFF", "普通最短路径"),
        ("#178A4A", "安全路径"),
        ("#F0B86A", "拥堵路段"),
    ]
    danger_types = {edge.danger_type for edge in edges if edge.danger_type != "normal"}
    if "flood" in danger_types:
        legend.insert(2, ("#82B8FF", "积水风险路段"))
    if "collapse" in danger_types:
        legend.insert(2, ("#F09595", "塌方风险路段"))
    if disaster_events:
        zone_color = "#D64545" if disaster_events[0].danger_type == "collapse" else "#1F5EFF"
        legend.append((zone_color, "历史灾害影响区"))
    for i, (color, label) in enumerate(legend):
        y = legend_y + i * 42
        draw.line([(legend_x, y + 14), (legend_x + 62, y + 14)], fill=color, width=8)
        draw.text((legend_x + 78, y), label, fill="#102033", font=small_font)

    image.save(path)


def render_context_map(
    path: Path,
    nodes: dict[str, Node],
    edges: list[Edge],
    results: list[PathResult],
    disaster_events: list[DisasterEvent] | None = None,
) -> None:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return

    width, height = 1500, 900
    margin = 105
    image = Image.new("RGB", (width, height), "#F3F7FB")
    draw = ImageDraw.Draw(image)
    title_font = load_display_font(34)
    label_font = load_display_font(20)
    small_font = load_display_font(16)
    tiny_font = load_display_font(13)

    xs = [node.x for node in nodes.values()]
    ys = [node.y for node in nodes.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    pad_x = max((max_x - min_x) * 0.10, 0.01)
    pad_y = max((max_y - min_y) * 0.10, 0.01)
    min_x -= pad_x
    max_x += pad_x
    min_y -= pad_y
    max_y += pad_y

    def point(node_id: str, offset_y: int = 0) -> tuple[int, int]:
        node = nodes[node_id]
        x = margin + (node.x - min_x) / (max_x - min_x) * (width - 2 * margin)
        y = height - margin - (node.y - min_y) / (max_y - min_y) * (height - 2 * margin)
        return int(x), int(y + offset_y)

    def geo_point(lon: float, lat: float) -> tuple[int, int]:
        x = margin + (lon - min_x) / (max_x - min_x) * (width - 2 * margin)
        y = height - margin - (lat - min_y) / (max_y - min_y) * (height - 2 * margin)
        return int(x), int(y)

    def path_edge_keys(path_nodes: list[str]) -> set[frozenset[str]]:
        return {frozenset((a, b)) for a, b in zip(path_nodes, path_nodes[1:])}

    shortest = next(r for r in results if r.algorithm == "Dijkstra" and r.mode == "distance")
    safe = next(r for r in results if r.algorithm == "Dijkstra" and r.mode == "safe")
    shortest_edges = path_edge_keys(shortest.path)
    safe_edges = path_edge_keys(safe.path)

    # Map-like background: light districts, coordinate grid, and all AMap candidate roads.
    district_boxes = [
        ("海淀区 / 清华-中关村", (80, 115, 430, 335), "#EAF2FF"),
        ("西城-东城核心区", (410, 425, 780, 650), "#FFF2DF"),
        ("望京-东四环片区", (820, 170, 1210, 430), "#E8F6EE"),
        ("朝阳站周边", (1040, 570, 1390, 770), "#FDECEC"),
    ]
    for label, box, fill in district_boxes:
        draw.rounded_rectangle(box, radius=18, fill=fill, outline="#D9E2EC", width=1)
        draw.text((box[0] + 18, box[1] + 16), label, fill="#7890A8", font=tiny_font)

    for i in range(6):
        x = margin + i * (width - 2 * margin) / 5
        draw.line([(x, margin), (x, height - margin)], fill="#E1E8F0", width=1)
    for i in range(4):
        y = margin + i * (height - 2 * margin) / 3
        draw.line([(margin, y), (width - margin), (y)], fill="#E1E8F0", width=1)

    if disaster_events:
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        for event in disaster_events:
            cx, cy = geo_point(event.longitude, event.latitude)
            radius_lon = event.influence_radius_km / (111.320 * max(math.cos(math.radians(event.latitude)), 0.01))
            rx, _ = geo_point(event.longitude + radius_lon, event.latitude)
            radius_px = max(28, abs(rx - cx))
            if event.danger_type == "collapse":
                fill = (214, 69, 69, 42)
                outline = (214, 69, 69, 210)
                label = "历史地震影响区"
            else:
                fill = (31, 94, 255, 38)
                outline = (31, 94, 255, 210)
                label = "历史洪水影响区"
            overlay_draw.ellipse(
                [cx - radius_px, cy - radius_px, cx + radius_px, cy + radius_px],
                fill=fill,
                outline=outline,
                width=4,
            )
            overlay_draw.text((cx + 14, cy - radius_px - 26), label, fill=outline, font=small_font)
        image.paste(Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB"))
        draw = ImageDraw.Draw(image)

    edge_colors = {
        "normal": "#AFC1D2",
        "congestion": "#F0B86A",
        "flood": "#82B8FF",
        "collapse": "#F09595",
    }
    labeled_roads: set[str] = set()
    for edge in edges:
        p1 = point(edge.source)
        p2 = point(edge.target)
        key = frozenset((edge.source, edge.target))
        route_edge = key in shortest_edges or key in safe_edges
        width_px = 5 if route_edge else 3
        draw.line([p1, p2], fill=edge_colors.get(edge.danger_type, "#AFC1D2"), width=width_px)
        road_name = getattr(edge, "road_name", "") if hasattr(edge, "road_name") else ""
        if not road_name:
            continue
        if edge.distance >= 0.8 and road_name not in labeled_roads and len(labeled_roads) < 18:
            mx = (p1[0] + p2[0]) // 2
            my = (p1[1] + p2[1]) // 2
            draw.text((mx + 4, my - 18), road_name[:12], fill="#64748B", font=tiny_font)
            labeled_roads.add(road_name)

    draw_path(draw, shortest.path, point, "#1F5EFF", 10, -5)
    draw_path(draw, safe.path, point, "#178A4A", 12, 8)

    start = shortest.path[0] if shortest.path else safe.path[0]
    target = shortest.path[-1] if shortest.path else safe.path[-1]
    for node_id, label, fill in [
        (start, "起点\n清华大学", "#178A4A"),
        (target, "终点\n北京朝阳站", "#D64545"),
    ]:
        x, y = point(node_id)
        draw.ellipse([x - 22, y - 22, x + 22, y + 22], fill=fill, outline="#102033", width=3)
        draw.text((x + 28, y - 24), label, fill="#102033", font=label_font)

    draw.text((margin, 38), "救援路径规划结果（道路背景增强图）", fill="#102033", font=title_font)
    draw.text(
        (margin, 84),
        "浅色线为高德返回的全部候选道路，粗线为 Dijkstra 输出路径，半透明区域为历史灾害影响区。",
        fill="#5B677A",
        font=small_font,
    )

    draw_callout(
        draw,
        (112, 250),
        "普通最短路径",
        f"距离 {shortest.total_distance} km\n经过 {', '.join(shortest.danger_types) or 'normal'}",
        "#EAF2FF",
        "#1F5EFF",
        label_font,
        small_font,
    )
    draw_callout(
        draw,
        (360, 705),
        "安全路径",
        f"距离 {safe.total_distance} km\n{avoided_danger_label(shortest, safe)}",
        "#E8F6EE",
        "#178A4A",
        label_font,
        small_font,
    )

    legend_x, legend_y = width - 395, 55
    legend = [
        ("#AFC1D2", "高德候选道路背景"),
        ("#1F5EFF", "普通最短路径"),
        ("#178A4A", "安全路径"),
        ("#F09595", "塌方风险路段"),
        ("#82B8FF", "积水风险路段"),
        ("#F0B86A", "拥堵路段"),
    ]
    for i, (color, label) in enumerate(legend):
        y = legend_y + i * 38
        draw.line([(legend_x, y + 12), (legend_x + 58, y + 12)], fill=color, width=7)
        draw.text((legend_x + 74, y), label, fill="#102033", font=small_font)

    image.save(path)


def draw_callout(draw, xy: tuple[int, int], title: str, body: str, fill: str, accent: str, title_font, body_font) -> None:
    x, y = xy
    draw.rounded_rectangle([x, y, x + 280, y + 112], radius=14, fill=fill, outline="#D9E2EC", width=2)
    draw.rectangle([x, y, x + 8, y + 112], fill=accent)
    draw.text((x + 22, y + 18), title, fill=accent, font=title_font)
    draw.text((x + 22, y + 56), body, fill="#102033", font=body_font)


def avoided_danger_label(shortest: PathResult, safe: PathResult) -> str:
    reduced = [item for item in shortest.danger_types if item not in safe.danger_types]
    if "collapse" in reduced:
        return "避开 collapse 塌方风险"
    if "flood" in reduced:
        return "避开 flood 积水风险"
    if reduced:
        return "避开 " + ", ".join(reduced) + " 风险"
    return "降低综合通行风险"


def simplify_polyline(points: list[tuple[int, int]], epsilon: float) -> list[tuple[int, int]]:
    if len(points) <= 2:
        return points

    def point_line_distance(point: tuple[int, int], start: tuple[int, int], end: tuple[int, int]) -> float:
        px, py = point
        sx, sy = start
        ex, ey = end
        dx = ex - sx
        dy = ey - sy
        if dx == 0 and dy == 0:
            return math.hypot(px - sx, py - sy)
        t = max(0.0, min(1.0, ((px - sx) * dx + (py - sy) * dy) / (dx * dx + dy * dy)))
        proj_x = sx + t * dx
        proj_y = sy + t * dy
        return math.hypot(px - proj_x, py - proj_y)

    start = points[0]
    end = points[-1]
    max_distance = 0.0
    split_index = 0
    for index in range(1, len(points) - 1):
        distance = point_line_distance(points[index], start, end)
        if distance > max_distance:
            max_distance = distance
            split_index = index

    if max_distance > epsilon:
        left = simplify_polyline(points[: split_index + 1], epsilon)
        right = simplify_polyline(points[split_index:], epsilon)
        return left[:-1] + right
    return [start, end]


def print_summary(results: list[PathResult]) -> None:
    print("Rescue path planning completed.\n")
    for result in results:
        print(
            f"{result.algorithm:8s} | {result.mode:8s} | "
            f"path: {' -> '.join(result.path) or 'unreachable'} | "
            f"distance: {result.total_distance} | cost: {result.total_cost} | "
            f"danger edges: {result.dangerous_edge_count}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Disaster rescue path planning demo.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = run_planning(args.data_dir, args.output_dir)
    print_summary(results)


if __name__ == "__main__":
    main()
