"""A small client for the two Ollama endpoints this project needs."""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
import numpy as np


class OllamaError(RuntimeError):
    pass


class Ollama:
    def __init__(self, base_url: str, chat_model: str, embed_model: str, timeout: float = 300):
        self.chat_model = chat_model
        self.embed_model = embed_model
        self.http = httpx.Client(base_url=base_url, timeout=timeout)

    def embed(self, texts: list[str], batch: int = 32) -> np.ndarray:
        """Unit-length embeddings, one row per text, so a dot product is cosine similarity."""
        rows = []
        for i in range(0, len(texts), batch):
            resp = self._post("/api/embed", {"model": self.embed_model, "input": texts[i : i + batch]})
            rows.extend(resp.json()["embeddings"])
        vectors = np.asarray(rows, dtype=np.float32)
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True).clip(min=1e-12)

    def chat(self, messages: list[dict], temperature: float = 0.1) -> Iterator[str]:
        """Streams the reply token by token."""
        body = {"model": self.chat_model, "messages": messages, "stream": True, "options": {"temperature": temperature}}
        with self.http.stream("POST", "/api/chat", json=body) as resp:
            if resp.status_code != 200:
                resp.read()
                raise OllamaError(f"chat failed ({resp.status_code}): {resp.text[:200]}")
            for line in resp.iter_lines():
                if not line:
                    continue
                event = json.loads(line)
                if "error" in event:
                    raise OllamaError(event["error"])
                if token := event.get("message", {}).get("content"):
                    yield token

    def warm(self) -> None:
        """Load both models into memory now, so the first question does not pay for it."""
        self._post("/api/generate", {"model": self.chat_model, "prompt": "", "keep_alive": "30m"})
        self.embed(["warm-up"])

    def ready(self) -> dict[str, bool]:
        """Which of the configured models are present on the server."""
        try:
            names = {m["name"] for m in self.http.get("/api/tags").json().get("models", [])}
        except httpx.HTTPError:
            return {self.chat_model: False, self.embed_model: False}

        def present(model: str) -> bool:
            return model in names or f"{model}:latest" in names

        return {self.chat_model: present(self.chat_model), self.embed_model: present(self.embed_model)}

    def _post(self, path: str, body: dict) -> httpx.Response:
        try:
            resp = self.http.post(path, json=body)
        except httpx.HTTPError as err:
            raise OllamaError(f"cannot reach Ollama: {err}") from err
        if resp.status_code != 200:
            raise OllamaError(f"{path} failed ({resp.status_code}): {resp.text[:200]}")
        return resp
