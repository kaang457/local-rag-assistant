"""Measures retrieval and answers on a labelled question set.

Each question names the file (and optionally the pages or rows) that answer
it, the facts a correct answer must contain, and its kind:

  same-language   question and document share a language
  cross-language  an English question about a Turkish document, or the reverse
  exact-term      hinges on a code, number or name rather than meaning
  unanswerable    not covered by any document; the right answer is to say so

Retrieval needs only embeddings, so it is cheap to run on every change.
Answer checks call the language model and take longer.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .answer import cited
from .assistant import Assistant
from .bm25 import turkish_lower
from .search import Hit

MODES = ("vector", "keyword", "hybrid")
DEPTH = 10
FUSION_WEIGHTS = (1.0, 0.5, 0.25)
REFUSALS = (
    "not cover",
    "does not contain",
    "do not contain",
    "don't contain",
    "no information",
    "not mention",
    "not specified",
    "yer almıyor",
    "bulunmuyor",
    "bilgi yok",
    "kapsamıyor",
    "içermiyor",
    "belirtilmemiş",
    "bahsedilmiyor",
    "bulunmamaktadır",
    "yer almamaktadır",
    "mevcut değil",
)


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    kind: str
    source: str | None = None
    locations: tuple[str, ...] = ()
    expect: tuple[str, ...] = ()
    reject: tuple[str, ...] = ()  # wrong items that must not appear, e.g. rows a list question should filter out

    def relevant(self, hit: Hit) -> bool:
        if hit.chunk.source != self.source:
            return False
        return not self.locations or hit.chunk.location in self.locations


def load(path: Path) -> list[Question]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            raw = json.loads(line)
            out.append(
                Question(
                    raw["id"],
                    raw["question"],
                    raw["kind"],
                    raw.get("source"),
                    tuple(raw.get("locations", ())),
                    tuple(raw.get("expect", ())),
                    tuple(raw.get("reject", ())),
                )
            )
    return out


def first_relevant_rank(q: Question, hits: list[Hit]) -> int | None:
    return next((rank for rank, hit in enumerate(hits, start=1) if q.relevant(hit)), None)


@dataclass
class Tally:
    n: int = 0
    hit1: int = 0
    hit_k: int = 0
    rr: float = 0.0

    def add(self, rank: int | None, k: int) -> None:
        self.n += 1
        if rank is not None:
            self.hit1 += rank == 1
            self.hit_k += rank <= k
            self.rr += 1 / rank

    def row(self) -> str:
        return f"{self.hit1 / self.n:.0%} | {self.hit_k / self.n:.0%} | {self.rr / self.n:.2f}"


@dataclass
class AnswerTally:
    n: int = 0
    correct: int = 0
    cited_right: int = 0
    seconds: list[float] = field(default_factory=list)


def is_refusal(text: str) -> bool:
    lowered = turkish_lower(text)
    return any(phrase in lowered for phrase in REFUSALS)


def check_answer(q: Question, text: str, hits: list[Hit]) -> tuple[bool, bool]:
    """(correct, cites the right document)."""
    if q.kind == "unanswerable":
        return is_refusal(text), True
    lowered = turkish_lower(text)
    # A fact may list accepted spellings separated by "|", e.g. "0,65|0.65".
    correct = all(any(turkish_lower(alt) in lowered for alt in fact.split("|")) for fact in q.expect)
    correct = correct and not any(turkish_lower(wrong) in lowered for wrong in q.reject)
    sources = {hits[n - 1].chunk.source for n in cited(text, len(hits))}
    return correct, q.source in sources


def run(assistant: Assistant, path: Path, out: Path, with_answers: bool = False) -> None:
    questions = load(path)
    answerable = [q for q in questions if q.kind != "unanswerable"]
    k = assistant.settings.top_k
    retrieval: dict[str, dict[str, Tally]] = {m: defaultdict(Tally) for m in MODES}
    misses: dict[str, list[str]] = defaultdict(list)
    for q in answerable:
        for mode in MODES:
            rank = first_relevant_rank(q, assistant.retrieve(q.question, mode, DEPTH))
            retrieval[mode][q.kind].add(rank, k)
            retrieval[mode]["all"].add(rank, k)
            if mode == "hybrid" and (rank is None or rank > k):
                misses[q.id].append(f"rank {rank}")

    kinds = ["all", *sorted({q.kind for q in answerable})]
    lines = [
        "# Evaluation",
        "",
        f"{len(questions)} questions ({len(answerable)} answerable). Index: {len(assistant.index.chunks)} chunks "
        f"from {len(assistant.index.files())} files. Embeddings: `{assistant.settings.embed_model}`.",
        "",
        f"## Retrieval: does the right page appear in the top {k}?",
        "",
        "| Questions | n | " + " | ".join(f"{m} hit@1 | {m} hit@{k} | {m} MRR" for m in MODES) + " |",
        "|---|---:|" + "---:|" * (3 * len(MODES)),
    ]
    for kind in kinds:
        n = retrieval["hybrid"][kind].n
        lines.append(f"| {kind} | {n} | " + " | ".join(retrieval[m][kind].row() for m in MODES) + " |")
    if misses:
        lines += ["", "Hybrid misses: " + ", ".join(f"`{qid}` ({', '.join(why)})" for qid, why in misses.items())]

    # How much the keyword ranking should count against the embedding ranking.
    lines += [
        "",
        f"### Fusion weight (hybrid uses {assistant.settings.keyword_weight})",
        "",
        f"| keyword weight | all hit@{k} | all MRR | cross-language hit@{k} | exact-term hit@{k} |",
        "|---:|---:|---:|---:|---:|",
    ]
    for weight in FUSION_WEIGHTS:
        tallies: dict[str, Tally] = defaultdict(Tally)
        for q in answerable:
            rank = first_relevant_rank(q, assistant.retrieve(q.question, "hybrid", DEPTH, keyword_weight=weight))
            tallies[q.kind].add(rank, k)
            tallies["all"].add(rank, k)
        t, x, e = tallies["all"], tallies["cross-language"], tallies["exact-term"]
        lines.append(f"| {weight} | {t.hit_k / t.n:.0%} | {t.rr / t.n:.2f} | {x.hit_k / max(x.n, 1):.0%} | {e.hit_k / max(e.n, 1):.0%} |")

    if with_answers:
        tallies: dict[str, AnswerTally] = defaultdict(AnswerTally)
        failures = []
        for q in questions:
            started = time.perf_counter()
            hits, tokens, _ = assistant.ask(q.question, [])
            text = "".join(tokens)
            elapsed = time.perf_counter() - started
            correct, cites = check_answer(q, text, hits)
            for key in ("all", q.kind):
                t = tallies[key]
                t.n += 1
                t.correct += correct
                t.cited_right += cites
                t.seconds.append(elapsed)
            if not correct:
                failures.append((q.id, text.strip().replace("\n", " ")[:220]))
            print(f"{'ok ' if correct else 'MISS'} {q.id}: {elapsed:.1f}s")
        lines += [
            "",
            f"## Answers (`{assistant.settings.chat_model}`)",
            "",
            "Correct means every expected fact appears in the answer, or, for unanswerable questions, that the "
            "answer says the documents do not cover it.",
            "",
            "| Questions | n | correct | cites the right file | median seconds |",
            "|---|---:|---:|---:|---:|",
        ]
        for kind in ["all", *sorted({q.kind for q in questions})]:
            t = tallies[kind]
            median = sorted(t.seconds)[len(t.seconds) // 2]
            lines.append(f"| {kind} | {t.n} | {t.correct / t.n:.0%} | {t.cited_right / t.n:.0%} | {median:.1f} |")
        if failures:
            lines += ["", "### Wrong answers", ""] + [f"- `{qid}`: {text}" for qid, text in failures]

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
