"""Load markdown runbooks and split them into sections by heading."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


@dataclass
class Section:
    """One chunk of a runbook: the text under a single heading."""

    source: str  # file name, e.g. "crashloopbackoff.md"
    heading: str  # heading text; "(overview)" for text before the first heading
    level: int  # markdown heading level, 0 for the pre-heading overview
    text: str
    title: str = ""  # the runbook's own H1 title, for context

    @property
    def citation(self) -> str:
        return f"{self.source} > {self.heading}"


@dataclass
class Runbook:
    source: str
    title: str
    sections: list[Section] = field(default_factory=list)


def split_markdown(source: str, content: str) -> list[Section]:
    """Split one markdown document into sections at ATX headings."""
    sections: list[Section] = []
    title = ""
    heading = "(overview)"
    level = 0
    buffer: list[str] = []

    def flush() -> None:
        text = "\n".join(buffer).strip()
        if text:
            sections.append(
                Section(source=source, heading=heading, level=level, text=text, title=title)
            )

    for line in content.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            flush()
            buffer = []
            level = len(match.group(1))
            heading = match.group(2).strip()
            if level == 1 and not title:
                title = heading
        else:
            buffer.append(line)
    flush()

    # Sections parsed before the H1 still belong to the titled runbook.
    for section in sections:
        if not section.title:
            section.title = title
    return sections


def load_runbook(path: Path) -> Runbook:
    content = path.read_text(encoding="utf-8")
    sections = split_markdown(path.name, content)
    title = sections[0].title if sections else path.stem
    return Runbook(source=path.name, title=title, sections=sections)


def load_runbooks(runbooks_dir: str | Path) -> list[Runbook]:
    directory = Path(runbooks_dir)
    if not directory.is_dir():
        raise FileNotFoundError(f"runbooks directory not found: {directory}")
    return [load_runbook(path) for path in sorted(directory.glob("*.md"))]


def load_sections(runbooks_dir: str | Path) -> list[Section]:
    sections: list[Section] = []
    for runbook in load_runbooks(runbooks_dir):
        sections.extend(runbook.sections)
    return sections
