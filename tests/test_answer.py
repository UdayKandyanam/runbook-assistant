from pathlib import Path

import pytest

from runbook_assistant.answer import answer_question
from runbook_assistant.index import BM25Index
from runbook_assistant.loading import Section, load_sections

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


def test_canary_question_hits_canary_runbook(index):
    answer = answer_question(
        index,
        "The canary deployment has a much higher error rate than the stable "
        "version. Should I stop the canary rollout?",
    )
    assert answer.answered
    assert answer.excerpts[0].source == "canary-deployment-checks.md"


def test_backlog_question_hits_queue_runbook(index):
    answer = answer_question(
        index,
        "The queue backlog keeps growing and the consumers are falling "
        "behind. How do I check consumer lag?",
    )
    assert answer.answered
    assert answer.excerpts[0].source == "queue-backlog-triage.md"


def test_pod_restarts_question_hits_crashloop_runbook(index):
    answer = answer_question(index, "My pod keeps restarting and never becomes ready. What should I check first?")
    assert answer.answered
    assert answer.excerpts[0].source == "crashloopbackoff.md"


def test_oomkilled_question_hits_crashloop_runbook(index):
    # Before synonym handling this question scored the canary runbook
    # highest, because "oomkilled" matched nothing in the corpus.
    answer = answer_question(index, "The container was OOMKilled. What should I check?")
    assert answer.answered
    assert answer.excerpts[0].source == "crashloopbackoff.md"


def test_tls_cert_question_hits_certificate_runbook(index):
    answer = answer_question(index, "Our TLS cert expired last night. How do I check the expiry date?")
    assert answer.answered
    assert answer.excerpts[0].source == "expired-certificates.md"


def test_rollback_answer_stays_in_the_rollback_runbook(index):
    # The canary runbook has a section on stopping and rolling back, and it
    # scored above the relative floor for this question. It is a different
    # procedure, so it stays out of the rollback answer.
    answer = answer_question(index, "How do I roll back a bad deployment?")
    assert answer.answered
    assert len(answer.excerpts) >= 2
    assert all(e.source == "rollback-deployment.md" for e in answer.excerpts)


def test_oomkilled_answer_stays_in_the_crashloop_runbook(index):
    # The disk pressure runbook mentions containers and scored above the
    # floor here. It has nothing to do with an OOMKill, so it stays out.
    answer = answer_question(index, "The container was OOMKilled. What should I check?")
    assert answer.answered
    assert len(answer.excerpts) >= 2
    assert all(e.source == "crashloopbackoff.md" for e in answer.excerpts)


def test_trailing_excerpt_from_another_runbook_is_dropped():
    # Synthetic pair where the second runbook scores well on the same
    # words, so the relative floor alone would keep it.
    sections = [
        Section(
            source="rollback.md",
            heading="Roll back",
            level=2,
            text="Roll back the deployment with kubectl rollout undo. "
            "Check the deployment status after the roll back. A bad "
            "deployment gets a roll back first and questions later.",
        ),
        Section(
            source="canary.md",
            heading="Stop and roll back",
            level=2,
            text="Stop the canary and roll back the deployment. "
            "Roll back sends traffic to the stable deployment.",
        ),
        Section(
            source="rollback.md",
            heading="Verify",
            level=2,
            text="Verify the roll back worked and the deployment is "
            "healthy after the roll back of the bad deployment.",
        ),
        Section(
            source="certificates.md",
            heading="Renewal",
            level=2,
            text="Renew the expired certificate and check the expiry date "
            "with openssl before the tls handshake fails again.",
        ),
        Section(
            source="disk.md",
            heading="Cleanup",
            level=2,
            text="The node disk is full of old container images and log "
            "files. Remove the unused images to free disk space.",
        ),
        Section(
            source="queue.md",
            heading="Backlog",
            level=2,
            text="The queue backlog grows when consumers fall behind. "
            "Check consumer lag and add workers to drain the queue.",
        ),
    ]
    answer = answer_question(BM25Index(sections), "How do I roll back a bad deployment?")
    assert answer.answered
    assert answer.excerpts[0].source == "rollback.md"
    assert all(e.source == "rollback.md" for e in answer.excerpts)


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
