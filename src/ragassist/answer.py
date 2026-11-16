"""Grounded answers: numbered sources in, cited answer out."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from .search import Hit

SYSTEM = """You are a document assistant for a company's internal documents.
Answer only from the numbered sources below. Cite every fact with its source number in square brackets, like [2].
If the sources do not contain the answer, say that the documents do not cover it. Do not use outside knowledge and do not guess.
Answer in the same language as the question. Be concise: a few sentences or a short list.

Sources:
{sources}"""

REWRITE = """Rewrite the last question so that it can be understood without the conversation.
Only add what the last question refers back to (words like "it", "that", "and for B?").
If the last question already makes sense on its own, or changes the subject, return it unchanged.
Keep its language. Reply with the question only.

Conversation:
{history}

Last question: {question}"""


@dataclass(frozen=True)
class Turn:
    question: str
    answer: str


def format_sources(hits: list[Hit]) -> str:
    if not hits:
        return "(no sources found)"
    return "\n\n".join(f"[{n}] {hit.chunk.citation}\n{hit.chunk.text}" for n, hit in enumerate(hits, start=1))


def messages(question: str, hits: list[Hit], history: list[Turn]) -> list[dict]:
    out = [{"role": "system", "content": SYSTEM.format(sources=format_sources(hits))}]
    for turn in history:
        out += [{"role": "user", "content": turn.question}, {"role": "assistant", "content": turn.answer}]
    out.append({"role": "user", "content": question})
    return out


def standalone_question(question: str, history: list[Turn], chat) -> str:
    """Follow-ups like "and for suppliers?" retrieve nothing on their own."""
    if not history:
        return question
    transcript = "\n".join(f"Q: {t.question}\nA: {t.answer}" for t in history)
    rewritten = "".join(chat([{"role": "user", "content": REWRITE.format(history=transcript, question=question)}])).strip()
    return rewritten or question


CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def cited(answer: str, n_sources: int) -> list[int]:
    """Source numbers the answer cites, in order of first use; accepts [2] and [1, 3]."""
    seen: list[int] = []
    for group in CITATION.findall(answer):
        for n in (int(x) for x in group.split(",")):
            if 1 <= n <= n_sources and n not in seen:
                seen.append(n)
    return seen


def stream(question: str, hits: list[Hit], history: list[Turn], chat) -> Iterator[str]:
    yield from chat(messages(question, hits, history))
