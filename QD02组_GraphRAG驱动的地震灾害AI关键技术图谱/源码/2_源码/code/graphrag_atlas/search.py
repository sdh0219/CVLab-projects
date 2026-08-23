from __future__ import annotations

import json
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Missing index file: {path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def global_search(output_dir: Path, query: str) -> dict:
    reports = load_jsonl(output_dir / "community_reports.jsonl")
    scored = sorted(
        (
            (
                score_text(
                    query,
                    " ".join(
                        [
                            report["summary"],
                            report["title"],
                            " ".join(report.get("entities", [])),
                            " ".join(report.get("representative_docs", [])),
                        ]
                    ),
                ),
                report,
            )
            for report in reports
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    selected = [report for score, report in scored if score > 0][:5] or [report for _, report in scored[:3]]
    return {
        "mode": "global",
        "query": query,
        "answer": "；".join(report["summary"] for report in selected),
        "community_reports": selected,
    }


def local_search(output_dir: Path, entity_name: str) -> dict:
    entities = load_jsonl(output_dir / "entities.jsonl")
    relations = load_jsonl(output_dir / "relations.jsonl")
    claims = load_jsonl(output_dir / "claims.jsonl")
    normalized_entity_name = entity_name.lower()
    matches = [
        entity
        for entity in entities
        if normalized_entity_name in entity["entity_id"].lower()
        or normalized_entity_name in entity["name"].lower()
        or any(normalized_entity_name in alias.lower() for alias in entity.get("aliases", []))
    ]
    if not matches:
        return {"mode": "local", "entity": entity_name, "matches": [], "relations": [], "claims": []}
    entity_ids = {entity["entity_id"] for entity in matches}
    neighborhood = [
        relation
        for relation in relations
        if relation["source"] in entity_ids or relation["target"] in entity_ids
    ]
    relevant_claims = [
        claim for claim in claims if any(entity_id in claim["entities"] for entity_id in entity_ids)
    ]
    return {
        "mode": "local",
        "entity": entity_name,
        "matches": matches,
        "relations": neighborhood[:20],
        "claims": relevant_claims[:20],
    }


def gap_search(output_dir: Path) -> dict:
    entities = load_jsonl(output_dir / "entities.jsonl")
    relations = load_jsonl(output_dir / "relations.jsonl")
    relation_types_by_entity: dict[str, set[str]] = {}
    for relation in relations:
        relation_types_by_entity.setdefault(relation["source"], set()).add(relation["relation_type"])
        relation_types_by_entity.setdefault(relation["target"], set()).add(relation["relation_type"])
    tech_entities = [entity for entity in entities if entity["entity_type"] == "AITech"]
    gaps = []
    for entity in tech_entities:
        relation_types = relation_types_by_entity.get(entity["entity_id"], set())
        missing = []
        if "VALIDATED_IN" not in relation_types:
            missing.append("缺少案例验证")
        if "DEPENDS_ON" not in relation_types:
            missing.append("缺少数据依赖证据")
        if "LIMITED_BY" not in relation_types:
            missing.append("缺少技术限制证据")
        if missing:
            gaps.append({"technology": entity["name"], "missing": missing})
    return {"mode": "gap", "gaps": gaps}


def score_text(query: str, text: str) -> int:
    query_tokens = set(tokenize(query))
    text_tokens = set(tokenize(text))
    return len(query_tokens & text_tokens)


def tokenize(text: str) -> list[str]:
    normalized = text.lower()
    tokens = []
    buffer = ""
    for char in normalized:
        if "\u4e00" <= char <= "\u9fff":
            if buffer:
                tokens.append(buffer)
                buffer = ""
            tokens.append(char)
        elif char.isalnum():
            buffer += char
        else:
            if buffer:
                tokens.append(buffer)
                buffer = ""
    if buffer:
        tokens.append(buffer)
    return tokens
