"""Optional FastAPI adapter over the runbook assistant core.

Install the extra and run it:

    pip install -e ".[api]"
    python -m runbook_assistant serve --port 8000

Or serve this module directly with `uvicorn app:app`. Set RUNBOOKS_DIR to
point at a different folder of runbooks. Edits, additions, and removals in
that folder are picked up on the next request, with no restart.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from runbook_assistant.answer import answer_question
from runbook_assistant.reloading import ReloadingIndex

RUNBOOKS_DIR = Path(os.environ.get("RUNBOOKS_DIR", Path(__file__).parent / "runbooks"))

_store = ReloadingIndex(RUNBOOKS_DIR)

app = FastAPI(title="Runbook Assistant")


class AskRequest(BaseModel):
    question: str
    top_k: int = 3


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "runbooks": _store.runbook_count,
        "sections": _store.section_count,
    }


@app.post("/ask")
def ask(request: AskRequest) -> dict:
    return answer_question(_store.index, request.question, top_k=request.top_k).to_dict()
