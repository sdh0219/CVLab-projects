from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


SOURCE_LABELS = {
    "paper": ("地震论文与综述", "提供地震AI技术术语、方法演化和实验指标"),
    "patent": ("地震相关专利", "识别地震预警、震损评估和应急决策的工程转化路径"),
    "project": ("地震示范项目", "识别地震预警、遥感评估和风险建模的部署能力"),
    "policy": ("地震政策预案", "限定地震应急治理任务、合规边界和应用优先级"),
    "case": ("地震案例", "验证技术是否进入真实地震处置和震后评估链条"),
    "standard": ("地震适用标准", "提供预警发布、应急管理、传感器和互操作规范"),
    "report": ("地震相关报告", "补充震害风险、生命线韧性和国际实践证据"),
}

EARTHQUAKE_TARGET_PER_SOURCE = 7


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish GraphRAG outputs as a frontend snapshot.")
    parser.add_argument("--output", default="outputs/graphrag_index")
    parser.add_argument("--public-dir", default="public/atlas")
    parser.add_argument("--config", default="config/ontology.json")
    args = parser.parse_args()

    output_dir = Path(args.output)
    public_dir = Path(args.public_dir)
    config_path = Path(args.config)
    export_dir = output_dir / "exports"

    summary = read_json(output_dir / "index_summary.json")
    ontology = read_json(config_path)
    documents = read_jsonl(output_dir / "documents.jsonl")
    communities = read_json(export_dir / "community_reports.json")
    quality = read_json(export_dir / "atlas_quality_report.json")
    assessments = read_json(export_dir / "key_technology_assessment.json")
    graph = read_json(export_dir / "graph_visualization.json")
    relations = read_jsonl(output_dir / "relations.jsonl")
    topology = read_optional_json(export_dir / "topology_communities.json", [])
    uncertainty = read_optional_json(export_dir / "uncertainty_report.json", {})
    qa_results = read_optional_json(export_dir / "qa_evaluation_results.json", [])
    export_tables = describe_exports(export_dir)
    graph_data = build_frontend_graph_data(graph, relations, documents)

    source_counts = Counter(str(item.get("source_type", "unknown")) for item in documents)
    corpus_layers = []
    for source_type, count in sorted(source_counts.items()):
        label, role = SOURCE_LABELS.get(source_type, (source_type, "待补充语料角色说明"))
        corpus_layers.append(
            {
                "source_type": source_type,
                "name": label,
                "count": count,
                "examples": f"{count} 条整理语料",
                "role": role,
                "readiness": 100
                if count >= EARTHQUAKE_TARGET_PER_SOURCE
                else round(count / EARTHQUAKE_TARGET_PER_SOURCE * 100),
            }
        )

    community_cards = []
    for report in communities:
        relation_ids = report.get("relation_ids", [])
        representative_docs = report.get("representative_docs", [])
        community_cards.append(
            {
                "name": report.get("title", ""),
                "evidence": round(float(report.get("evidence_strength", 0)) * 100),
                "evidenceCount": len(relation_ids),
                "documents": len(representative_docs),
                "summary": report.get("summary", ""),
                "openQuestion": first_or_default(report.get("open_questions"), "待专家复核。"),
            }
        )

    snapshot = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "summary": summary,
        "sourceTypes": sorted(source_counts.keys()),
        "entityTypes": list(ontology.get("entities", {}).keys()),
        "relationTypes": sorted({rule.get("relation_type", "") for rule in ontology.get("relation_rules", [])}),
        "corpusLayers": corpus_layers,
        "communities": community_cards,
        "exports": export_tables,
        "gaps": quality.get("technology_gaps", []),
        "topTechnologies": assessments[:10] if isinstance(assessments, list) else [],
        "topologyCommunities": topology[:10] if isinstance(topology, list) else [],
        "qaResults": qa_results if isinstance(qa_results, list) else [],
        "uncertainty": {
            "itemCount": len(uncertainty.get("items", [])) if isinstance(uncertainty, dict) else 0,
            "highPriorityCount": sum(
                1 for item in uncertainty.get("items", []) if item.get("risk_level") == "high"
            )
            if isinstance(uncertainty, dict)
            else 0,
        },
        "graph": {
            "nodes": len(graph.get("nodes", [])) if isinstance(graph, dict) else 0,
            "edges": len(graph.get("edges", [])) if isinstance(graph, dict) else 0,
        },
        "graphData": graph_data,
        "qualityNotes": quality.get("notes", []),
    }

    public_dir.mkdir(parents=True, exist_ok=True)
    (public_dir / "atlas_frontend.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (public_dir / "index_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (public_dir / "graph_visualization.json").write_text(
        json.dumps(graph_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"public_snapshot": str(public_dir / "atlas_frontend.json")}, ensure_ascii=False, indent=2))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_optional_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def describe_exports(export_dir: Path) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for path in sorted(export_dir.iterdir()):
        if not path.is_file() or path.suffix not in {".csv", ".json"}:
            continue
        if path.suffix == ".csv":
            headers, rows = read_csv_header_and_count(path)
            tables.append({"name": path.name, "fields": ", ".join(headers), "rows": rows})
        else:
            data = read_json(path)
            rows = len(data) if isinstance(data, list) else 1
            tables.append({"name": path.name, "fields": "json", "rows": rows})
    return tables


def read_csv_header_and_count(path: Path) -> tuple[list[str], int]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        headers = next(reader, [])
        return headers, sum(1 for _ in reader)


def build_frontend_graph_data(
    graph: Any, relations: list[dict[str, Any]], documents: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(graph, dict):
        return {"nodes": [], "edges": []}

    relation_by_id = {str(row.get("relation_id", "")): row for row in relations}
    document_by_id = {str(row.get("doc_id", "")): row for row in documents}

    nodes: list[dict[str, Any]] = []
    for node in graph.get("nodes", []):
        if not isinstance(node, dict):
            continue
        nodes.append(
            {
                "id": node.get("id"),
                "label": node.get("label") or node.get("name") or node.get("id"),
                "name": node.get("label") or node.get("name") or node.get("id"),
                "type": node.get("type") or node.get("entity_type"),
                "entity_type": node.get("type") or node.get("entity_type"),
                "community": node.get("community_id") or node.get("community"),
                "description": node.get("description", ""),
                "evidence_count": node.get("evidence_count", 0),
                "relation_count": node.get("relation_count", 0),
                "review_status": node.get("review_status", "pending"),
                "score": node.get("score"),
            }
        )

    edges: list[dict[str, Any]] = []
    for edge in graph.get("edges", []):
        if not isinstance(edge, dict):
            continue
        relation_id = str(edge.get("id") or edge.get("relation_id") or "")
        relation = relation_by_id.get(relation_id, {})
        doc_id = str(edge.get("doc_id") or relation.get("doc_id") or "")
        document = document_by_id.get(doc_id, {})
        metadata = document.get("metadata", {}) if isinstance(document.get("metadata"), dict) else {}
        relation_type = edge.get("type") or edge.get("relation_type") or relation.get("relation_type")
        edges.append(
            {
                "id": relation_id,
                "source": edge.get("source") or relation.get("source"),
                "target": edge.get("target") or relation.get("target"),
                "relation": relation_type,
                "relation_type": relation_type,
                "label": relation_type,
                "confidence": edge.get("confidence", relation.get("confidence")),
                "evidence_text": relation.get("evidence_text", ""),
                "doc_id": doc_id,
                "chunk_id": relation.get("chunk_id", ""),
                "source_name": metadata.get("source_name") or document.get("title") or doc_id,
                "review_status": edge.get("review_status") or relation.get("review_status") or "pending",
            }
        )

    return {"nodes": nodes, "edges": edges}

def first_or_default(value: object, default: str) -> str:
    if isinstance(value, list) and value:
        return str(value[0])
    if isinstance(value, tuple) and value:
        return str(value[0])
    return default


if __name__ == "__main__":
    main()



