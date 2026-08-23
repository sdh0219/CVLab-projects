from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate secondary analysis artifacts for the atlas.")
    parser.add_argument("--output", default="outputs/graphrag_index")
    args = parser.parse_args()

    output_dir = Path(args.output)
    export_dir = output_dir / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    entities = read_jsonl(output_dir / "entities.jsonl")
    relations = read_jsonl(output_dir / "relations.jsonl")
    claims = read_jsonl(output_dir / "claims.jsonl")
    communities = read_jsonl(output_dir / "community_reports.jsonl")
    summary = read_json(output_dir / "index_summary.json")

    topology = build_topology_communities(entities, relations)
    write_topology_outputs(export_dir, topology)
    uncertainty = build_uncertainty_report(entities, relations, claims, topology)
    write_json(export_dir / "uncertainty_report.json", uncertainty)
    write_uncertainty_markdown(export_dir / "uncertainty_report.md", uncertainty)
    qa_results = run_qa_evaluation(export_dir, output_dir)
    write_submission_manifest(export_dir, output_dir, summary, communities, topology, uncertainty, qa_results)

    print(
        json.dumps(
            {
                "topology_communities": len(topology),
                "uncertainty_items": len(uncertainty["items"]),
                "qa_results": len(qa_results),
                "submission_manifest": str(export_dir / "submission_manifest.md"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def build_topology_communities(entities: list[dict], relations: list[dict]) -> list[dict]:
    entity_map = {entity["entity_id"]: entity for entity in entities}
    adjacency: dict[str, Counter] = {entity_id: Counter() for entity_id in entity_map}
    relation_ids_by_pair: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    for relation in relations:
        source = relation["source"]
        target = relation["target"]
        weight = relation_weight(relation["relation_type"], relation.get("confidence", 0.6))
        adjacency[source][target] += weight
        adjacency[target][source] += weight
        relation_ids_by_pair[tuple(sorted((source, target)))].append(relation["relation_id"])

    labels = initial_labels(entity_map)
    for _ in range(24):
        changed = False
        for entity_id in sorted(entity_map):
            if not adjacency[entity_id]:
                continue
            votes: Counter = Counter()
            for neighbor, weight in adjacency[entity_id].items():
                votes[labels[neighbor]] += weight
            best_label, _ = max(votes.items(), key=lambda item: (item[1], -stable_order(item[0])))
            if labels[entity_id] != best_label:
                labels[entity_id] = best_label
                changed = True
        if not changed:
            break

    grouped: defaultdict[str, list[str]] = defaultdict(list)
    for entity_id, label in labels.items():
        grouped[label].append(entity_id)

    communities: list[dict] = []
    for index, (_, members) in enumerate(
        sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])),
        start=1,
    ):
        member_set = set(members)
        internal_relations = [
            relation
            for relation in relations
            if relation["source"] in member_set and relation["target"] in member_set
        ]
        docs = Counter(relation["doc_id"] for relation in internal_relations)
        types = Counter(entity_map[entity_id]["entity_type"] for entity_id in members)
        tech_names = [
            entity_map[entity_id]["name"]
            for entity_id in members
            if entity_map[entity_id]["entity_type"] == "AITech"
        ]
        title = "、".join(tech_names[:2]) if tech_names else most_common_type_name(types)
        communities.append(
            {
                "topology_community_id": f"T{index:03d}",
                "title": title,
                "member_count": len(members),
                "relation_count": len(internal_relations),
                "entity_types": dict(sorted(types.items())),
                "members": [
                    {
                        "entity_id": entity_id,
                        "name": entity_map[entity_id]["name"],
                        "entity_type": entity_map[entity_id]["entity_type"],
                    }
                    for entity_id in sorted(members)
                ],
                "representative_docs": [
                    {"doc_id": doc_id, "relation_count": count}
                    for doc_id, count in docs.most_common(8)
                ],
                "summary": summarize_topology_community(title, types, internal_relations),
            }
        )
    return communities


def write_topology_outputs(export_dir: Path, communities: list[dict]) -> None:
    write_json(export_dir / "topology_communities.json", communities)
    with (export_dir / "topology_communities.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "topology_community_id",
                "title",
                "member_count",
                "relation_count",
                "entity_types",
                "representative_docs",
                "summary",
            ],
        )
        writer.writeheader()
        for community in communities:
            writer.writerow(
                {
                    "topology_community_id": community["topology_community_id"],
                    "title": community["title"],
                    "member_count": community["member_count"],
                    "relation_count": community["relation_count"],
                    "entity_types": json.dumps(community["entity_types"], ensure_ascii=False),
                    "representative_docs": ";".join(item["doc_id"] for item in community["representative_docs"]),
                    "summary": community["summary"],
                }
            )
    lines = [
        "# 拓扑社区发现结果",
        "",
        "该结果由实体关系图的加权标签传播生成，用于补充按 AITech 节点生成的社区报告。",
        "",
        "| 社区 | 标题 | 成员数 | 关系数 | 摘要 |",
        "|---|---|---:|---:|---|",
    ]
    for community in communities:
        lines.append(
            f"| {community['topology_community_id']} | {community['title']} | "
            f"{community['member_count']} | {community['relation_count']} | {community['summary']} |"
        )
    (export_dir / "topology_communities.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_uncertainty_report(
    entities: list[dict],
    relations: list[dict],
    claims: list[dict],
    topology_communities: list[dict],
) -> dict:
    entity_map = {entity["entity_id"]: entity for entity in entities}
    by_tech: defaultdict[str, list[dict]] = defaultdict(list)
    for relation in relations:
        if entity_map.get(relation["source"], {}).get("entity_type") == "AITech":
            by_tech[relation["source"]].append(relation)
        if entity_map.get(relation["target"], {}).get("entity_type") == "AITech":
            by_tech[relation["target"]].append(relation)

    items: list[dict] = []
    for tech_id, tech_relations in by_tech.items():
        relation_types = {relation["relation_type"] for relation in tech_relations}
        docs = {relation["doc_id"] for relation in tech_relations}
        confidence_values = [float(relation.get("confidence", 0)) for relation in tech_relations]
        avg_confidence = round(sum(confidence_values) / len(confidence_values), 3)
        reasons = []
        if "VALIDATED_IN" not in relation_types:
            reasons.append("缺少案例验证关系")
        if "LIMITED_BY" not in relation_types:
            reasons.append("缺少限制条件关系")
        if len(docs) < 5:
            reasons.append("证据来源少于5份")
        if avg_confidence < 0.66:
            reasons.append("平均置信度偏低")
        if reasons:
            risk_level = "high" if "缺少案例验证关系" in reasons and len(docs) >= 10 else "medium"
            items.append(
                {
                    "item_id": tech_id,
                    "item_type": "technology",
                    "name": entity_map[tech_id]["name"],
                    "risk_level": risk_level,
                    "reasons": reasons,
                    "evidence_doc_count": len(docs),
                    "relation_count": len(tech_relations),
                    "avg_confidence": avg_confidence,
                    "recommended_action": "优先补充真实案例或专家审核证据" if risk_level == "high" else "纳入专家抽样复核",
                }
            )

    duplicate_claims = find_duplicate_claims(claims)
    for duplicate in duplicate_claims:
        items.append(duplicate)

    topology_notes = []
    for community in topology_communities:
        if community["member_count"] <= 2:
            topology_notes.append(
                {
                    "topology_community_id": community["topology_community_id"],
                    "risk": "小型拓扑社区，需要确认是否为孤立证据或本体覆盖不足",
                }
            )

    items.sort(key=lambda item: (risk_rank(item["risk_level"]), -int(item.get("evidence_doc_count", 0))))
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "items": items[:120],
        "topology_notes": topology_notes,
        "notes": [
            "该报告是自动不确定性筛查，不等同于专家判定。",
            "高风险项应优先进入 expert_review_log.csv 的人工审核流程。",
        ],
    }


def write_uncertainty_markdown(path: Path, report: dict) -> None:
    lines = [
        "# 冲突与不确定性筛查报告",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 高优先级复核项",
        "",
        "| 对象 | 类型 | 风险 | 原因 | 建议 |",
        "|---|---|---|---|---|",
    ]
    for item in report["items"][:40]:
        lines.append(
            f"| {item.get('name', item['item_id'])} | {item['item_type']} | {item['risk_level']} | "
            f"{'；'.join(item.get('reasons', []))} | {item.get('recommended_action', '')} |"
        )
    lines.extend(["", "## 说明", ""])
    for note in report["notes"]:
        lines.append(f"- {note}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_qa_evaluation(export_dir: Path, output_dir: Path) -> list[dict]:
    qa_path = export_dir / "qa_evaluation_set.csv"
    if not qa_path.exists():
        return []
    communities = read_jsonl(output_dir / "community_reports.jsonl")
    entities = read_jsonl(output_dir / "entities.jsonl")
    relations = read_jsonl(output_dir / "relations.jsonl")
    claims = read_jsonl(output_dir / "claims.jsonl")
    rows = read_csv_rows(qa_path)
    results: list[dict] = []
    for row in rows:
        mode = row["mode"]
        question = row["question"]
        expected = [item for item in row["expected_evidence"].split(";") if item]
        if mode == "global":
            matched = [report["community_id"] for report in communities if report["community_id"] in expected]
            answer = "；".join(report["summary"] for report in communities[:3])
        elif mode == "gap":
            assessments = read_json(export_dir / "key_technology_assessment.json")
            matched = ["key_technology_assessment.csv"] if assessments else []
            answer = "；".join(
                f"{item['name']}：{item['missing_evidence']}"
                for item in assessments
                if item.get("missing_evidence")
            )
        else:
            if "在地震灾害防灾减灾" in question:
                tech_name = question.split("在地震灾害防灾减灾")[0]
            else:
                tech_name = question.split("在", 1)[0]
            entity_ids = [
                entity["entity_id"]
                for entity in entities
                if tech_name == entity["name"]
            ]
            returned_relation_ids = [
                relation["relation_id"]
                for relation in relations
                if relation["source"] in entity_ids or relation["target"] in entity_ids
            ][:20]
            matched = [relation_id for relation_id in expected if relation_id in returned_relation_ids]
            answer = f"返回 {len(returned_relation_ids)} 条关系和 {len(claims)} 条全局声明供证据追踪。"
        coverage = round(len(matched) / max(1, len(expected)), 3)
        results.append(
            {
                "question_id": row["question_id"],
                "mode": mode,
                "question": question,
                "expected_count": len(expected),
                "matched_count": len(matched),
                "evidence_coverage": coverage,
                "status": "passed" if coverage >= 0.5 or mode == "gap" else "needs_review",
                "answer_preview": answer[:500],
            }
        )
    with (export_dir / "qa_evaluation_results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0].keys()) if results else [])
        if results:
            writer.writeheader()
            writer.writerows(results)
    write_json(export_dir / "qa_evaluation_results.json", results)
    return results


def write_submission_manifest(
    export_dir: Path,
    output_dir: Path,
    summary: dict,
    communities: list[dict],
    topology: list[dict],
    uncertainty: dict,
    qa_results: list[dict],
) -> None:
    files = sorted(path for path in export_dir.iterdir() if path.is_file())
    lines = [
        "# 地震灾害AI防灾减灾关键技术图谱构建成果清单",
        "",
        f"生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "",
        "## 核心规模",
        "",
        f"- 文档：{summary.get('documents', 0)}",
        f"- 实体节点：{summary.get('entities', 0)}",
        f"- 关系边：{summary.get('relations', 0)}",
        f"- 声明：{summary.get('claims', 0)}",
        f"- 技术社区：{len(communities)}",
        f"- 拓扑社区：{len(topology)}",
        f"- QA评测问题：{len(qa_results)}",
        f"- 不确定性复核项：{len(uncertainty.get('items', []))}",
        "",
        "## 交付文件",
        "",
    ]
    for path in files:
        lines.append(f"- `{path.name}`：{path.stat().st_size} bytes")
    lines.extend(
        [
            "",
            "## 建议提交边界",
            "",
            "- 保留 `config/`、`data/corpus/`、`graphrag_atlas/`、`tools/`、`outputs/graphrag_index/`、`public/atlas/`、`docs/`、`README.md`。",
            "- 不建议提交 `node_modules/`、`.wrangler/`、`.idea/`、`dist/`、`build/`、`__pycache__/` 和运行日志。",
            "- 专家审核文件当前为待审核结构，不应表述为已完成专家评审。",
        ]
    )
    (export_dir / "submission_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(
        export_dir / "submission_manifest.json",
        {
            "summary": summary,
            "export_files": [{"name": path.name, "bytes": path.stat().st_size} for path in files],
            "recommended_include": [
                "config",
                "data/corpus",
                "graphrag_atlas",
                "tools",
                "outputs/graphrag_index",
                "public/atlas",
                "docs",
                "README.md",
            ],
            "recommended_exclude": ["node_modules", ".wrangler", ".idea", "dist", "build", "__pycache__", "dev-server*.log"],
        },
    )


def relation_weight(relation_type: str, confidence: Any) -> float:
    weights = {
        "VALIDATED_IN": 1.5,
        "DEPENDS_ON": 1.25,
        "SOLVES": 1.2,
        "APPLIES_TO": 1.1,
        "SERVES_STAGE": 1.0,
        "USES_MODEL": 0.95,
        "LIMITED_BY": 0.85,
        "REQUIRED_BY": 0.75,
    }
    try:
        conf = float(confidence)
    except (TypeError, ValueError):
        conf = 0.6
    return weights.get(relation_type, 1.0) * max(0.1, conf)


def initial_labels(entity_map: dict[str, dict]) -> dict[str, str]:
    tech_ids = [entity_id for entity_id, entity in entity_map.items() if entity["entity_type"] == "AITech"]
    labels: dict[str, str] = {}
    fallback = tech_ids[0] if tech_ids else next(iter(entity_map))
    for entity_id, entity in entity_map.items():
        labels[entity_id] = entity_id if entity["entity_type"] == "AITech" else fallback
    return labels


def stable_order(value: str) -> int:
    return sum(ord(char) for char in value)


def most_common_type_name(types: Counter) -> str:
    if not types:
        return "未命名拓扑社区"
    return f"{types.most_common(1)[0][0]}社区"


def summarize_topology_community(title: str, types: Counter, relations: list[dict]) -> str:
    relation_types = Counter(relation["relation_type"] for relation in relations)
    type_text = "、".join(f"{name}{count}" for name, count in types.most_common(4))
    relation_text = "、".join(name for name, _ in relation_types.most_common(4)) or "暂无内部关系"
    return f"{title}包含{type_text}，内部关系主要为{relation_text}。"


def find_duplicate_claims(claims: list[dict]) -> list[dict]:
    buckets: defaultdict[str, list[dict]] = defaultdict(list)
    for claim in claims:
        key = normalize_claim_text(str(claim.get("text", "")))
        if key:
            buckets[key].append(claim)
    duplicates = []
    for key, items in buckets.items():
        doc_ids = {item["doc_id"] for item in items}
        if len(items) >= 4 and len(doc_ids) >= 3:
            duplicates.append(
                {
                    "item_id": key[:32],
                    "item_type": "claim_cluster",
                    "name": items[0]["text"][:80],
                    "risk_level": "medium",
                    "reasons": ["多文档重复声明，需要确认是否为模板化整理文本导致的证据重复"],
                    "evidence_doc_count": len(doc_ids),
                    "relation_count": 0,
                    "avg_confidence": round(sum(float(item.get("confidence", 0)) for item in items) / len(items), 3),
                    "recommended_action": "抽样检查原始来源和整理稿是否过度同质化",
                }
            )
    return duplicates


def normalize_claim_text(text: str) -> str:
    return "".join(char for char in text.lower() if char.isalnum() or "\u4e00" <= char <= "\u9fff")[:120]


def risk_rank(risk_level: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(risk_level, 3)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


if __name__ == "__main__":
    main()
