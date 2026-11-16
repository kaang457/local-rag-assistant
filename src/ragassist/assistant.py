"""Ties the index, retrieval and the language model together."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field

from . import answer
from .answer import Turn
from .config import Settings
from .index import Index, IngestReport
from .ollama import Ollama
from .search import Hit, merge, search


@dataclass
class Timings:
    started: float = field(default_factory=time.perf_counter)
    marks: dict[str, float] = field(default_factory=dict)

    def mark(self, name: str) -> None:
        self.marks[name] = round((time.perf_counter() - self.started) * 1000, 1)


class Assistant:
    def __init__(self, settings: Settings, llm: Ollama | None = None, index: Index | None = None):
        self.settings = settings
        self.llm = llm or Ollama(settings.ollama_url, settings.chat_model, settings.embed_model)
        self.index = index or Index(settings.index_dir / "index.sqlite3")
        self.lock = threading.Lock()

    def sync(self) -> IngestReport:
        self.settings.documents_dir.mkdir(parents=True, exist_ok=True)
        with self.lock:
            return self.index.sync(self.settings.documents_dir, self.llm.embed, self.settings.chunk_chars, self.settings.chunk_overlap)

    def retrieve(self, query: str, mode: str = "hybrid", k: int | None = None, keyword_weight: float | None = None) -> list[Hit]:
        s = self.settings
        weight = s.keyword_weight if keyword_weight is None else keyword_weight
        with self.lock:
            return search(self.index, self.llm.embed, query, k or s.top_k, mode, s.min_relative_score, weight)  # type: ignore[arg-type]

    def ask(self, question: str, history: list[Turn]) -> tuple[list[Hit], Iterator[str], Timings]:
        timings = Timings()
        history = history[-self.settings.history_turns :]
        query = answer.standalone_question(question, history, self.llm.chat)
        timings.mark("rewrite_ms")
        hits = self.retrieve(question)
        if query.strip() != question.strip():
            # Search both: a bad rewrite cannot then hide what the question itself finds.
            hits = merge([hits, self.retrieve(query)], self.settings.top_k)
        timings.mark("retrieve_ms")

        def tokens() -> Iterator[str]:
            first = True
            for token in answer.stream(question, hits, history, self.llm.chat):
                if first:
                    timings.mark("first_token_ms")
                    first = False
                yield token
            timings.mark("total_ms")

        return hits, tokens(), timings
