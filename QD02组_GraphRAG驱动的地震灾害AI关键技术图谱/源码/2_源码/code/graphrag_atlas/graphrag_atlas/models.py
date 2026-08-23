from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    source_type: str
    year: int
    region: str
    disaster_type: str
    path: str
    text: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    index: int


@dataclass(frozen=True)
class Entity:
    entity_id: str
    name: str
    entity_type: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class Claim:
    claim_id: str
    doc_id: str
    chunk_id: str
    text: str
    entities: tuple[str, ...]
    confidence: float


@dataclass(frozen=True)
class Relation:
    relation_id: str
    source: str
    target: str
    relation_type: str
    doc_id: str
    chunk_id: str
    evidence_text: str
    confidence: float


@dataclass(frozen=True)
class CommunityReport:
    community_id: str
    title: str
    entities: tuple[str, ...]
    relation_ids: tuple[str, ...]
    representative_docs: tuple[str, ...]
    summary: str
    evidence_strength: float
    open_questions: tuple[str, ...]


def to_dict(item: Any) -> dict[str, Any]:
    return asdict(item)
