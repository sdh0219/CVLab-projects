from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_OUTPUTS = [
    "documents.jsonl",
    "chunks.jsonl",
    "entities.jsonl",
    "claims.jsonl",
    "relations.jsonl",
    "community_reports.jsonl",
    "index_summary.json",
]

REQUIRED_EXPORTS = [
    "technology_nodes.csv",
    "scenario_nodes.csv",
    "evidence_edges.csv",
    "community_reports.csv",
    "community_reports.json",
    "expert_review_log.csv",
    "corpus_manifest.csv",
    "atlas_quality_report.json",
    "atlas_quality_report.md",
    "graph_nodes.csv",
    "graph_edges_neo4j.csv",
    "graph_visualization.json",
    "atlas.graphml",
    "neo4j_import.cypher",
    "key_technology_assessment.csv",
    "key_technology_assessment.json",
    "key_technology_assessment.md",
    "qa_evaluation_set.csv",
    "qa_evaluation_set.json",
    "qa_evaluation_results.csv",
    "qa_evaluation_results.json",
    "expert_review_priority.csv",
    "topology_communities.csv",
    "topology_communities.json",
    "topology_communities.md",
    "uncertainty_report.json",
    "uncertainty_report.md",
    "submission_manifest.md",
    "submission_manifest.json",
]

REQUIRED_METADATA = [
    "doc_id",
    "title",
    "source_type",
    "source_name",
    "source_url",
    "year",
    "region",
    "disaster_type",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate GraphRAG atlas outputs.")
    parser.add_argument("--corpus", default="data/corpus/sample")
    parser.add_argument("--output", default="outputs/graphrag_index")
    parser.add_argument("--public-file", default="public/atlas/atlas_frontend.json")
    args = parser.parse_args()

    corpus_dir = Path(args.corpus)
    output_dir = Path(args.output)
    export_dir = output_dir / "exports"
    public_file = Path(args.public_file)
    errors: list[str] = []
    warnings: list[str] = []

    for name in REQUIRED_OUTPUTS:
        if not (output_dir / name).exists():
            errors.append(f"missing output file: {name}")
    for name in REQUIRED_EXPORTS:
        if not (export_dir / name).exists():
            errors.append(f"missing export file: exports/{name}")

    summary = read_json(output_dir / "index_summary.json") if (output_dir / "index_summary.json").exists() else {}
    jsonl_counts = {
        "documents": count_jsonl(output_dir / "documents.jsonl"),
        "chunks": count_jsonl(output_dir / "chunks.jsonl"),
        "entities": count_jsonl(output_dir / "entities.jsonl"),
        "claims": count_jsonl(output_dir / "claims.jsonl"),
        "relations": count_jsonl(output_dir / "relations.jsonl"),
        "communities": count_jsonl(output_dir / "community_reports.jsonl"),
    }
    for key, count in jsonl_counts.items():
        if key in summary and summary[key] != count:
            errors.append(f"summary mismatch: {key}={summary[key]} but {count} rows in jsonl")
        if count <= 0:
            errors.append(f"empty jsonl output: {key}")

    corpus_files = sorted(corpus_dir.glob("*.md"))
    if summary.get("documents") and len(corpus_files) != summary.get("documents"):
        errors.append(f"corpus count mismatch: {len(corpus_files)} markdown files but summary documents={summary.get('documents')}")
    metadata_issues = validate_corpus_metadata(corpus_files)
    if metadata_issues:
        errors.extend(metadata_issues[:20])
        if len(metadata_issues) > 20:
            warnings.append(f"{len(metadata_issues) - 20} additional metadata issues omitted")

    expert_rows = count_csv_rows(export_dir / "expert_review_log.csv")
    expected_review_rows = int(summary.get("claims", 0)) + int(summary.get("relations", 0))
    if expert_rows != expected_review_rows:
        errors.append(f"expert_review_log.csv rows={expert_rows}, expected claims+relations={expected_review_rows}")

    scenario_rows = count_csv_rows(export_dir / "scenario_nodes.csv")
    if scenario_rows <= 0:
        errors.append("scenario_nodes.csv has no rows")
    graph_node_rows = count_csv_rows(export_dir / "graph_nodes.csv")
    if graph_node_rows != int(summary.get("entities", 0)):
        errors.append(f"graph_nodes.csv rows={graph_node_rows}, expected entities={summary.get('entities')}")
    graph_edge_rows = count_csv_rows(export_dir / "graph_edges_neo4j.csv")
    if graph_edge_rows != int(summary.get("relations", 0)):
        errors.append(f"graph_edges_neo4j.csv rows={graph_edge_rows}, expected relations={summary.get('relations')}")
    tech_assessment_rows = count_csv_rows(export_dir / "key_technology_assessment.csv")
    if tech_assessment_rows <= 0:
        errors.append("key_technology_assessment.csv has no rows")
    qa_rows = count_csv_rows(export_dir / "qa_evaluation_set.csv")
    if qa_rows < 3:
        errors.append("qa_evaluation_set.csv should contain at least 3 benchmark questions")
    qa_result_rows = count_csv_rows(export_dir / "qa_evaluation_results.csv")
    if qa_result_rows != qa_rows:
        errors.append(f"qa_evaluation_results.csv rows={qa_result_rows}, expected qa rows={qa_rows}")
    topology_rows = count_csv_rows(export_dir / "topology_communities.csv")
    if topology_rows <= 0:
        errors.append("topology_communities.csv has no rows")
    uncertainty = read_json(export_dir / "uncertainty_report.json")
    if not uncertainty.get("items"):
        errors.append("uncertainty_report.json has no uncertainty items")

    if public_file.exists():
        public_snapshot = read_json(public_file)
        frontend_summary = public_snapshot.get("summary", {})
        for key in ["documents", "entities", "claims", "relations", "communities"]:
            if frontend_summary.get(key) != summary.get(key):
                errors.append(f"frontend snapshot mismatch: {key}")
        if not public_snapshot.get("topologyCommunities"):
            errors.append("frontend snapshot missing topologyCommunities")
        if not public_snapshot.get("qaResults"):
            errors.append("frontend snapshot missing qaResults")
    else:
        warnings.append(f"frontend snapshot not found: {public_file}")

    result = {
        "status": "failed" if errors else "passed",
        "summary": summary,
        "jsonl_counts": jsonl_counts,
        "expert_review_rows": expert_rows,
        "scenario_rows": scenario_rows,
        "graph_node_rows": graph_node_rows,
        "graph_edge_rows": graph_edge_rows,
        "tech_assessment_rows": tech_assessment_rows,
        "qa_rows": qa_rows,
        "qa_result_rows": qa_result_rows,
        "topology_rows": topology_rows,
        "uncertainty_items": len(uncertainty.get("items", [])),
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        sys.exit(1)


def parse_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, flags=re.S)
    if not match:
        return {}
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata


def validate_corpus_metadata(paths: list[Path]) -> list[str]:
    issues: list[str] = []
    seen_doc_ids: set[str] = set()
    for path in paths:
        metadata = parse_frontmatter(path.read_text(encoding="utf-8"))
        if not metadata:
            issues.append(f"{path.name}: missing frontmatter")
            continue
        doc_id = metadata.get("doc_id", "")
        if doc_id in seen_doc_ids:
            issues.append(f"{path.name}: duplicate doc_id {doc_id}")
        seen_doc_ids.add(doc_id)
        missing = [field for field in REQUIRED_METADATA if not metadata.get(field)]
        if missing:
            issues.append(f"{path.name}: missing metadata {', '.join(missing)}")
    return issues


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return max(0, sum(1 for _ in csv.reader(handle)) - 1)


if __name__ == "__main__":
    main()
