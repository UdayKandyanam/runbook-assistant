"""HTTP layer tests for the FastAPI adapter in app.py.

These need the api extra. Without it the whole module skips, so the core
suite still passes on a plain dev install.
"""

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

import app as app_module  # noqa: E402
from runbook_assistant.cli import main  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app_module.app)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["runbooks"] == 7
    assert data["sections"] == 33


def test_ask_answered_question(client):
    response = client.post(
        "/ask",
        json={"question": "A pod is in CrashLoopBackOff and keeps restarting. What should I check?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["answered"] is True
    assert data["sources"][0]["source"] == "crashloopbackoff.md"


def test_ask_refused_question(client):
    response = client.post(
        "/ask",
        json={"question": "How do I bake a sourdough loaf with a crisp crust?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["answered"] is False
    assert data["sources"] == []
    assert "do not cover" in data["message"]


def test_serve_without_api_extra(monkeypatch, capsys):
    # A None entry in sys.modules makes the import fail the way it does on
    # a machine where the api extra was never installed.
    monkeypatch.setitem(sys.modules, "uvicorn", None)
    rc = main(["serve", "--port", "8000"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "api extra" in err
    assert "Traceback" not in err
