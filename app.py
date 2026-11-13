"""Optional FastAPI adapter over the runbook assistant core.

Install the extra and run it:

    pip install -e ".[api]"
    uvicorn app:app

Set RUNBOOKS_DIR to point at a different folder of runbooks.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from runbook_assistant.answer import answer_question
from runbook_assistant.index import BM25Index
from runbook_assistant.loading import load_runbooks, load_sections

RUNBOOKS_DIR = Path(os.environ.get("RUNBOOKS_DIR", Path(__file__).parent / "runbooks"))

_runbooks = load_runbooks(RUNBOOKS_DIR)
_index = BM25Index(load_sections(RUNBOOKS_DIR))

app = FastAPI(title="Runbook Assistant")


class AskRequest(BaseModel):
    question: str
    top_k: int = 3


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "runbooks": len(_runbooks),
        "sections": len(_index),
    }


@app.post("/ask")
def ask(request: AskRequest) -> dict:
    return answer_question(_index, request.question, top_k=request.top_k).to_dict()
