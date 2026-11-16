"""Stand-ins for Ollama so tests run in milliseconds without a model."""

from __future__ import annotations

import hashlib
import re

import numpy as np

from ragassist.bm25 import tokenize

DIM = 256


def hashed_embedding(text: str) -> np.ndarray:
    """Bag of (stemmed) words hashed into a fixed vector: similar wording, similar vector."""
    v = np.zeros(DIM, dtype=np.float32)
    for token in tokenize(text):
        v[int(hashlib.md5(token.encode()).hexdigest(), 16) % DIM] += 1
    norm = np.linalg.norm(v)
    return v / norm if norm else v


class FakeLLM:
    chat_model = "fake-chat"
    embed_model = "fake-embed"

    def __init__(self, reply: str = "Bilekliğin direnci 1 MΩ olmalıdır [1]."):
        self.reply = reply
        self.embedded = 0
        self.prompts: list[list[dict]] = []

    def embed(self, texts: list[str]) -> np.ndarray:
        self.embedded += len(texts)
        return np.vstack([hashed_embedding(t) for t in texts]) if texts else np.zeros((0, DIM), np.float32)

    def chat(self, messages: list[dict], temperature: float = 0.1):
        self.prompts.append(messages)
        yield from re.findall(r"\S+\s*", self.reply)  # word-sized tokens, spaces kept

    def warm(self) -> None:
        pass

    def ready(self) -> dict[str, bool]:
        return {self.chat_model: True, self.embed_model: True}
