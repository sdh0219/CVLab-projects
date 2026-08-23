from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from .models import Document


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, flags=re.S)
    if not match:
        return {}, text
    meta_text, body = match.groups()
    metadata: dict[str, str] = {}
    for line in meta_text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata, body.strip()


def load_documents(corpus_dir: Path) -> list[Document]:
    documents: list[Document] = []
    for path in sorted(corpus_dir.glob("*.md")):
        metadata, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        doc_id = metadata.get("doc_id") or path.stem
        documents.append(
            Document(
                doc_id=doc_id,
                title=metadata.get("title", path.stem),
                source_type=metadata.get("source_type", "unknown"),
                year=int(metadata.get("year", "0") or "0"),
                region=metadata.get("region", "unknown"),
                disaster_type=metadata.get("disaster_type", "unknown"),
                path=str(path),
                text=body,
                metadata=metadata,
            )
        )
    return documents


def chunk_document(document: Document, max_chars: int = 520) -> list:
    from .models import Chunk

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", document.text) if part.strip()]
    chunks: list[Chunk] = []
    buffer = ""
    index = 0
    for paragraph in paragraphs:
        candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
        if len(candidate) <= max_chars:
            buffer = candidate
            continue
        if buffer:
            chunks.append(Chunk(f"{document.doc_id}_c{index:03d}", document.doc_id, buffer, index))
            index += 1
        buffer = paragraph
    if buffer:
        chunks.append(Chunk(f"{document.doc_id}_c{index:03d}", document.doc_id, buffer, index))
    return chunks
