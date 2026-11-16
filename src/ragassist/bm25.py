"""Keyword search (Okapi BM25) that copes with Turkish morphology.

Turkish stacks suffixes onto a stem: "prosedür", "prosedürü", "prosedüründe".
Exact-token matching misses those, and a full morphological analyser is a
heavy dependency. Truncating every token to its first five letters is a
well-known approximation that performs close to real stemming for Turkish
retrieval (Can et al., 2008, "Information retrieval on Turkish texts"),
and it is harmless for English.
"""

from __future__ import annotations

import math
import re
from collections import Counter

PREFIX = 5
WORD = re.compile(r"[0-9a-zçğıöşüâîû]+")


def turkish_lower(text: str) -> str:
    # str.lower() maps "I" to "i" and "İ" to "i̇"; Turkish wants "ı" and "i".
    return text.replace("I", "ı").replace("İ", "i").lower()


def tokenize(text: str) -> list[str]:
    return [w[:PREFIX] for w in WORD.findall(turkish_lower(text)) if len(w) > 1]


class BM25:
    def __init__(self, documents: list[str], k1: float = 1.4, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(d)) for d in documents]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg_len = sum(self.lengths) / len(self.lengths) if self.lengths else 0.0
        df = Counter(term for d in self.docs for term in d)
        n = len(self.docs)
        self.idf = {term: math.log(1 + (n - f + 0.5) / (f + 0.5)) for term, f in df.items()}

    def scores(self, query: str) -> list[float]:
        terms = [t for t in set(tokenize(query)) if t in self.idf]
        out = []
        for doc, length in zip(self.docs, self.lengths, strict=True):
            norm = self.k1 * (1 - self.b + self.b * length / self.avg_len) if self.avg_len else self.k1
            out.append(sum(self.idf[t] * doc[t] * (self.k1 + 1) / (doc[t] + norm) for t in terms if t in doc))
        return out
