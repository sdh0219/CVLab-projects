from __future__ import annotations

from collections import Counter

from .models import CommunityReport, Document, Entity, Relation


def build_communities(
    entities: list[Entity], relations: list[Relation], documents: list[Document]
) -> list[CommunityReport]:
    entity_map = {entity.entity_id: entity for entity in entities}
    doc_titles = {doc.doc_id: doc.title for doc in documents}
    tech_entities = [entity for entity in entities if entity.entity_type == "AITech"]
    reports: list[CommunityReport] = []
    for index, tech in enumerate(tech_entities, start=1):
        component_relations = [
            relation
            for relation in relations
            if relation.source == tech.entity_id or relation.target == tech.entity_id
        ]
        if not component_relations:
            continue
        component = {tech.entity_id}
        for relation in component_relations:
            component.add(relation.source)
            component.add(relation.target)
        docs = Counter(relation.doc_id for relation in component_relations)
        entity_names = [entity_map[item].name for item in sorted(component) if item in entity_map]
        tech_names = [tech.name]
        disaster_names = [
            entity_map[item].name
            for item in sorted(component)
            if item in entity_map and entity_map[item].entity_type == "DisasterType"
        ]
        title = tech.name
        summary = summarize_community(title, tech_names, disaster_names, component_relations)
        open_questions = infer_open_questions(component, entity_map, component_relations)
        evidence_strength = round(
            min(1.0, (len(component_relations) / 12) * 0.55 + (len(docs) / 8) * 0.45),
            3,
        )
        reports.append(
            CommunityReport(
                community_id=f"C{index:03d}",
                title=title,
                entities=tuple(entity_names),
                relation_ids=tuple(relation.relation_id for relation in component_relations),
                representative_docs=tuple(
                    f"{doc_id}: {doc_titles.get(doc_id, doc_id)}" for doc_id, _ in docs.most_common(5)
                ),
                summary=summary,
                evidence_strength=evidence_strength,
                open_questions=tuple(open_questions),
            )
        )
    return reports


def summarize_community(
    title: str, tech_names: list[str], disaster_names: list[str], relations: list[Relation]
) -> str:
    relation_types = Counter(relation.relation_type for relation in relations)
    tech_text = "、".join(tech_names[:4]) if tech_names else title
    disaster_text = "、".join(disaster_names[:4]) if disaster_names else "地震灾害场景"
    relation_text = "、".join(name for name, _ in relation_types.most_common(4))
    return (
        f"该社区围绕{tech_text}展开，主要关联{disaster_text}。"
        f"当前证据关系以{relation_text}为主，适合进一步追踪关键技术、应用任务、数据依赖和验证案例。"
    )


def infer_open_questions(
    component: set[str], entity_map: dict[str, Entity], relations: list[Relation]
) -> list[str]:
    entity_types = {entity_map[item].entity_type for item in component if item in entity_map}
    relation_types = {relation.relation_type for relation in relations}
    questions: list[str] = []
    if "Case" not in entity_types and "VALIDATED_IN" not in relation_types:
        questions.append("缺少真实灾害案例或工程部署证据。")
    if "Dataset" not in entity_types:
        questions.append("需要补充数据源、数据质量和可复现实验条件。")
    if "Limitation" not in entity_types:
        questions.append("需要抽取技术边界、泛化风险和部署限制。")
    if not questions:
        questions.append("需要由专家复核该社区是否构成稳定关键技术方向。")
    return questions[:3]
