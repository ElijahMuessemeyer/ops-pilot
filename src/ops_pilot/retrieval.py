from __future__ import annotations

from collections import Counter
from math import sqrt

from .models import Chunk, EvidenceSnippet
from .utils import short_quote, tokenize


class SimpleRetriever:
    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks
        self._chunk_tokens = [Counter(tokenize(chunk.text)) for chunk in chunks]

    def search(self, query: str, limit: int = 5) -> list[EvidenceSnippet]:
        query_tokens = Counter(tokenize(query))
        if not query_tokens:
            return []

        scored: list[tuple[float, Chunk]] = []
        for chunk, chunk_tokens in zip(self._chunks, self._chunk_tokens, strict=False):
            score = _cosine_like(query_tokens, chunk_tokens)
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            EvidenceSnippet(
                source_name=chunk.source_name,
                quote=short_quote(chunk.text),
                score=round(score, 3),
            )
            for score, chunk in scored[:limit]
        ]


def _cosine_like(left: Counter[str], right: Counter[str]) -> float:
    common = set(left).intersection(right)
    if not common:
        return 0.0

    numerator = sum(left[token] * right[token] for token in common)
    left_norm = sqrt(sum(value * value for value in left.values()))
    right_norm = sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)
