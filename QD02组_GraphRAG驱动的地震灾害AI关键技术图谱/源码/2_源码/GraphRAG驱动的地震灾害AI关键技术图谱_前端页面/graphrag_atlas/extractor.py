from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from .models import Chunk, Claim, Entity, Relation


class RuleBasedExtractor:
    """Deterministic extractor used as a local baseline.

    The interface is intentionally small so a future LLM extractor can replace
    this class without changing the rest of the GraphRAG pipeline.
    """

    def __init__(self, ontology: dict):
        self.ontology = ontology
        self.entity_specs = ontology["entities"]
        self.relation_rules = ontology["relation_rules"]
        self._entities = self._build_entities()

    def _build_entities(self) -> dict[str, Entity]:
        entities: dict[str, Entity] = {}
        for entity_type, items in self.entity_specs.items():
            for item in items:
                entity_id = item["id"]
                entities[entity_id] = Entity(
                    entity_id=entity_id,
                    name=item["name"],
                    entity_type=entity_type,
                    aliases=tuple(item.get("aliases", [])),
                )
        return entities

    @property
    def entities(self) -> list[Entity]:
        return list(self._entities.values())

    def extract(self, chunks: list[Chunk]) -> tuple[list[Claim], list[Relation]]:
        claims: list[Claim] = []
        relations: list[Relation] = []
        for chunk in chunks:
            mentions = self._find_mentions(chunk.text)
            if mentions:
                claims.extend(self._extract_claims(chunk, mentions))
                relations.extend(self._extract_relations(chunk, mentions))
        return self._dedupe_claims(claims), self._dedupe_relations(relations)

    def _find_mentions(self, text: str) -> dict[str, set[str]]:
        found: dict[str, set[str]] = defaultdict(set)
        lowered = text.lower()
        for entity in self._entities.values():
            names = [entity.name, *entity.aliases]
            if any(name and name.lower() in lowered for name in names):
                found[entity.entity_type].add(entity.entity_id)
        return found

    def _extract_claims(self, chunk: Chunk, mentions: dict[str, set[str]]) -> list[Claim]:
        sentences = [item.strip() for item in re.split(r"[。；;.!?？]\s*", chunk.text) if item.strip()]
        all_entities = tuple(sorted({entity for group in mentions.values() for entity in group}))
        claims: list[Claim] = []
        for sentence in sentences:
            sentence_mentions = {
                entity.entity_id
                for entity in self._entities.values()
                if entity.entity_id in all_entities
                and any(name and name.lower() in sentence.lower() for name in [entity.name, *entity.aliases])
            }
            if len(sentence_mentions) < 2:
                continue
            claim_id = stable_id("claim", chunk.chunk_id, sentence)
            confidence = min(0.95, 0.55 + 0.08 * len(sentence_mentions))
            claims.append(
                Claim(
                    claim_id=claim_id,
                    doc_id=chunk.doc_id,
                    chunk_id=chunk.chunk_id,
                    text=sentence,
                    entities=tuple(sorted(sentence_mentions)),
                    confidence=round(confidence, 3),
                )
            )
        if not claims and len(all_entities) >= 2:
            claims.append(
                Claim(
                    claim_id=stable_id("claim", chunk.chunk_id, chunk.text[:120]),
                    doc_id=chunk.doc_id,
                    chunk_id=chunk.chunk_id,
                    text=chunk.text[:240],
                    entities=all_entities,
                    confidence=0.55,
                )
            )
        return claims

    def _extract_relations(self, chunk: Chunk, mentions: dict[str, set[str]]) -> list[Relation]:
        relations: list[Relation] = []
        for rule in self.relation_rules:
            source_type = rule["source_type"]
            target_type = rule["target_type"]
            relation_type = rule["relation_type"]
            for source in mentions.get(source_type, set()):
                for target in mentions.get(target_type, set()):
                    if source == target:
                        continue
                    relations.append(
                        Relation(
                            relation_id=stable_id(
                                "rel", source, relation_type, target, chunk.doc_id, chunk.chunk_id
                            ),
                            source=source,
                            target=target,
                            relation_type=relation_type,
                            doc_id=chunk.doc_id,
                            chunk_id=chunk.chunk_id,
                            evidence_text=chunk.text[:360],
                            confidence=rule.get("confidence", 0.68),
                        )
                    )
        return relations

    def _dedupe_claims(self, claims: list[Claim]) -> list[Claim]:
        return dedupe_claims(claims)

    def _dedupe_relations(self, relations: list[Relation]) -> list[Relation]:
        return dedupe_relations(relations)


def dedupe_claims(claims: list[Claim]) -> list[Claim]:
    seen = set()
    unique: list[Claim] = []
    for claim in claims:
        if claim.claim_id in seen:
            continue
        seen.add(claim.claim_id)
        unique.append(claim)
    return unique


def dedupe_relations(relations: list[Relation]) -> list[Relation]:
    seen = set()
    unique: list[Relation] = []
    for relation in relations:
        if relation.relation_id in seen:
            continue
        seen.add(relation.relation_id)
        unique.append(relation)
    return unique


def stable_id(*parts: str) -> str:
    raw = "::".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
