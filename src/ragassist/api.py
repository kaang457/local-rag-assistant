"""HTTP API and the chat page.

POST /api/ask streams Server-Sent Events: one `sources` event, then `token`
events as the model writes, then `done` with the cited sources and timings.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from .answer import Turn, cited
from .assistant import Assistant
from .config import Settings
from .loaders import SUPPORTED
from .ollama import OllamaError

log = logging.getLogger("ragassist")
WEB = Path(__file__).parent / "web"
MAX_UPLOAD = 50 * 1024 * 1024


class TurnIn(BaseModel):
    question: str
    answer: str


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[TurnIn] = []


def sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def create_app(assistant: Assistant | None = None, sync_on_start: bool = True) -> FastAPI:
    # "syncing" starts true when a startup sync is coming, so /api/health never reports a
    # finished index before the first sync has even begun.
    state: dict = {"syncing": sync_on_start, "last_sync": None, "warm": False}

    def run_sync() -> None:
        state["syncing"] = True
        try:
            report = app.state.assistant.sync()
            if not state["warm"]:
                app.state.assistant.llm.warm()
                state["warm"] = True
            state["last_sync"] = report.__dict__
            log.info("index: %d chunks, added %s, failed %s", report.chunks, report.added, report.failed)
        except OllamaError as err:
            state["last_sync"] = {"error": str(err)}
            log.error("sync failed: %s", err)
        finally:
            state["syncing"] = False

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.assistant = assistant or Assistant(Settings.from_env())
        if sync_on_start:
            threading.Thread(target=run_sync, daemon=True).start()
        yield

    app = FastAPI(title="Local RAG assistant", lifespan=lifespan)

    @app.get("/", include_in_schema=False)
    def page() -> FileResponse:
        return FileResponse(WEB / "index.html")

    @app.get("/api/health")
    def health() -> dict:
        a: Assistant = app.state.assistant
        return {
            "models": a.llm.ready(),
            "chunks": len(a.index.chunks),
            "syncing": state["syncing"],
            "last_sync": state["last_sync"],
        }

    @app.get("/api/documents")
    def documents() -> list[dict]:
        return [{"name": name, "chunks": chunks} for name, chunks in app.state.assistant.index.files()]

    @app.post("/api/documents")
    async def upload(file: UploadFile) -> dict:
        name = Path(file.filename or "").name
        if Path(name).suffix.lower() not in SUPPORTED or not re.fullmatch(r"[\w .()\-]+", name):
            raise HTTPException(400, f"unsupported file; allowed: {', '.join(sorted(SUPPORTED))}")
        data = await file.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "file larger than 50 MB")
        folder = app.state.assistant.settings.documents_dir
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
        run_sync()
        return {"name": name, "last_sync": state["last_sync"]}

    @app.post("/api/sync")
    def sync() -> dict:
        run_sync()
        return state["last_sync"]

    @app.post("/api/ask")
    def ask(body: AskIn) -> StreamingResponse:
        a: Assistant = app.state.assistant
        history = [Turn(t.question, t.answer) for t in body.history]

        def events() -> Iterator[str]:
            try:
                hits, tokens, timings = a.ask(body.question.strip(), history)
                yield sse("sources", [{"n": n, "citation": h.chunk.citation, "text": h.chunk.text} for n, h in enumerate(hits, 1)])
                text = []
                for token in tokens:
                    text.append(token)
                    yield sse("token", token)
                yield sse("done", {"cited": cited("".join(text), len(hits)), "timings": timings.marks})
            except OllamaError as err:
                yield sse("error", str(err))

        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    return app
