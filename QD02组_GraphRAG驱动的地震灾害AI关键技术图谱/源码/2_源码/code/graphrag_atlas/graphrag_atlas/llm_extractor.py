from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .extractor import dedupe_claims, dedupe_relations, stable_id
from .models import Chunk, Claim, Entity, Relation


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    api_key: str
    base_url: str
    timeout_seconds: int = 60
    max_tokens: int = 1400
    temperature: float = 0.0
    top_p: float | None = None
    json_mode: bool = True
    max_retries: int = 3
    retry_sleep_seconds: float = 8.0
    request_sleep_seconds: float = 0.0
    cache_dir: str | None = "outputs/graphrag_index/llm_cache"


class OpenAICompatibleClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.cache_hits = 0
        self.cache_writes = 0

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if self.config.top_p is not None:
            payload["top_p"] = self.config.top_p
        if self.config.json_mode:
            payload["response_format"] = {"type": "json_object"}
        cache_path = self._cache_path(payload)
        if cache_path and cache_path.exists():
            self.cache_hits += 1
            return json.loads(cache_path.read_text(encoding="utf-8"))
        request = urllib.request.Request(
            url=f"{self.config.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(1, self.config.max_retries + 2):
            if self.config.request_sleep_seconds > 0:
                time.sleep(self.config.request_sleep_seconds)
            try:
                with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                    raw = response.read().decode("utf-8")
                data = json.loads(raw)
                content = data["choices"][0]["message"]["content"]
                parsed = parse_json_object(content)
                if cache_path:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
                    self.cache_writes += 1
                return parsed
            except urllib.error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="replace")
                last_error = RuntimeError(f"LLM HTTP {exc.code}: {details}")
                if exc.code != 429 or attempt > self.config.max_retries:
                    raise last_error from exc
                retry_after = exc.headers.get("Retry-After")
                sleep_seconds = parse_retry_after(retry_after, self.config.retry_sleep_seconds * attempt)
                print(
                    f"[LLM] HTTP 429, retrying in {sleep_seconds:.1f}s (attempt {attempt}/{self.config.max_retries})",
                    file=sys.stderr,
                    flush=True,
                )
                time.sleep(sleep_seconds)
            except Exception as exc:
                last_error = exc
                if attempt > self.config.max_retries:
                    raise
                sleep_seconds = self.config.retry_sleep_seconds * attempt
                print(
                    f"[LLM] request failed, retrying in {sleep_seconds:.1f}s (attempt {attempt}/{self.config.max_retries}): {type(exc).__name__}",
                    file=sys.stderr,
                    flush=True,
                )
                time.sleep(sleep_seconds)
        if last_error:
            raise last_error
        raise RuntimeError("LLM request failed without an error.")

    def _cache_path(self, payload: dict[str, Any]) -> Path | None:
        if not self.config.cache_dir:
            return None
        cache_basis = {
            "provider": self.config.provider,
            "base_url": self.config.base_url.rstrip("/"),
            "model": self.config.model,
            "json_mode": self.config.json_mode,
            "payload": payload,
        }
        cache_key = hashlib.sha256(
            json.dumps(cache_basis, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return Path(self.config.cache_dir) / f"{cache_key}.json"


class LLMExtractor:
    """Ontology-constrained LLM extractor.

    The model is allowed to extract claims and relations, but all entity IDs and
    relation types are validated against config/ontology.json before entering
    the graph index.
    """

    def __init__(self, ontology: dict, client: OpenAICompatibleClient, ignore_errors: bool = False):
        self.ontology = ontology
        self.client = client
        self.ignore_errors = ignore_errors
        self.entity_specs = ontology["entities"]
        self.relation_rules = ontology["relation_rules"]
        self._entities = self._build_entities()
        self.entity_types = {entity.entity_id: entity.entity_type for entity in self._entities.values()}
        self.relation_rule_set = {
            (rule["source_type"], rule["target_type"], rule["relation_type"])
            for rule in self.relation_rules
        }
        self.relation_defaults = {
            (rule["source_type"], rule["target_type"], rule["relation_type"]): rule.get("confidence", 0.68)
            for rule in self.relation_rules
        }
        self.stats: dict[str, Any] = {
            "extractor": "llm",
            "llm_provider": client.config.provider,
            "llm_model": client.config.model,
            "llm_calls": 0,
            "llm_failures": 0,
            "llm_available": True,
            "llm_cache_enabled": bool(client.config.cache_dir),
            "llm_cache_hits": 0,
            "llm_cache_writes": 0,
        }

    @classmethod
    def from_env(cls, ontology: dict, ignore_errors: bool = False) -> "LLMExtractor":
        config = llm_config_from_env()
        if config.provider != "openai_compatible":
            raise ValueError(f"Unsupported ATLAS_LLM_PROVIDER: {config.provider}")
        return cls(ontology, OpenAICompatibleClient(config), ignore_errors=ignore_errors)

    @property
    def entities(self) -> list[Entity]:
        return list(self._entities.values())

    def extract(self, chunks: list[Chunk]) -> tuple[list[Claim], list[Relation]]:
        claims: list[Claim] = []
        relations: list[Relation] = []
        total = len(chunks)
        show_progress = os.environ.get("ATLAS_LLM_PROGRESS", "0") == "1"
        for index, chunk in enumerate(chunks, start=1):
            if show_progress:
                print(
                    f"[LLM] extracting chunk {index}/{total}: {chunk.chunk_id}",
                    file=sys.stderr,
                    flush=True,
                )
            try:
                chunk_claims, chunk_relations = self._extract_chunk(chunk)
            except Exception as exc:
                self.stats["llm_failures"] += 1
                if show_progress:
                    print(
                        f"[LLM] failed chunk {index}/{total}: {chunk.chunk_id} ({type(exc).__name__}: {str(exc)[:300]})",
                        file=sys.stderr,
                        flush=True,
                    )
                if self.ignore_errors:
                    continue
                raise
            claims.extend(chunk_claims)
            relations.extend(chunk_relations)
        return dedupe_claims(claims), dedupe_relations(relations)

    def _build_entities(self) -> dict[str, Entity]:
        entities: dict[str, Entity] = {}
        for entity_type, items in self.entity_specs.items():
            for item in items:
                entities[item["id"]] = Entity(
                    entity_id=item["id"],
                    name=item["name"],
                    entity_type=entity_type,
                    aliases=tuple(item.get("aliases", [])),
                )
        return entities

    def _extract_chunk(self, chunk: Chunk) -> tuple[list[Claim], list[Relation]]:
        self.stats["llm_calls"] += 1
        response = self.client.complete_json(self._messages(chunk))
        self.stats["llm_cache_hits"] = self.client.cache_hits
        self.stats["llm_cache_writes"] = self.client.cache_writes
        return self._parse_response(chunk, response)

    def _messages(self, chunk: Chunk) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "你是地震灾害AI防灾减灾GraphRAG知识抽取器。只输出JSON对象，不要输出解释。"
                    "所有实体必须使用给定ontology里的entity_id，关系必须使用给定relation_rules。"
                    "不要臆造证据；evidence_text必须来自输入文本，可摘取短句。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": "extract_claims_and_relations",
                        "schema": {
                            "claims": [
                                {
                                    "text": "string",
                                    "entities": ["entity_id"],
                                    "confidence": 0.0,
                                }
                            ],
                            "relations": [
                                {
                                    "source": "entity_id",
                                    "target": "entity_id",
                                    "relation_type": "APPLIES_TO|SERVES_STAGE|SOLVES|DEPENDS_ON|USES_MODEL|VALIDATED_IN|LIMITED_BY|REQUIRED_BY",
                                    "evidence_text": "string from input text",
                                    "confidence": 0.0,
                                }
                            ],
                        },
                        "ontology_entities": ontology_prompt_entities(self.entities),
                        "relation_rules": self.relation_rules,
                        "chunk": {
                            "doc_id": chunk.doc_id,
                            "chunk_id": chunk.chunk_id,
                            "text": chunk.text,
                        },
                    },
                    ensure_ascii=False,
                ),
            },
        ]

    def _parse_response(self, chunk: Chunk, response: dict[str, Any]) -> tuple[list[Claim], list[Relation]]:
        claims: list[Claim] = []
        relations: list[Relation] = []
        for index, item in enumerate(response.get("claims", [])):
            text = str(item.get("text", "")).strip()
            entity_ids = tuple(
                sorted(
                    entity_id
                    for entity_id in item.get("entities", [])
                    if isinstance(entity_id, str) and entity_id in self.entity_types
                )
            )
            if not text or len(entity_ids) < 2:
                continue
            claims.append(
                Claim(
                    claim_id=stable_id("llm_claim", chunk.chunk_id, str(index), text),
                    doc_id=chunk.doc_id,
                    chunk_id=chunk.chunk_id,
                    text=text[:500],
                    entities=entity_ids,
                    confidence=coerce_confidence(item.get("confidence"), default=0.72),
                )
            )
        for index, item in enumerate(response.get("relations", [])):
            source = item.get("source")
            target = item.get("target")
            relation_type = item.get("relation_type")
            if not isinstance(source, str) or not isinstance(target, str) or not isinstance(relation_type, str):
                continue
            if source not in self.entity_types or target not in self.entity_types or source == target:
                continue
            source_type = self.entity_types[source]
            target_type = self.entity_types[target]
            rule_key = (source_type, target_type, relation_type)
            if rule_key not in self.relation_rule_set:
                continue
            evidence_text = str(item.get("evidence_text", "")).strip() or chunk.text[:360]
            default_confidence = self.relation_defaults.get(rule_key, 0.68)
            relations.append(
                Relation(
                    relation_id=stable_id("llm_rel", source, relation_type, target, chunk.doc_id, chunk.chunk_id, str(index)),
                    source=source,
                    target=target,
                    relation_type=relation_type,
                    doc_id=chunk.doc_id,
                    chunk_id=chunk.chunk_id,
                    evidence_text=evidence_text[:500],
                    confidence=coerce_confidence(item.get("confidence"), default=default_confidence),
                )
            )
        return claims, relations


class HybridExtractor:
    def __init__(self, ontology: dict):
        from .extractor import RuleBasedExtractor

        self.rule = RuleBasedExtractor(ontology)
        self.llm: LLMExtractor | None = None
        self.stats: dict[str, Any] = {
            "extractor": "hybrid",
            "llm_available": False,
            "llm_calls": 0,
            "llm_failures": 0,
        }
        try:
            self.llm = LLMExtractor.from_env(ontology, ignore_errors=True)
            self.stats.update(self.llm.stats)
            self.stats["extractor"] = "hybrid"
            self.stats["llm_available"] = True
        except ValueError as exc:
            self.stats["llm_error"] = str(exc)

    @property
    def entities(self) -> list[Entity]:
        return self.rule.entities

    def extract(self, chunks: list[Chunk]) -> tuple[list[Claim], list[Relation]]:
        rule_claims, rule_relations = self.rule.extract(chunks)
        if not self.llm:
            return rule_claims, rule_relations
        llm_claims, llm_relations = self.llm.extract(chunks)
        self.stats.update(self.llm.stats)
        self.stats["extractor"] = "hybrid"
        return dedupe_claims([*rule_claims, *llm_claims]), dedupe_relations([*rule_relations, *llm_relations])


def llm_config_from_env() -> LLMConfig:
    api_key = os.environ.get("ATLAS_LLM_API_KEY", "").strip()
    if not api_key:
        raise ValueError("ATLAS_LLM_API_KEY is required for LLM extraction.")
    return LLMConfig(
        provider=os.environ.get("ATLAS_LLM_PROVIDER", "openai_compatible").strip(),
        model=os.environ.get("ATLAS_LLM_MODEL", "").strip() or "gpt-4.1-mini",
        api_key=api_key,
        base_url=os.environ.get("ATLAS_LLM_BASE_URL", "https://api.openai.com/v1").strip(),
        timeout_seconds=int(os.environ.get("ATLAS_LLM_TIMEOUT_SECONDS", "60")),
        max_tokens=int(os.environ.get("ATLAS_LLM_MAX_TOKENS", "1400")),
        temperature=float(os.environ.get("ATLAS_LLM_TEMPERATURE", "0")),
        top_p=optional_float(os.environ.get("ATLAS_LLM_TOP_P")),
        json_mode=os.environ.get("ATLAS_LLM_JSON_MODE", "1") != "0",
        max_retries=int(os.environ.get("ATLAS_LLM_MAX_RETRIES", "3")),
        retry_sleep_seconds=float(os.environ.get("ATLAS_LLM_RETRY_SLEEP_SECONDS", "8")),
        request_sleep_seconds=float(os.environ.get("ATLAS_LLM_REQUEST_SLEEP_SECONDS", "0")),
        cache_dir=llm_cache_dir_from_env(),
    )


def llm_cache_dir_from_env() -> str | None:
    if os.environ.get("ATLAS_LLM_CACHE", "1") == "0":
        return None
    cache_dir = os.environ.get("ATLAS_LLM_CACHE_DIR", "outputs/graphrag_index/llm_cache").strip()
    return cache_dir or None


def parse_json_object(content: str) -> dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        match = re.search(r"\{.*\}", content, flags=re.S)
        if not match:
            raise ValueError(f"LLM response is not JSON: {content[:200]}") from exc
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("LLM response JSON must be an object.")
    return data


def coerce_confidence(value: Any, default: float) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = default
    return round(max(0.0, min(1.0, confidence)), 3)


def optional_float(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    return float(value)


def parse_retry_after(value: str | None, default: float) -> float:
    if not value:
        return default
    try:
        return max(0.0, float(value))
    except ValueError:
        return default


def ontology_prompt_entities(entities: list[Entity]) -> list[dict[str, Any]]:
    return [
        {
            "entity_id": entity.entity_id,
            "name": entity.name,
            "entity_type": entity.entity_type,
            "aliases": list(entity.aliases),
        }
        for entity in entities
    ]
