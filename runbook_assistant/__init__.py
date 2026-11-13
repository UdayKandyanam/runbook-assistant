"""Runbook Assistant: answer platform questions from a folder of runbooks."""

from runbook_assistant.answer import Answer, Excerpt, answer_question
from runbook_assistant.index import BM25Index
from runbook_assistant.loading import Section, load_sections

__all__ = [
    "Answer",
    "BM25Index",
    "Excerpt",
    "Section",
    "answer_question",
    "load_sections",
]

__version__ = "0.1.0"
