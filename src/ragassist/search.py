"""Hybrid retrieval: semantic search and keyword search, fused by rank.

Embeddings find passages that mean the same thing in other words, or in
another language. BM25 finds exact terms embeddings blur: part numbers,
standard names, codes like "AKS-014". Reciprocal rank fusion combines the two
ranked lists without having to calibrate their very different score scales.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from .chunking import Chunk
from .index import Embedder, Index

Mode = Literal["hybrid", "vector", "keyword"]
RRF_K = 10  # sharper than the usual 60: with two lists of 50, k=60 lets mediocre agreement outrank a clear first place
CANDIDATES = 50


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


def top(scores: np.ndarray, n: int) -> list[int]:
    n = min(n, len(scores))
    if n == 0:
        return []
    best = np.argpartition(-scores, n - 1)[:n]
    return [int(i) for i in best[np.argsort(-scores[best])] if scores[i] > 0]


def rrf(rankings: list[list[int]], weights: list[float] | None = None, k: int = RRF_K) -> dict[int, float]:
    fused: dict[int, float] = {}
    for ranking, weight in zip(rankings, weights or [1.0] * len(rankings), strict=True):
        for rank, i in enumerate(ranking):
            fused[i] = fused.get(i, 0.0) + weight / (k + rank + 1)
    return fused


def merge(result_lists: list[list[Hit]], k: int) -> list[Hit]:
    """Fuse several result lists for the same question (e.g. as asked, and as rewritten)."""
    ids: dict[Chunk, int] = {}
    rankings = [[ids.setdefault(h.chunk, len(ids)) for h in hits] for hits in result_lists]
    chunks = list(ids)
    fused = sorted(rrf(rankings).items(), key=lambda item: -item[1])[:k]
    return [Hit(chunks[i], score) for i, score in fused]


def search(
    index: Index,
    embed: Embedder,
    query: str,
    k: int = 6,
    mode: Mode = "hybrid",
    min_relative: float = 0.0,
    keyword_weight: float = 0.5,
) -> list[Hit]:
    """`keyword_weight` scales BM25's vote against the embedding's. Equal votes
    hurt cross-language questions: BM25 then ranks whatever shares the query's
    English words, which is the wrong document when the answer is in Turkish."""
    if not index.chunks:
        return []
    rankings, weights = [], []
    if mode in ("hybrid", "vector"):
        rankings.append(top(index.matrix @ embed([query])[0], CANDIDATES))
        weights.append(1.0)
    if mode in ("hybrid", "keyword"):
        rankings.append(top(np.asarray(index.bm25.scores(query)), CANDIDATES))
        weights.append(keyword_weight if mode == "hybrid" else 1.0)
    fused = sorted(rrf(rankings, weights).items(), key=lambda item: -item[1])[:k]
    if not fused:
        return []
    best = fused[0][1]
    return [Hit(index.chunks[i], score) for i, score in fused if score >= best * min_relative]
