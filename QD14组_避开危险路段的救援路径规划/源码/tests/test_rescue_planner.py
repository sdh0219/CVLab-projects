from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rescue_planner import (  # noqa: E402
    build_graph,
    dijkstra,
    edge_cost,
    edge_lookup,
    edges_for_path,
    load_edges,
    load_scenario,
    run_planning,
)


def main() -> None:
    data_dir = PROJECT_ROOT / "data"
    scenario = load_scenario(data_dir / "scenario.json")
    edges = load_edges(data_dir / "edges.csv", scenario)
    graph = build_graph(edges, undirected=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        results = run_planning(data_dir, Path(tmpdir))

    by_key = {(result.algorithm, result.mode): result for result in results}
    assert by_key[("Dijkstra", "distance")].dangerous_edge_count > by_key[("Dijkstra", "safe")].dangerous_edge_count
    assert by_key[("Dijkstra", "safe")].total_distance > by_key[("Dijkstra", "distance")].total_distance
    assert by_key[("Dijkstra", "safe")].path == ["A", "E", "F", "G", "H", "I"]

    lookup = edge_lookup(edges)
    shortest_edges = edges_for_path(by_key[("Dijkstra", "distance")].path, lookup)
    safe_edges = edges_for_path(by_key[("Dijkstra", "safe")].path, lookup)
    shortest_path_safe_cost = sum(edge_cost(edge, "safe") for edge in shortest_edges)
    safe_path_safe_cost = sum(edge_cost(edge, "safe") for edge in safe_edges)
    assert safe_path_safe_cost < shortest_path_safe_cost

    same_node_path, same_node_cost = dijkstra(graph, "A", "A", "safe")
    assert same_node_path == ["A"]
    assert same_node_cost == 0

    blocked_graph = build_graph([], undirected=True)
    unreachable_path, unreachable_cost = dijkstra(blocked_graph, "A", "I", "safe")
    assert unreachable_path == []
    assert math.isinf(unreachable_cost)

    assert all(edge.danger_type == "normal" for edge in safe_edges)

    print("All tests passed.")


if __name__ == "__main__":
    main()
