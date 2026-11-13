from pathlib import Path

from runbook_assistant.loading import load_sections, split_markdown

SAMPLE = """# Deploy guide

Intro text before any section.

## First step

Do the first thing.

## Second step

Do the second thing.
More detail here.

### A subsection

Nested detail.
"""


def test_split_by_heading():
    sections = split_markdown("deploy.md", SAMPLE)
    headings = [s.heading for s in sections]
    assert headings == ["Deploy guide", "First step", "Second step", "A subsection"]


def test_section_keeps_source_and_title():
    sections = split_markdown("deploy.md", SAMPLE)
    for section in sections:
        assert section.source == "deploy.md"
        assert section.title == "Deploy guide"
    assert "Do the first thing." in sections[1].text


def test_overview_chunk_for_text_before_first_heading():
    sections = split_markdown("plain.md", "Just a paragraph.\n\n## Later\n\nBody.\n")
    assert sections[0].heading == "(overview)"
    assert "Just a paragraph." in sections[0].text
    assert sections[1].heading == "Later"


def test_load_sections_from_bundled_runbooks():
    runbooks_dir = Path(__file__).resolve().parent.parent / "runbooks"
    sections = load_sections(runbooks_dir)
    sources = {s.source for s in sections}
    assert sources == {
        "canary-deployment-checks.md",
        "crashloopbackoff.md",
        "database-connection-saturation.md",
        "expired-certificates.md",
        "node-disk-pressure.md",
        "queue-backlog-triage.md",
        "rollback-deployment.md",
    }
    assert len(sections) == 33
