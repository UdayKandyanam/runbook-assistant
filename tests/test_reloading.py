"""Tests for the reloading index used by the HTTP API.

Each test builds its own small runbook folder in tmp_path, so an edit
here never touches the bundled runbooks.
"""

from runbook_assistant.answer import answer_question
from runbook_assistant.reloading import ReloadingIndex

FIRST = """# Widget failures

## Symptoms

The widget frobs the gizmo and the gizmo stops responding.

## First checks

Restart the widget and watch the gizmo light.
"""

EDITED = """# Widget failures

## Symptoms

The widget frobs the gizmo and the gizmo stops responding.

## First checks

Restart the widget and watch the gizmo light.

## Escalation

Page the widget owner and quote the gizmo serial number.
"""

SECOND = """# Sprocket failures

## Symptoms

The sprocket rattles and the belt slips under load.

## First checks

Tighten the sprocket and check the belt tension.
"""


def _store(tmp_path, files):
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    return ReloadingIndex(tmp_path)


def test_initial_load_counts(tmp_path):
    store = _store(tmp_path, {"widget.md": FIRST})
    assert store.runbook_count == 1
    assert store.section_count == 2


def test_no_change_means_no_reload(tmp_path):
    store = _store(tmp_path, {"widget.md": FIRST})
    assert store.refresh_if_changed() is False
    assert store.refresh_if_changed() is False


def test_edit_is_picked_up_and_answers_change(tmp_path):
    store = _store(tmp_path, {"widget.md": FIRST})
    before = answer_question(store.index, "Who do I page for a widget escalation?")
    assert before.answered is False

    (tmp_path / "widget.md").write_text(EDITED, encoding="utf-8")
    assert store.refresh_if_changed() is True
    assert store.section_count == 3

    after = answer_question(store.index, "Who do I page for a widget escalation?")
    assert after.answered is True
    assert after.excerpts[0].heading == "Escalation"
    assert store.refresh_if_changed() is False


def test_added_file_is_picked_up(tmp_path):
    store = _store(tmp_path, {"widget.md": FIRST})
    (tmp_path / "sprocket.md").write_text(SECOND, encoding="utf-8")
    assert store.refresh_if_changed() is True
    assert store.runbook_count == 2
    assert store.section_count == 4
    answer = answer_question(store.index, "The sprocket rattles and the belt slips")
    assert answer.answered is True
    assert answer.excerpts[0].source == "sprocket.md"


def test_removed_file_is_picked_up(tmp_path):
    store = _store(tmp_path, {"widget.md": FIRST, "sprocket.md": SECOND})
    assert store.runbook_count == 2
    (tmp_path / "sprocket.md").unlink()
    assert store.refresh_if_changed() is True
    assert store.runbook_count == 1
    assert store.section_count == 2
