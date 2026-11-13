"""Command line entry point: `python -m runbook_assistant ask|list`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from runbook_assistant.answer import answer_question
from runbook_assistant.index import BM25Index
from runbook_assistant.loading import load_runbooks, load_sections

DEFAULT_RUNBOOKS = Path(__file__).resolve().parent.parent / "runbooks"


def _add_runbooks_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--runbooks",
        default=str(DEFAULT_RUNBOOKS),
        help="directory of markdown runbooks (default: %(default)s)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="runbook-assistant",
        description="Answer platform questions from a folder of runbooks.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ask = sub.add_parser("ask", help="ask a question")
    ask.add_argument("question", help="the question, in quotes")
    _add_runbooks_flag(ask)
    ask.add_argument("--format", choices=["text", "json"], default="text")
    ask.add_argument("--top-k", type=int, default=3, help="max sections to cite")

    list_cmd = sub.add_parser("list", help="show indexed runbooks and section counts")
    _add_runbooks_flag(list_cmd)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "list":
        runbooks = load_runbooks(args.runbooks)
        total = 0
        for runbook in runbooks:
            print(f"{runbook.source}: {len(runbook.sections)} sections ({runbook.title})")
            total += len(runbook.sections)
        print(f"{len(runbooks)} runbooks, {total} sections indexed")
        return 0

    if args.command == "ask":
        index = BM25Index(load_sections(args.runbooks))
        answer = answer_question(index, args.question, top_k=args.top_k)
        if args.format == "json":
            print(json.dumps(answer.to_dict(), indent=2))
        else:
            print(answer.to_text())
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
