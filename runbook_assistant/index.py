"""BM25 ranking over runbook sections, implemented from scratch."""

from __future__ import annotations

import math
import re
from collections import Counter

from runbook_assistant.loading import Section

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Words that carry no topical signal in an ops question.
STOPWORDS = frozenset(
    """
    a an the is are was were do does did how what why when where which who
    i me my we our you your it its this that these those to of in on for
    with at by from and or not no if then than so can could should would
    """.split()
)


def tokenize(text: str) -> list[str]:
    return [tok for tok in _TOKEN_RE.findall(text.lower()) if tok not in STOPWORDS]


class BM25Index:
    """Okapi BM25 over a fixed list of sections."""

    def __init__(self, sections: list[Section], k1: float = 1.5, b: float = 0.75):
        self.sections = sections
        self.k1 = k1
        self.b = b
        # Headings repeat the key terms of a section, so index them with the body.
        self._doc_tokens: list[list[str]] = [
            tokenize(f"{section.heading} {section.heading} {section.text}")
            for section in sections
        ]
        self._doc_lengths = [len(tokens) for tokens in self._doc_tokens]
        self._avg_length = (
            sum(self._doc_lengths) / len(self._doc_lengths) if self._doc_lengths else 0.0
        )
        self._term_freqs: list[Counter[str]] = [Counter(t) for t in self._doc_tokens]
        doc_freq: Counter[str] = Counter()
        for freqs in self._term_freqs:
            for term in freqs:
                doc_freq[term] += 1
        self._doc_freq = doc_freq

    def __len__(self) -> int:
        return len(self.sections)

    def _idf(self, term: str) -> float:
        n = len(self.sections)
        df = self._doc_freq.get(term, 0)
        # Robertson's smoothed idf; stays positive even for common terms.
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def score(self, query_terms: list[str], doc_index: int) -> float:
        if not self._avg_length:
            return 0.0
        freqs = self._term_freqs[doc_index]
        length = self._doc_lengths[doc_index]
        total = 0.0
        for term in set(query_terms):
            tf = freqs.get(term, 0)
            if not tf:
                continue
            denom = tf + self.k1 * (1 - self.b + self.b * length / self._avg_length)
            total += self._idf(term) * (tf * (self.k1 + 1) / denom)
        return total

    def search(self, query: str, top_k: int = 3) -> list[tuple[Section, float]]:
        """Return up to top_k (section, score) pairs with a positive score."""
        terms = tokenize(query)
        if not terms:
            return []
        scored = [
            (section, self.score(terms, i))
            for i, section in enumerate(self.sections)
        ]
        scored = [pair for pair in scored if pair[1] > 0]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]
