"""Splits pages into overlapping chunks at natural boundaries.

Chunks never cross a page, so every chunk has exactly one citation. Inside a
page the splitter prefers paragraph breaks, then sentence ends, then spaces,
and only cuts mid-word as a last resort.
"""

from __future__ import annotations

from dataclasses import dataclass

from .loaders import Page

SEPARATORS = ("\n\n", "\n", ". ", "; ", ", ", " ")


@dataclass(frozen=True)
class Chunk:
    source: str
    location: str
    text: str

    @property
    def citation(self) -> str:
        return f"{self.source}, {self.location}"


def split_text(text: str, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text]
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            window = text[start:end]
            for sep in SEPARATORS:
                cut = window.rfind(sep)
                if cut > size // 2:  # only accept a boundary in the second half of the window
                    end = start + cut + len(sep)
                    break
        pieces.append(text[start:end].strip())
        if end >= len(text):
            break
        next_start = end - overlap
        # Start the overlap on a word boundary.
        space = text.find(" ", next_start, end)
        start = space + 1 if space != -1 else next_start
    return [p for p in pieces if p]


def chunk_pages(pages: list[Page], size: int = 900, overlap: int = 150) -> list[Chunk]:
    return [
        Chunk(page.source, page.location, piece)
        for page in pages
        for piece in (split_text(page.text, size, overlap) if page.split else [page.text])
    ]
