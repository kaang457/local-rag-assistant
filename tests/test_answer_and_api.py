import json

import pytest
from fastapi.testclient import TestClient

from ragassist.answer import Turn, cited, messages
from ragassist.api import create_app
from ragassist.assistant import Assistant
from ragassist.chunking import Chunk
from ragassist.config import Settings
from ragassist.evaluate import Question, check_answer
from ragassist.search import Hit
from tests.fakes import FakeLLM


def hit(text: str, source: str = "esd.md") -> Hit:
    return Hit(Chunk(source, "p. 1", text), 1.0)


def test_cited_reads_single_and_grouped_citations():
    assert cited("Direnç 1 MΩ [2]. Nem aralığı [1, 3]. Yine [2].", 3) == [2, 1, 3]
    assert cited("Uydurma kaynak [9].", 3) == []


def test_prompt_numbers_sources_and_keeps_history():
    msgs = messages("Peki nem?", [hit("Nem %30-%70.")], [Turn("Direnç?", "1 MΩ [1].")])
    assert "[1] esd.md, p. 1\nNem %30-%70." in msgs[0]["content"]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]


def test_answer_check_accepts_alternatives_and_refusals():
    q = Question("q", "?", "exact-term", "a.pdf", (), ("0,65|0.65",))
    assert check_answer(q, "AQL 0.65 uygulanır [1].", [hit("x", "a.pdf")]) == (True, True)
    unanswerable = Question("u", "?", "unanswerable")
    assert check_answer(unanswerable, "Bu bilgi belgelerde yer almıyor.", [])[0]
    assert not check_answer(unanswerable, "Vade 60 gündür.", [])[0]


@pytest.fixture
def client(tmp_path):
    docs = tmp_path / "documents"
    docs.mkdir()
    (docs / "esd.md").write_text("Bileklik kayışı 1 MΩ seri dirençle topraklanır.", encoding="utf-8")
    llm = FakeLLM()
    assistant = Assistant(Settings(documents_dir=docs, index_dir=tmp_path / "index"), llm=llm)
    assistant.sync()
    with TestClient(create_app(assistant, sync_on_start=False)) as c:
        yield c, llm


def events(body: str) -> list[tuple[str, object]]:
    out = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_ask_streams_sources_tokens_and_citations(client):
    c, _ = client
    resp = c.post("/api/ask", json={"question": "Bileklik direnci ne olmalı?"})
    stream = events(resp.text)
    assert stream[0][0] == "sources" and stream[0][1][0]["citation"] == "esd.md, text"
    assert "".join(data for name, data in stream if name == "token") == "Bilekliğin direnci 1 MΩ olmalıdır [1]."
    done = stream[-1][1]
    assert stream[-1][0] == "done" and done["cited"] == [1] and done["timings"]["total_ms"] >= 0


def test_follow_up_is_rewritten_before_retrieval(client):
    c, llm = client
    c.post("/api/ask", json={"question": "Peki ya nem?", "history": [{"question": "Direnç?", "answer": "1 MΩ"}]})
    assert "Rewrite the last question" in llm.prompts[0][0]["content"]


def test_bad_rewrite_cannot_hide_what_the_question_finds(tmp_path):
    docs = tmp_path / "documents"
    docs.mkdir()
    (docs / "esd.md").write_text("Bileklik kayışı 1 MΩ seri dirençle topraklanır.", encoding="utf-8")
    (docs / "supplier.md").write_text("Tedarikçi performans puanı: kalite yüzde 50, teslimat yüzde 30.", encoding="utf-8")
    # The fake model "rewrites" every question into the earlier ESD topic.
    assistant = Assistant(Settings(documents_dir=docs, index_dir=tmp_path / "index", top_k=2), llm=FakeLLM("bileklik direnci"))
    assistant.sync()
    hits, _, _ = assistant.ask("tedarikçi performans puanı", [Turn("Bileklik?", "1 MΩ [1].")])
    assert "supplier.md" in {h.chunk.source for h in hits}


def test_upload_rejects_unsupported_files_and_indexes_new_ones(client):
    c, _ = client
    assert c.post("/api/documents", files={"file": ("x.exe", b"MZ")}).status_code == 400
    assert c.post("/api/documents", files={"file": ("../evil.md", b"x")}).json()["name"] == "evil.md"
    resp = c.post("/api/documents", files={"file": ("nem.md", "Bağıl nem %30 ile %70 arasında tutulur.".encode())})
    assert resp.status_code == 200
    assert {d["name"] for d in c.get("/api/documents").json()} == {"esd.md", "evil.md", "nem.md"}
    assert c.get("/api/health").json()["chunks"] == 3


def test_empty_question_is_rejected(client):
    c, _ = client
    assert c.post("/api/ask", json={"question": ""}).status_code == 422
