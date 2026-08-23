from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import datetime
from html import escape
from pathlib import Path

from .community import build_communities
from .extractor import RuleBasedExtractor
from .io_utils import chunk_document, load_documents, read_json, write_json, write_jsonl
from .llm_extractor import HybridExtractor, LLMExtractor
from .models import Claim, CommunityReport, Document, Entity, Relation, to_dict


def run_index(
    config_path: Path,
    corpus_dir: Path,
    output_dir: Path,
    extractor_mode: str = "rule",
    max_chunks: int | None = None,
) -> dict:
    ontology = read_json(config_path)
    documents = load_documents(corpus_dir)
    chunks = [chunk for document in documents for chunk in chunk_document(document)]
    if max_chunks is not None:
        chunks = chunks[:max_chunks]
    extractor = build_extractor(ontology, extractor_mode)
    entities = extractor.entities
    claims, relations = extractor.extract(chunks)
    reports = build_communities(entities, relations, documents)
    extractor_stats = getattr(extractor, "stats", {"extractor": extractor_mode})

    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "documents.jsonl", [to_dict(item) for item in documents])
    write_jsonl(output_dir / "chunks.jsonl", [to_dict(item) for item in chunks])
    write_jsonl(output_dir / "entities.jsonl", [to_dict(item) for item in entities])
    write_jsonl(output_dir / "claims.jsonl", [to_dict(item) for item in claims])
    write_jsonl(output_dir / "relations.jsonl", [to_dict(item) for item in relations])
    write_jsonl(output_dir / "community_reports.jsonl", [to_dict(item) for item in reports])

    write_json(
        output_dir / "index_summary.json",
        {
            "documents": len(documents),
            "chunks": len(chunks),
            "max_chunks": max_chunks,
            "entities": len(entities),
            "claims": len(claims),
            "relations": len(relations),
            "communities": len(reports),
            **extractor_stats,
        },
    )
    write_csv_exports(output_dir, documents, entities, claims, relations, reports)
    write_quality_report(output_dir, documents, entities, claims, relations, reports)
    return {
        "documents": len(documents),
        "chunks": len(chunks),
        "max_chunks": max_chunks,
        "entities": len(entities),
        "claims": len(claims),
        "relations": len(relations),
        "communities": len(reports),
        **extractor_stats,
    }


def build_extractor(ontology: dict, extractor_mode: str):
    normalized = extractor_mode.lower().strip()
    if normalized == "rule":
        extractor = RuleBasedExtractor(ontology)
        extractor.stats = {"extractor": "rule"}
        return extractor
    if normalized == "llm":
        return LLMExtractor.from_env(ontology, ignore_errors=False)
    if normalized == "hybrid":
        return HybridExtractor(ontology)
    raise ValueError(f"Unsupported extractor mode: {extractor_mode}. Use rule, llm, or hybrid.")


def write_csv_exports(
    output_dir: Path,
    documents: list[Document],
    entities: list[Entity],
    claims: list[Claim],
    relations: list[Relation],
    reports: list[CommunityReport],
) -> None:
    export_dir = output_dir / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    entity_map = {entity.entity_id: entity for entity in entities}
    relation_counts = count_entity_relations(relations)
    evidence_counts = count_entity_evidence(relations)

    with (export_dir / "technology_nodes.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "entity_id",
                "name",
                "entity_type",
                "aliases",
                "relation_count",
                "evidence_count",
                "evidence_score",
                "expert_status",
            ],
        )
        writer.writeheader()
        for entity in entities:
            if entity.entity_type in {"AITech", "Model", "Dataset", "Task"}:
                relation_count = relation_counts[entity.entity_id]
                writer.writerow(
                    {
                        "entity_id": entity.entity_id,
                        "name": entity.name,
                        "entity_type": entity.entity_type,
                        "aliases": ";".join(entity.aliases),
                        "relation_count": relation_count,
                        "evidence_count": evidence_counts[entity.entity_id],
                        "evidence_score": evidence_score(relation_count),
                        "expert_status": "pending",
                    }
                )

    with (export_dir / "scenario_nodes.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "entity_id",
                "name",
                "entity_type",
                "aliases",
                "relation_count",
                "evidence_count",
                "policy_priority",
                "expert_status",
            ],
        )
        writer.writeheader()
        for entity in entities:
            if entity.entity_type in {"DisasterType", "Scenario", "Policy"}:
                writer.writerow(
                    {
                        "entity_id": entity.entity_id,
                        "name": entity.name,
                        "entity_type": entity.entity_type,
                        "aliases": ";".join(entity.aliases),
                        "relation_count": relation_counts[entity.entity_id],
                        "evidence_count": evidence_counts[entity.entity_id],
                        "policy_priority": "pending_review",
                        "expert_status": "pending",
                    }
                )

    with (export_dir / "evidence_edges.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "relation_id",
                "source",
                "source_name",
                "source_type",
                "target",
                "target_name",
                "target_type",
                "relation_type",
                "doc_id",
                "chunk_id",
                "confidence",
                "evidence_text",
                "expert_status",
            ],
        )
        writer.writeheader()
        for relation in relations:
            source = entity_map.get(relation.source)
            target = entity_map.get(relation.target)
            writer.writerow(
                {
                    **to_dict(relation),
                    "source_name": source.name if source else relation.source,
                    "source_type": source.entity_type if source else "unknown",
                    "target_name": target.name if target else relation.target,
                    "target_type": target.entity_type if target else "unknown",
                    "expert_status": "pending",
                }
            )

    with (export_dir / "community_reports.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "community_id",
                "title",
                "entities",
                "evidence_strength",
                "representative_docs",
                "summary",
                "open_questions",
            ],
        )
        writer.writeheader()
        for report in reports:
            writer.writerow(
                {
                    "community_id": report.community_id,
                    "title": report.title,
                    "entities": ";".join(report.entities),
                    "evidence_strength": report.evidence_strength,
                    "representative_docs": ";".join(report.representative_docs),
                    "summary": report.summary,
                    "open_questions": ";".join(report.open_questions),
                }
            )

    write_json(export_dir / "community_reports.json", [to_dict(report) for report in reports])
    write_expert_review_log(export_dir, claims, relations)
    write_corpus_manifest(export_dir, documents)
    write_graph_exports(export_dir, entities, relations, reports)
    write_technology_assessment(export_dir, entities, relations, reports)
    write_query_evaluation_set(export_dir, entities, relations, reports)
    write_expert_review_priority(export_dir, claims, relations, entities)


def write_expert_review_log(export_dir: Path, claims: list[Claim], relations: list[Relation]) -> None:
    with (export_dir / "expert_review_log.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "review_item_id",
                "item_type",
                "claim_id",
                "relation_id",
                "doc_id",
                "chunk_id",
                "reviewer",
                "decision",
                "comment",
                "revision",
                "timestamp",
            ],
        )
        writer.writeheader()
        for claim in claims:
            writer.writerow(
                {
                    "review_item_id": claim.claim_id,
                    "item_type": "claim",
                    "claim_id": claim.claim_id,
                    "relation_id": "",
                    "doc_id": claim.doc_id,
                    "chunk_id": claim.chunk_id,
                    "reviewer": "",
                    "decision": "pending",
                    "comment": "",
                    "revision": 1,
                    "timestamp": "",
                }
            )
        for relation in relations:
            writer.writerow(
                {
                    "review_item_id": relation.relation_id,
                    "item_type": "relation",
                    "claim_id": "",
                    "relation_id": relation.relation_id,
                    "doc_id": relation.doc_id,
                    "chunk_id": relation.chunk_id,
                    "reviewer": "",
                    "decision": "pending",
                    "comment": "",
                    "revision": 1,
                    "timestamp": "",
                }
            )


def write_corpus_manifest(export_dir: Path, documents: list[Document]) -> None:
    with (export_dir / "corpus_manifest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "doc_id",
                "title",
                "source_type",
                "source_name",
                "source_url",
                "year",
                "region",
                "disaster_type",
                "path",
                "body_chars",
                "has_source_url",
                "quality_status",
                "curation_note",
            ],
        )
        writer.writeheader()
        for document in documents:
            source_url = document.metadata.get("source_url", "").strip()
            writer.writerow(
                {
                    "doc_id": document.doc_id,
                    "title": document.title,
                    "source_type": document.source_type,
                    "source_name": document.metadata.get("source_name", ""),
                    "source_url": source_url,
                    "year": document.year,
                    "region": document.region,
                    "disaster_type": document.disaster_type,
                    "path": document.path,
                    "body_chars": len(document.text),
                    "has_source_url": "yes" if source_url else "no",
                    "quality_status": "needs_source_review" if not source_url else "source_traced",
                    "curation_note": "中文整理稿，需保留来源追溯并在正式报告中标明非原文全文转载",
                }
            )


def write_graph_exports(
    export_dir: Path,
    entities: list[Entity],
    relations: list[Relation],
    reports: list[CommunityReport],
) -> None:
    entity_map = {entity.entity_id: entity for entity in entities}
    relation_counts = count_entity_relations(relations)
    evidence_counts = count_entity_evidence(relations)
    community_by_entity_name = community_membership_by_name(reports)

    with (export_dir / "graph_nodes.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "entity_id:ID",
                "name",
                ":LABEL",
                "entity_type",
                "aliases",
                "relation_count:int",
                "evidence_count:int",
                "community_id",
                "expert_status",
            ],
        )
        writer.writeheader()
        for entity in entities:
            writer.writerow(
                {
                    "entity_id:ID": entity.entity_id,
                    "name": entity.name,
                    ":LABEL": entity.entity_type,
                    "entity_type": entity.entity_type,
                    "aliases": ";".join(entity.aliases),
                    "relation_count:int": relation_counts[entity.entity_id],
                    "evidence_count:int": evidence_counts[entity.entity_id],
                    "community_id": community_by_entity_name.get(entity.name, ""),
                    "expert_status": "pending",
                }
            )

    with (export_dir / "graph_edges_neo4j.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                ":START_ID",
                ":END_ID",
                ":TYPE",
                "relation_id",
                "doc_id",
                "chunk_id",
                "confidence:float",
                "evidence_text",
                "expert_status",
            ],
        )
        writer.writeheader()
        for relation in relations:
            writer.writerow(
                {
                    ":START_ID": relation.source,
                    ":END_ID": relation.target,
                    ":TYPE": relation.relation_type,
                    "relation_id": relation.relation_id,
                    "doc_id": relation.doc_id,
                    "chunk_id": relation.chunk_id,
                    "confidence:float": relation.confidence,
                    "evidence_text": relation.evidence_text,
                    "expert_status": "pending",
                }
            )

    write_json(
        export_dir / "graph_visualization.json",
        {
            "nodes": [
                {
                    "id": entity.entity_id,
                    "label": entity.name,
                    "type": entity.entity_type,
                    "relation_count": relation_counts[entity.entity_id],
                    "evidence_count": evidence_counts[entity.entity_id],
                    "community_id": community_by_entity_name.get(entity.name, ""),
                }
                for entity in entities
            ],
            "edges": [
                {
                    "id": relation.relation_id,
                    "source": relation.source,
                    "target": relation.target,
                    "type": relation.relation_type,
                    "confidence": relation.confidence,
                    "doc_id": relation.doc_id,
                }
                for relation in relations
            ],
        },
    )
    write_graphml(export_dir / "atlas.graphml", entities, relations, relation_counts, evidence_counts)
    write_neo4j_import_cypher(export_dir / "neo4j_import.cypher")


def write_technology_assessment(
    export_dir: Path,
    entities: list[Entity],
    relations: list[Relation],
    reports: list[CommunityReport],
) -> list[dict]:
    entity_map = {entity.entity_id: entity for entity in entities}
    community_by_title = {report.title: report.community_id for report in reports}
    rows: list[dict] = []
    for tech in [entity for entity in entities if entity.entity_type == "AITech"]:
        tech_relations = [
            relation
            for relation in relations
            if relation.source == tech.entity_id or relation.target == tech.entity_id
        ]
        relation_types = {relation.relation_type for relation in tech_relations}
        disaster_ids = related_targets(tech.entity_id, tech_relations, entity_map, {"DisasterType"})
        scenario_ids = related_targets(tech.entity_id, tech_relations, entity_map, {"Scenario"})
        doc_ids = {relation.doc_id for relation in tech_relations}
        has_dataset_dependency = "DEPENDS_ON" in relation_types
        has_case_validation = "VALIDATED_IN" in relation_types
        has_limitation = "LIMITED_BY" in relation_types
        score = key_technology_score(
            evidence_doc_count=len(doc_ids),
            disaster_count=len(disaster_ids),
            scenario_count=len(scenario_ids),
            has_dataset_dependency=has_dataset_dependency,
            has_case_validation=has_case_validation,
            has_limitation=has_limitation,
        )
        missing = []
        if not has_case_validation:
            missing.append("缺少案例验证")
        if not has_dataset_dependency:
            missing.append("缺少数据依赖")
        if not has_limitation:
            missing.append("缺少限制条件")
        row = {
            "tech_id": tech.entity_id,
            "name": tech.name,
            "community_id": community_by_title.get(tech.name, ""),
            "relation_count": len(tech_relations),
            "evidence_doc_count": len(doc_ids),
            "disaster_coverage": len(disaster_ids),
            "scenario_coverage": len(scenario_ids),
            "has_dataset_dependency": has_dataset_dependency,
            "has_case_validation": has_case_validation,
            "has_limitation": has_limitation,
            "key_tech_score": score,
            "maturity_level": maturity_level(score, has_case_validation),
            "review_priority": review_priority(score, missing),
            "missing_evidence": "；".join(missing),
        }
        rows.append(row)
    rows.sort(key=lambda item: (item["key_tech_score"], item["relation_count"]), reverse=True)

    with (export_dir / "key_technology_assessment.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)
    write_json(export_dir / "key_technology_assessment.json", rows)
    write_technology_assessment_markdown(export_dir / "key_technology_assessment.md", rows)
    return rows


def write_query_evaluation_set(
    export_dir: Path,
    entities: list[Entity],
    relations: list[Relation],
    reports: list[CommunityReport],
) -> None:
    tech_entities = [entity for entity in entities if entity.entity_type == "AITech"]
    relation_count = count_entity_relations(relations)
    top_tech = sorted(tech_entities, key=lambda entity: relation_count[entity.entity_id], reverse=True)[:5]
    rows: list[dict] = [
        {
            "question_id": "q_global_001",
            "mode": "global",
            "question": "地震灾害AI防灾减灾领域有哪些关键技术社区？",
            "expected_answer_focus": "应综合 community_reports，列出地震专题技术社区、代表证据和待复核问题。",
            "expected_evidence": ";".join(report.community_id for report in reports[:5]),
            "review_status": "pending",
        },
        {
            "question_id": "q_gap_001",
            "mode": "gap",
            "question": "地震灾害场景下哪些AI技术缺少真实案例验证？",
            "expected_answer_focus": "应依据 VALIDATED_IN 缺失情况返回需补地震案例验证的技术。",
            "expected_evidence": "key_technology_assessment.csv",
            "review_status": "pending",
        },
    ]
    for index, tech in enumerate(top_tech, start=1):
        relation_ids = [
            relation.relation_id
            for relation in relations
            if relation.source == tech.entity_id or relation.target == tech.entity_id
        ][:10]
        rows.append(
            {
                "question_id": f"q_local_{index:03d}",
                "mode": "local",
                "question": f"{tech.name}在地震灾害防灾减灾中的证据链是什么？",
                "expected_answer_focus": "应返回相关实体、关系类型、来源文档、证据片段和置信度。",
                "expected_evidence": ";".join(relation_ids),
                "review_status": "pending",
            }
        )

    with (export_dir / "qa_evaluation_set.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    write_json(export_dir / "qa_evaluation_set.json", rows)


def write_expert_review_priority(
    export_dir: Path,
    claims: list[Claim],
    relations: list[Relation],
    entities: list[Entity],
) -> None:
    entity_map = {entity.entity_id: entity for entity in entities}
    rows: list[dict] = []
    for relation in relations:
        source = entity_map.get(relation.source)
        target = entity_map.get(relation.target)
        priority = review_item_priority(relation.confidence, relation.relation_type)
        if priority == "normal":
            continue
        rows.append(
            {
                "review_item_id": relation.relation_id,
                "item_type": "relation",
                "priority": priority,
                "reason": review_reason(relation.confidence, relation.relation_type),
                "doc_id": relation.doc_id,
                "chunk_id": relation.chunk_id,
                "source": source.name if source else relation.source,
                "relation_type": relation.relation_type,
                "target": target.name if target else relation.target,
                "confidence": relation.confidence,
                "suggested_decision": "pending_manual_review",
            }
        )
    for claim in claims:
        if claim.confidence >= 0.66:
            continue
        rows.append(
            {
                "review_item_id": claim.claim_id,
                "item_type": "claim",
                "priority": "medium",
                "reason": "声明置信度较低，需要人工确认表述和证据是否一致",
                "doc_id": claim.doc_id,
                "chunk_id": claim.chunk_id,
                "source": "",
                "relation_type": "",
                "target": "",
                "confidence": claim.confidence,
                "suggested_decision": "pending_manual_review",
            }
        )
    rows.sort(key=lambda item: (priority_rank(item["priority"]), -float(item["confidence"])))
    with (export_dir / "expert_review_priority.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "review_item_id",
                "item_type",
                "priority",
                "reason",
                "doc_id",
                "chunk_id",
                "source",
                "relation_type",
                "target",
                "confidence",
                "suggested_decision",
            ],
        )
        writer.writeheader()
        writer.writerows(rows[:300])


def write_quality_report(
    output_dir: Path,
    documents: list[Document],
    entities: list[Entity],
    claims: list[Claim],
    relations: list[Relation],
    reports: list[CommunityReport],
) -> None:
    export_dir = output_dir / "exports"
    required_metadata = [
        "doc_id",
        "title",
        "source_type",
        "source_name",
        "source_url",
        "year",
        "region",
        "disaster_type",
    ]
    missing_metadata = [
        {
            "doc_id": document.doc_id,
            "missing": [field for field in required_metadata if not document.metadata.get(field)],
        }
        for document in documents
        if any(not document.metadata.get(field) for field in required_metadata)
    ]
    relation_type_counts = Counter(relation.relation_type for relation in relations)
    source_type_counts = Counter(document.source_type for document in documents)
    entity_type_counts = Counter(entity.entity_type for entity in entities)
    gaps = technology_gap_rows(entities, relations)
    tech_assessments = technology_assessment_rows(entities, relations, reports)
    export_files = {
        path.name: count_csv_rows(path) if path.suffix == ".csv" else None
        for path in sorted(export_dir.iterdir())
        if path.is_file()
    }
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "counts": {
            "documents": len(documents),
            "entities": len(entities),
            "claims": len(claims),
            "relations": len(relations),
            "communities": len(reports),
        },
        "source_type_counts": dict(sorted(source_type_counts.items())),
        "entity_type_counts": dict(sorted(entity_type_counts.items())),
        "relation_type_counts": dict(sorted(relation_type_counts.items())),
        "missing_metadata": missing_metadata,
        "technology_gaps": gaps,
        "top_technologies": tech_assessments[:10],
        "export_files": export_files,
        "notes": [
            "语料正文为面向GraphRAG抽取的中文整理稿，不是原文全文转载。",
            "expert_status 当前为 pending，需要后续人工或专家复核。",
            "community_reports 当前为本地规则化社区报告，仍可升级为正式GraphRAG社区发现和LLM摘要。",
        ],
    }
    write_json(export_dir / "atlas_quality_report.json", report)
    write_quality_markdown(export_dir / "atlas_quality_report.md", report)


def write_quality_markdown(path: Path, report: dict) -> None:
    counts = report["counts"]
    lines = [
        "# 地震灾害AI防灾减灾关键技术图谱质量报告",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 索引规模",
        "",
        f"- 文档：{counts['documents']}",
        f"- 实体：{counts['entities']}",
        f"- 声明：{counts['claims']}",
        f"- 关系：{counts['relations']}",
        f"- 技术社区：{counts['communities']}",
        "",
        "## 语料类型分布",
        "",
    ]
    for name, count in report["source_type_counts"].items():
        lines.append(f"- {name}: {count}")
    lines.extend(["", "## 待专家复核的技术缺口", ""])
    if report["technology_gaps"]:
        for item in report["technology_gaps"]:
            lines.append(f"- {item['technology']}: {'；'.join(item['missing'])}")
    else:
        lines.append("- 未发现规则层面的核心证据缺口。")
    lines.extend(["", "## 关键技术评分前五", ""])
    for item in report.get("top_technologies", [])[:5]:
        lines.append(
            f"- {item['name']}: {item['key_tech_score']} 分，{item['maturity_level']}，"
            f"证据来源 {item['evidence_doc_count']} 份"
        )
    lines.extend(["", "## 数据质量提示", ""])
    if report["missing_metadata"]:
        for item in report["missing_metadata"][:20]:
            lines.append(f"- {item['doc_id']}: 缺少 {', '.join(item['missing'])}")
    else:
        lines.append("- 所有语料均具备当前要求的核心元数据字段。")
    lines.extend(["", "## 说明", ""])
    for note in report["notes"]:
        lines.append(f"- {note}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def count_entity_relations(relations: list[Relation]) -> Counter:
    counts: Counter = Counter()
    for relation in relations:
        counts[relation.source] += 1
        counts[relation.target] += 1
    return counts


def count_entity_evidence(relations: list[Relation]) -> Counter:
    evidence_docs: defaultdict[str, set[str]] = defaultdict(set)
    for relation in relations:
        evidence_docs[relation.source].add(relation.doc_id)
        evidence_docs[relation.target].add(relation.doc_id)
    return Counter({entity_id: len(doc_ids) for entity_id, doc_ids in evidence_docs.items()})


def evidence_score(relation_count: int) -> float:
    return round(min(1.0, relation_count / 40), 3)


def technology_assessment_rows(
    entities: list[Entity],
    relations: list[Relation],
    reports: list[CommunityReport],
) -> list[dict]:
    entity_map = {entity.entity_id: entity for entity in entities}
    community_by_title = {report.title: report.community_id for report in reports}
    rows: list[dict] = []
    for tech in [entity for entity in entities if entity.entity_type == "AITech"]:
        tech_relations = [
            relation
            for relation in relations
            if relation.source == tech.entity_id or relation.target == tech.entity_id
        ]
        relation_types = {relation.relation_type for relation in tech_relations}
        doc_ids = {relation.doc_id for relation in tech_relations}
        disaster_ids = related_targets(tech.entity_id, tech_relations, entity_map, {"DisasterType"})
        scenario_ids = related_targets(tech.entity_id, tech_relations, entity_map, {"Scenario"})
        has_dataset_dependency = "DEPENDS_ON" in relation_types
        has_case_validation = "VALIDATED_IN" in relation_types
        has_limitation = "LIMITED_BY" in relation_types
        missing = []
        if not has_case_validation:
            missing.append("缺少案例验证")
        if not has_dataset_dependency:
            missing.append("缺少数据依赖")
        if not has_limitation:
            missing.append("缺少限制条件")
        score = key_technology_score(
            len(doc_ids),
            len(disaster_ids),
            len(scenario_ids),
            has_dataset_dependency,
            has_case_validation,
            has_limitation,
        )
        rows.append(
            {
                "tech_id": tech.entity_id,
                "name": tech.name,
                "community_id": community_by_title.get(tech.name, ""),
                "relation_count": len(tech_relations),
                "evidence_doc_count": len(doc_ids),
                "disaster_coverage": len(disaster_ids),
                "scenario_coverage": len(scenario_ids),
                "has_dataset_dependency": has_dataset_dependency,
                "has_case_validation": has_case_validation,
                "has_limitation": has_limitation,
                "key_tech_score": score,
                "maturity_level": maturity_level(score, has_case_validation),
                "review_priority": review_priority(score, missing),
                "missing_evidence": "；".join(missing),
            }
        )
    return sorted(rows, key=lambda item: (item["key_tech_score"], item["relation_count"]), reverse=True)


def key_technology_score(
    evidence_doc_count: int,
    disaster_count: int,
    scenario_count: int,
    has_dataset_dependency: bool,
    has_case_validation: bool,
    has_limitation: bool,
) -> int:
    score = 0
    score += min(25, evidence_doc_count * 2)
    score += min(20, disaster_count * 5)
    score += min(15, scenario_count * 3)
    score += 15 if has_dataset_dependency else 0
    score += 15 if has_case_validation else 0
    score += 10 if has_limitation else 0
    return min(100, score)


def maturity_level(score: int, has_case_validation: bool) -> str:
    if score >= 80 and has_case_validation:
        return "工程验证较充分"
    if score >= 70:
        return "证据较充分但需复核"
    if not has_case_validation:
        return "需补案例验证"
    return "待补充证据"


def review_priority(score: int, missing: list[str]) -> str:
    if "缺少案例验证" in missing and score >= 65:
        return "high"
    if missing:
        return "medium"
    return "normal"


def related_targets(
    tech_id: str,
    relations: list[Relation],
    entity_map: dict[str, Entity],
    entity_types: set[str],
) -> set[str]:
    related: set[str] = set()
    for relation in relations:
        other = ""
        if relation.source == tech_id:
            other = relation.target
        elif relation.target == tech_id:
            other = relation.source
        if other and other in entity_map and entity_map[other].entity_type in entity_types:
            related.add(other)
    return related


def community_membership_by_name(reports: list[CommunityReport]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for report in reports:
        for name in report.entities:
            mapping[name] = report.community_id
    return mapping


def write_technology_assessment_markdown(path: Path, rows: list[dict]) -> None:
    lines = [
        "# 关键技术评分与复核建议",
        "",
        "| 排名 | 技术 | 分数 | 成熟度 | 证据来源 | 缺口 |",
        "|---:|---|---:|---|---:|---|",
    ]
    for index, row in enumerate(rows, start=1):
        lines.append(
            f"| {index} | {row['name']} | {row['key_tech_score']} | {row['maturity_level']} | "
            f"{row['evidence_doc_count']} | {row['missing_evidence'] or '无规则缺口'} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_graphml(
    path: Path,
    entities: list[Entity],
    relations: list[Relation],
    relation_counts: Counter,
    evidence_counts: Counter,
) -> None:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        '<key id="name" for="node" attr.name="name" attr.type="string"/>',
        '<key id="entity_type" for="node" attr.name="entity_type" attr.type="string"/>',
        '<key id="relation_count" for="node" attr.name="relation_count" attr.type="int"/>',
        '<key id="evidence_count" for="node" attr.name="evidence_count" attr.type="int"/>',
        '<key id="relation_type" for="edge" attr.name="relation_type" attr.type="string"/>',
        '<key id="confidence" for="edge" attr.name="confidence" attr.type="double"/>',
        '<key id="doc_id" for="edge" attr.name="doc_id" attr.type="string"/>',
        '<graph id="AI_Disaster_Technology_Atlas" edgedefault="directed">',
    ]
    for entity in entities:
        lines.extend(
            [
                f'<node id="{escape(entity.entity_id)}">',
                f'<data key="name">{escape(entity.name)}</data>',
                f'<data key="entity_type">{escape(entity.entity_type)}</data>',
                f'<data key="relation_count">{relation_counts[entity.entity_id]}</data>',
                f'<data key="evidence_count">{evidence_counts[entity.entity_id]}</data>',
                "</node>",
            ]
        )
    for relation in relations:
        lines.extend(
            [
                f'<edge id="{escape(relation.relation_id)}" source="{escape(relation.source)}" target="{escape(relation.target)}">',
                f'<data key="relation_type">{escape(relation.relation_type)}</data>',
                f'<data key="confidence">{relation.confidence}</data>',
                f'<data key="doc_id">{escape(relation.doc_id)}</data>',
                "</edge>",
            ]
        )
    lines.extend(["</graph>", "</graphml>"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_neo4j_import_cypher(path: Path) -> None:
    lines = [
        "// Put CSV files in Neo4j import directory before running.",
        "CREATE CONSTRAINT atlas_entity_id IF NOT EXISTS FOR (n:AtlasEntity) REQUIRE n.entity_id IS UNIQUE;",
        "",
        "LOAD CSV WITH HEADERS FROM 'file:///graph_nodes.csv' AS row",
        "MERGE (n:AtlasEntity {entity_id: row.`entity_id:ID`})",
        "SET n.name = row.name,",
        "    n.entity_type = row.entity_type,",
        "    n.aliases = row.aliases,",
        "    n.relation_count = toInteger(row.`relation_count:int`),",
        "    n.evidence_count = toInteger(row.`evidence_count:int`),",
        "    n.community_id = row.community_id,",
        "    n.expert_status = row.expert_status;",
        "",
        "LOAD CSV WITH HEADERS FROM 'file:///graph_edges_neo4j.csv' AS row",
        "MATCH (s:AtlasEntity {entity_id: row.`:START_ID`})",
        "MATCH (t:AtlasEntity {entity_id: row.`:END_ID`})",
        "CALL apoc.create.relationship(s, row.`:TYPE`, {",
        "  relation_id: row.relation_id,",
        "  doc_id: row.doc_id,",
        "  chunk_id: row.chunk_id,",
        "  confidence: toFloat(row.`confidence:float`),",
        "  evidence_text: row.evidence_text,",
        "  expert_status: row.expert_status",
        "}, t) YIELD rel",
        "RETURN count(rel);",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def review_item_priority(confidence: float, relation_type: str) -> str:
    if relation_type in {"VALIDATED_IN", "LIMITED_BY"}:
        return "high"
    if confidence < 0.64:
        return "medium"
    return "normal"


def review_reason(confidence: float, relation_type: str) -> str:
    if relation_type == "VALIDATED_IN":
        return "案例验证关系直接影响技术成熟度，需要优先人工确认"
    if relation_type == "LIMITED_BY":
        return "限制条件影响结论边界，需要优先人工确认"
    if confidence < 0.64:
        return "关系置信度较低，需要人工确认"
    return "常规抽样复核"


def priority_rank(priority: str) -> int:
    return {"high": 0, "medium": 1, "normal": 2}.get(priority, 3)


def technology_gap_rows(entities: list[Entity], relations: list[Relation]) -> list[dict]:
    tech_ids = {entity.entity_id: entity.name for entity in entities if entity.entity_type == "AITech"}
    relation_types_by_tech: defaultdict[str, set[str]] = defaultdict(set)
    for relation in relations:
        if relation.source in tech_ids:
            relation_types_by_tech[relation.source].add(relation.relation_type)
        if relation.target in tech_ids:
            relation_types_by_tech[relation.target].add(relation.relation_type)
    required = {
        "VALIDATED_IN": "缺少案例验证",
        "DEPENDS_ON": "缺少数据依赖",
        "LIMITED_BY": "缺少技术限制",
    }
    gaps: list[dict] = []
    for tech_id, tech_name in tech_ids.items():
        missing = [label for relation_type, label in required.items() if relation_type not in relation_types_by_tech[tech_id]]
        if missing:
            gaps.append({"technology_id": tech_id, "technology": tech_name, "missing": missing})
    return gaps


def count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return max(0, sum(1 for _ in csv.reader(handle)) - 1)
