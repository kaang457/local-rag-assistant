from pathlib import Path

import pytest
from openpyxl import Workbook

from ragassist.chunking import chunk_pages
from ragassist.index import Index
from ragassist.loaders import load
from ragassist.search import rrf, search
from tests.fakes import FakeLLM

DOCUMENTS = Path(__file__).resolve().parents[1] / "documents"


@pytest.fixture
def folder(tmp_path):
    docs = tmp_path / "documents"
    docs.mkdir()
    (docs / "esd.md").write_text("Bileklik kayışı 1 MΩ seri dirençle topraklanır. Test sonucu ESD-F-03 formuna yazılır.", encoding="utf-8")
    (docs / "supplier.md").write_text("A sınıfı tedarikçiler yılda bir kez denetlenir. B sınıfı iki yılda bir.", encoding="utf-8")
    return docs


def test_sync_adds_skips_updates_and_removes(tmp_path, folder):
    llm = FakeLLM()
    index = Index(tmp_path / "index.sqlite3")

    first = index.sync(folder, llm.embed)
    assert sorted(first.added) == ["esd.md", "supplier.md"]
    embedded = llm.embedded

    second = index.sync(folder, llm.embed)
    assert second.unchanged == 2 and llm.embedded == embedded, "unchanged files must not be re-embedded"

    (folder / "esd.md").write_text("Bileklik direnci 1 MΩ. Nem %30-%70.", encoding="utf-8")
    (folder / "supplier.md").unlink()
    third = index.sync(folder, llm.embed)
    assert third.updated == ["esd.md"] and third.removed == ["supplier.md"]
    assert {c.source for c in index.chunks} == {"esd.md"}


def test_index_survives_a_restart(tmp_path, folder):
    Index(tmp_path / "index.sqlite3").sync(folder, FakeLLM().embed)
    reopened = Index(tmp_path / "index.sqlite3")
    assert len(reopened.chunks) == 2 and reopened.matrix.shape[0] == 2


def test_unreadable_file_is_reported_not_fatal(tmp_path, folder):
    (folder / "broken.pdf").write_bytes(b"not a pdf")
    report = Index(tmp_path / "index.sqlite3").sync(folder, FakeLLM().embed)
    assert "broken.pdf" in report.failed
    assert sorted(report.added) == ["esd.md", "supplier.md"]


def test_spreadsheet_rows_become_cited_facts(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Aksiyonlar"
    ws.append(["Aksiyon No", "Konu", "Durum"])
    ws.append(["AKS-001", "Lehim köprüleme", "Kapandı"])
    ws.append([None, None, None])
    path = tmp_path / "actions.xlsx"
    wb.save(path)
    pages = load(path)
    assert len(pages) == 1
    assert pages[0].location == "Aksiyonlar, row 2"
    assert pages[0].text == "Aksiyon No: AKS-001; Konu: Lehim köprüleme; Durum: Kapandı"


def test_small_sheet_is_also_indexed_whole_and_unsplit(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Aksiyonlar"
    ws.append(["No", "Konu"])
    for i in range(40):
        ws.append([f"AKS-{i:03d}", "Uzun bir konu açıklaması " * 3])
    path = tmp_path / "actions.xlsx"
    wb.save(path)
    pages = load(path)
    assert pages[-1].location == "Aksiyonlar, all rows" and not pages[-1].split
    whole = [c for c in chunk_pages(pages, 300, 50) if c.location == "Aksiyonlar, all rows"]
    assert len(whole) == 1 and "AKS-039" in whole[0].text


def test_sample_pdfs_load_with_page_numbers():
    pages = load(DOCUMENTS / "ESD-PR-001 ESD Kontrol Proseduru.pdf")
    assert [p.location for p in pages] == ["p. 1", "p. 2"]
    assert "1 MΩ" in pages[0].text


def test_rrf_rewards_agreement():
    fused = rrf([[1, 2, 3], [3, 1, 4]])
    assert max(fused, key=fused.get) == 1
    assert fused[3] > fused[2]


def test_hybrid_search_finds_codes_and_meaning(tmp_path, folder):
    llm = FakeLLM()
    index = Index(tmp_path / "index.sqlite3")
    index.sync(folder, llm.embed)
    assert search(index, llm.embed, "ESD-F-03", k=1, mode="keyword")[0].chunk.source == "esd.md"
    assert search(index, llm.embed, "tedarikçi denetimleri", k=1)[0].chunk.source == "supplier.md"
    assert search(Index(tmp_path / "empty.sqlite3"), llm.embed, "anything") == []
