"""Settings, read once from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    ollama_url: str = "http://localhost:11434"
    chat_model: str = "qwen2.5:7b"
    embed_model: str = "bge-m3"
    documents_dir: Path = Path("documents")
    index_dir: Path = Path("index")
    chunk_chars: int = 900
    chunk_overlap: int = 150
    top_k: int = 6
    keyword_weight: float = 0.5
    # Fused hits below this share of the best hit's score are dropped from the prompt.
    min_relative_score: float = 0.35
    history_turns: int = 3

    @classmethod
    def from_env(cls) -> Settings:
        env = os.environ.get
        default = cls()
        return cls(
            ollama_url=env("OLLAMA_URL", default.ollama_url).rstrip("/"),
            chat_model=env("CHAT_MODEL", default.chat_model),
            embed_model=env("EMBED_MODEL", default.embed_model),
            documents_dir=Path(env("DOCUMENTS_DIR", str(default.documents_dir))),
            index_dir=Path(env("INDEX_DIR", str(default.index_dir))),
            top_k=int(env("TOP_K", str(default.top_k))),
            keyword_weight=float(env("KEYWORD_WEIGHT", str(default.keyword_weight))),
        )
