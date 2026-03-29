from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import Chunk, SourceDocument
from .utils import normalize_whitespace, sentence_split


SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json"}


def load_document(path: str | Path) -> SourceDocument:
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_TEXT_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix}")

    if suffix == ".csv":
        content = _read_csv(file_path)
        kind = "csv"
    elif suffix == ".json":
        content = _read_json(file_path)
        kind = "json"
    else:
        content = file_path.read_text(encoding="utf-8")
        kind = "text"

    return SourceDocument(name=file_path.name, kind=kind, content=content.strip())


def load_documents(paths: list[str | Path]) -> list[SourceDocument]:
    return [load_document(path) for path in paths]


def _read_csv(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return ""

    lines: list[str] = []
    for row in rows:
        values = [f"{key}: {value}" for key, value in row.items() if value not in (None, "")]
        if values:
            lines.append("; ".join(values))
    return "\n".join(lines)


def _read_json(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    return json.dumps(data, indent=2, sort_keys=True)


def chunk_document(document: SourceDocument, max_chars: int = 520) -> list[Chunk]:
    sentences = sentence_split(document.content)
    if not sentences:
        return []

    chunks: list[Chunk] = []
    bucket: list[str] = []
    bucket_length = 0
    index = 0

    for sentence in sentences:
        sentence_length = len(sentence) + 1
        if bucket and bucket_length + sentence_length > max_chars:
            chunks.append(
                Chunk(
                    source_name=document.name,
                    text=normalize_whitespace(" ".join(bucket)),
                    index=index,
                )
            )
            index += 1
            bucket = [bucket[-1], sentence]
            bucket_length = len(bucket[0]) + sentence_length + 1
            continue

        bucket.append(sentence)
        bucket_length += sentence_length

    if bucket:
        chunks.append(
            Chunk(
                source_name=document.name,
                text=normalize_whitespace(" ".join(bucket)),
                index=index,
            )
        )

    return chunks
