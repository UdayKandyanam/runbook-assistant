from pathlib import Path

import pytest

from runbook_assistant.answer import answer_question
from runbook_assistant.index import BM25Index
from runbook_assistant.loading import load_sections

RUNBOOKS = Path(__file__).resolve().parent.parent / "runbooks"


@pytest.fixture(scope="module")
def index() -> BM25Index:
    return BM25Index(load_sections(RUNBOOKS))


def test_answer_cites_sources(index):
    answer = answer_question(index, "A pod is in CrashLoopBackOff and keeps restarting. What should I check?")
    assert answer.answered
    assert answer.excerpts
    top = answer.excerpts[0]
    assert top.source == "crashloopbackoff.md"
    assert top.heading  # every claim carries its heading
    rendered = answer.to_text()
    assert "crashloopbackoff.md" in rendered
    # Weak tail matches from unrelated runbooks get filtered out.
    assert all(e.source == "crashloopbackoff.md" for e in answer.excerpts)


def test_certificate_question_hits_certificate_runbook(index):
    answer = answer_question(index, "Users are seeing x509 certificate expired errors. How do I check the expiry date?")
    assert answer.answered
    assert answer.excerpts[0].source == "expired-certificates.md"


def test_unrelated_question_is_refused(index):
    answer = answer_question(index, "How do I bake a sourdough loaf with a crisp crust?")
    assert not answer.answered
    assert answer.excerpts == []
    assert "do not cover" in answer.message


def test_answer_dict_shape(index):
    answer = answer_question(index, "How do I roll back a bad deployment?")
    data = answer.to_dict()
    assert data["answered"] is True
    assert data["question"].startswith("How do I roll back")
    assert isinstance(data["sources"], list)
    first = data["sources"][0]
    assert set(first) == {"source", "heading", "score", "text"}
    assert first["source"] == "rollback-deployment.md"
