"""The document index: chunks and their embeddings in one SQLite file.

Ingestion is incremental. Each file is fingerprinted by its SHA-256, so a
re-scan only embeds files that are new or changed and drops chunks of files
that were deleted. Embeddings are loaded into one matrix for search; at the
scale of a team's document folder (tens of thousands of chunks) a matrix
product is faster than any approximate index and needs no extra service.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .bm25 import BM25
from .chunking import Chunk, chunk_pages
from .loaders import SUPPORTED, load

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (name TEXT PRIMARY KEY, sha256 TEXT NOT NULL, chunks INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL REFERENCES files(name) ON DELETE CASCADE,
    location TEXT NOT NULL,
    text TEXT NOT NULL,
    embedding BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS chunks_source ON chunks(source);
"""

Embedder = Callable[[list[str]], np.ndarray]


@dataclass
class IngestReport:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    unchanged: int = 0
    failed: dict[str, str] = field(default_factory=dict)
    chunks: int = 0


# Bump when the way chunks are built or embedded changes; every file is then re-indexed.
INDEX_VERSION = b"4"


def sha256(path: Path) -> str:
    return hashlib.sha256(INDEX_VERSION + path.read_bytes()).hexdigest()


def embedding_text(chunk: Chunk) -> str:
    """The text that gets embedded: the chunk prefixed with its document's title.

    A spreadsheet row such as "Sorumlu Birim: Satın Alma; Durum: Açık" does not
    say it is an action item; the file name does. Without the title, short
    chunks lose the context a reader of the whole document would have."""
    title = Path(chunk.source).stem
    return f"{title} ({chunk.location})\n{chunk.text}"


class Index:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)
        self.reload()

    def reload(self) -> None:
        rows = self.db.execute("SELECT source, location, text, embedding FROM chunks ORDER BY id").fetchall()
        self.chunks = [Chunk(source, location, text) for source, location, text, _ in rows]
        self.matrix = np.vstack([np.frombuffer(r[3], dtype=np.float32) for r in rows]) if rows else np.zeros((0, 0), np.float32)
        self.bm25 = BM25([c.text for c in self.chunks])

    def files(self) -> list[tuple[str, int]]:
        return self.db.execute("SELECT name, chunks FROM files ORDER BY name").fetchall()

    def sync(self, folder: Path, embed: Embedder, size: int = 900, overlap: int = 150) -> IngestReport:
        """Make the index match the folder."""
        report = IngestReport()
        known = dict(self.db.execute("SELECT name, sha256 FROM files").fetchall())
        on_disk = {p.name: p for p in sorted(folder.iterdir()) if p.is_file() and p.suffix.lower() in SUPPORTED}

        for name in known.keys() - on_disk.keys():
            self.db.execute("DELETE FROM files WHERE name = ?", (name,))
            report.removed.append(name)

        for name, path in on_disk.items():
            digest = sha256(path)
            if known.get(name) == digest:
                report.unchanged += 1
                continue
            try:
                chunks = chunk_pages(load(path), size, overlap)
                vectors = embed([embedding_text(c) for c in chunks]) if chunks else np.zeros((0, 0), np.float32)
            except Exception as err:  # one unreadable file must not stop the rest
                report.failed[name] = str(err)
                continue
            with self.db:
                self.db.execute("DELETE FROM files WHERE name = ?", (name,))
                self.db.execute("INSERT INTO files VALUES (?, ?, ?)", (name, digest, len(chunks)))
                self.db.executemany(
                    "INSERT INTO chunks (source, location, text, embedding) VALUES (?, ?, ?, ?)",
                    [(c.source, c.location, c.text, v.astype(np.float32).tobytes()) for c, v in zip(chunks, vectors, strict=True)],
                )
            (report.updated if name in known else report.added).append(name)
        self.db.commit()
        self.reload()
        report.chunks = len(self.chunks)
        return report
