"""A runbook index that picks up file changes without a restart.

The API loads its runbooks once at startup. During an incident, a team
can edit a runbook while the service is running, and the old text kept
being served until someone restarted it. This wrapper checks the files
on each use: it hashes every markdown file in the folder, and when the
hash set differs from the one the current index was built from, it loads
and indexes the folder again.

Hashing the contents, not the timestamps, keeps the check exact. A save
that changes nothing does not trigger a reload, and a fast edit that
lands inside one timestamp tick still does.
"""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

from runbook_assistant.index import BM25Index
from runbook_assistant.loading import load_runbooks, load_sections


def _fingerprint(runbooks_dir: Path) -> tuple[tuple[str, str], ...]:
    if not runbooks_dir.is_dir():
        raise FileNotFoundError(f"runbooks directory not found: {runbooks_dir}")
    entries = []
    for path in sorted(runbooks_dir.glob("*.md")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append((path.name, digest))
    return tuple(entries)


class ReloadingIndex:
    """BM25 index over a runbook folder, rebuilt when the folder changes."""

    def __init__(self, runbooks_dir: str | Path):
        self._dir = Path(runbooks_dir)
        self._lock = threading.Lock()
        self._fingerprint: tuple[tuple[str, str], ...] | None = None
        self._runbooks: list = []
        self._index = BM25Index([])
        self.refresh_if_changed()

    def refresh_if_changed(self) -> bool:
        """Reload when any runbook file was added, removed, or edited."""
        current = _fingerprint(self._dir)
        with self._lock:
            if current == self._fingerprint:
                return False
            self._runbooks = load_runbooks(self._dir)
            self._index = BM25Index(load_sections(self._dir))
            self._fingerprint = current
            return True

    @property
    def index(self) -> BM25Index:
        self.refresh_if_changed()
        return self._index

    @property
    def runbook_count(self) -> int:
        self.refresh_if_changed()
        return len(self._runbooks)

    @property
    def section_count(self) -> int:
        self.refresh_if_changed()
        return len(self._index)
