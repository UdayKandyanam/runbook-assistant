import json
from pathlib import Path

from runbook_assistant.cli import main

RUNBOOKS = str(Path(__file__).resolve().parent.parent / "runbooks")


def test_cli_ask_json_shape(capsys):
    rc = main(["ask", "Pod keeps restarting with CrashLoopBackOff", "--runbooks", RUNBOOKS, "--format", "json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data) == {"question", "answered", "message", "sources"}
    assert data["answered"] is True
    assert data["sources"][0]["source"] == "crashloopbackoff.md"
    assert data["sources"][0]["heading"]


def test_cli_ask_refusal_json(capsys):
    rc = main(["ask", "What is the capital of France?", "--runbooks", RUNBOOKS, "--format", "json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["answered"] is False
    assert data["sources"] == []
    assert "do not cover" in data["message"]


def test_cli_list(capsys):
    rc = main(["list", "--runbooks", RUNBOOKS])
    assert rc == 0
    out = capsys.readouterr().out
    assert "crashloopbackoff.md" in out
    assert "canary-deployment-checks.md" in out
    assert "queue-backlog-triage.md" in out
    assert "7 runbooks, 33 sections indexed" in out
