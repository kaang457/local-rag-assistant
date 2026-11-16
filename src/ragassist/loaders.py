"""Turns files into pages of text that remember where they came from.

A "page" is the unit a citation points at: a PDF page, or one row of a
spreadsheet. Spreadsheet rows are written out as "Header: value" pairs so
that each row reads as a self-contained fact once it is retrieved on its own.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook
from pypdf import PdfReader

SUPPORTED = {".pdf", ".xlsx", ".md", ".txt"}


WHOLE_SHEET_LIMIT = 6000  # characters; smaller sheets are also indexed as one passage


@dataclass(frozen=True)
class Page:
    source: str  # file name, as shown in citations
    location: str  # "p. 12" or "Sheet1, row 7"
    text: str
    split: bool = True  # False keeps the page in one chunk however long it is


def clean(text: str) -> str:
    text = text.replace("­", "")  # soft hyphens from PDF line breaks
    text = re.sub(r"-\n(?=[a-zçğıöşü])", "", text)  # re-join words hyphenated across lines
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def load_pdf(path: Path) -> Iterator[Page]:
    for number, page in enumerate(PdfReader(path).pages, start=1):
        text = clean(page.extract_text() or "")
        if text:
            yield Page(path.name, f"p. {number}", text)


def load_xlsx(path: Path) -> Iterator[Page]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    for sheet in workbook.worksheets:
        rows = sheet.iter_rows(values_only=True)
        header = next(rows, None)
        if not header:
            continue
        names = [str(h).strip() if h is not None else f"Column {i + 1}" for i, h in enumerate(header)]
        cells: list[list[str]] = []
        for number, row in enumerate(rows, start=2):
            values = ["" if v is None else str(v).strip() for v in row][: len(names)]
            if not any(values):
                continue
            cells.append(values)
            fields = [f"{name}: {value}" for name, value in zip(names, values, strict=False) if value]
            yield Page(path.name, f"{sheet.title}, row {number}", "; ".join(fields))
        # Questions such as "which actions are still open?" need every row at once,
        # not the six rows that happen to embed closest to the question. A markdown
        # table keeps each value under its column, which small models filter more
        # reliably than a list of "name: value" lines.
        table = markdown_table(names, cells)
        if len(cells) > 1 and len(table) <= WHOLE_SHEET_LIMIT:
            yield Page(path.name, f"{sheet.title}, all rows", table, split=False)
    workbook.close()


def markdown_table(header: list[str], rows: list[list[str]]) -> str:
    def line(values: list[str]) -> str:
        padded = values + [""] * (len(header) - len(values))
        return "| " + " | ".join(v.replace("|", "/").replace("\n", " ") for v in padded) + " |"

    return "\n".join([line(header), "|" + "---|" * len(header), *(line(r) for r in rows)])


def load_text(path: Path) -> Iterator[Page]:
    text = clean(path.read_text(encoding="utf-8"))
    if text:
        yield Page(path.name, "text", text)


def load(path: Path) -> list[Page]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return list(load_pdf(path))
    if suffix == ".xlsx":
        return list(load_xlsx(path))
    if suffix in {".md", ".txt"}:
        return list(load_text(path))
    raise ValueError(f"unsupported file type: {path.name}")
