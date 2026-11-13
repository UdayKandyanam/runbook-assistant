"""Build a grounded answer from the sections BM25 ranks highest.

The assistant is extractive on purpose: it quotes the runbook sections it
found and names the source for each one. When nothing scores well enough,
it says the runbooks do not cover the question.
"""

from __future__ import annotations

from dataclasses import dataclass

from runbook_assistant.index import BM25Index

# Below this top score, the match is too weak to present as an answer.
MIN_TOP_SCORE = 1.5

# Sections scoring far below the best match are noise; leave them out.
MIN_RELATIVE_SCORE = 0.4

REFUSAL = (
    "The runbooks I have do not cover that. I would rather say so than guess: "
    "check with the team that owns the service, and consider adding a runbook "
    "for it afterwards."
)


@dataclass
class Excerpt:
    source: str
    heading: str
    text: str
    score: float

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "heading": self.heading,
            "score": round(self.score, 3),
            "text": self.text,
        }


@dataclass
class Answer:
    question: str
    answered: bool
    excerpts: list[Excerpt]

    @property
    def message(self) -> str:
        return "" if self.answered else REFUSAL

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "answered": self.answered,
            "message": self.message,
            "sources": [excerpt.to_dict() for excerpt in self.excerpts],
        }

    def to_text(self) -> str:
        if not self.answered:
            return self.message
        blocks = []
        for excerpt in self.excerpts:
            blocks.append(
                f"From {excerpt.source} > {excerpt.heading}:\n{excerpt.text}"
            )
        return "\n\n".join(blocks)


def _trim(text: str, limit: int = 900) -> str:
    if len(text) <= limit:
        return text
    cut = text.rfind("\n", 0, limit)
    return text[: cut if cut > 0 else limit].rstrip() + "\n[...]"


def answer_question(index: BM25Index, question: str, top_k: int = 3) -> Answer:
    results = index.search(question, top_k=top_k)
    if not results or results[0][1] < MIN_TOP_SCORE:
        return Answer(question=question, answered=False, excerpts=[])
    floor = results[0][1] * MIN_RELATIVE_SCORE
    results = [pair for pair in results if pair[1] >= floor]
    excerpts = [
        Excerpt(source=section.source, heading=section.heading, text=_trim(section.text), score=score)
        for section, score in results
    ]
    return Answer(question=question, answered=True, excerpts=excerpts)
