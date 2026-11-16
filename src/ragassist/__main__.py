"""Command line: serve | ingest | ask | eval."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .answer import cited
from .assistant import Assistant
from .config import Settings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ragassist")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="run the web app")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)
    sub.add_parser("ingest", help="index new and changed files in the documents folder")
    ask = sub.add_parser("ask", help="ask one question from the terminal")
    ask.add_argument("question")
    ev = sub.add_parser("eval", help="measure retrieval (and optionally answers) on a question set")
    ev.add_argument("--questions", type=Path, default=Path("eval/questions.jsonl"))
    ev.add_argument("--answers", action="store_true", help="also generate answers and check expected facts")
    ev.add_argument("--out", type=Path, default=Path("eval/results.md"))
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    settings = Settings.from_env()

    if args.command == "serve":
        import uvicorn

        from .api import create_app

        uvicorn.run(create_app(), host=args.host, port=args.port)
        return

    assistant = Assistant(settings)
    report = assistant.sync()
    print(f"index: {report.chunks} chunks; added {report.added or '-'}; updated {report.updated or '-'}; failed {report.failed or '-'}")
    if args.command == "ingest":
        return

    if args.command == "ask":
        hits, tokens, timings = assistant.ask(args.question, [])
        text = ""
        for token in tokens:
            text += token
            sys.stdout.write(token)
            sys.stdout.flush()
        print("\n")
        for n in cited(text, len(hits)):
            print(f"[{n}] {hits[n - 1].chunk.citation}")
        print(timings.marks)
        return

    from .evaluate import run

    run(assistant, args.questions, args.out, with_answers=args.answers)


if __name__ == "__main__":
    main()
