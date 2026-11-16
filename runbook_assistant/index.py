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


# Ops questions use short forms and near words that the runbooks spell out
# in full. Each group below lists terms I treat as the same topic when a
# question is expanded: "cert" and "tls" both point at the certificate
# sections, and "restarting" points at the CrashLoopBackOff sections.
_SYNONYM_GROUPS = [
    ("crashloopbackoff", "crashloop", "restart", "restarts", "restarting", "restarted"),
    ("certificate", "certificates", "cert", "certs", "x509", "tls", "ssl"),
    ("expired", "expire", "expires", "expiry", "expiration"),
    ("rollback", "revert", "reverts", "reverted", "undo", "downgrade"),
    ("database", "db", "postgres", "postgresql"),
    ("saturated", "saturation", "exhausted", "exhaustion", "maxed"),
    ("deploy", "deploys", "deployment", "deployments"),
    ("exit", "exits", "exited", "exiting"),
    ("backlog", "backlogged", "lag", "lagging"),
    ("evicted", "eviction", "evictions"),
    ("kubernetes", "k8s"),
]

# One way links where a group would be too loose. "memory" on its own is a
# plain topic word, so it stays unexpanded; the abbreviations point at it.
_EXTRA_EXPANSIONS = {
    "oom": ("memory", "killed"),
    "oomkill": ("memory", "killed", "oom"),
    "oomkilled": ("memory", "killed", "oom"),
    "crash": ("crashloopbackoff",),
    "loop": ("crashloopbackoff",),
    "rollback": ("roll", "back"),
    "undo": ("roll", "back"),
    "evicted": ("disk", "pressure"),
    "eviction": ("disk", "pressure"),
    "evictions": ("disk", "pressure"),
}


def _build_group_expansions() -> dict[str, tuple[str, ...]]:
    expansions: dict[str, set[str]] = {}
    for group in _SYNONYM_GROUPS:
        for term in group:
            expansions.setdefault(term, set()).update(
                mate for mate in group if mate != term
            )
    return {term: tuple(sorted(mates)) for term, mates in expansions.items()}


GROUP_EXPANSIONS = _build_group_expansions()

EXPANSIONS: dict[str, tuple[str, ...]] = {}
for _term in set(GROUP_EXPANSIONS) | set(_EXTRA_EXPANSIONS):
    _mates = set(GROUP_EXPANSIONS.get(_term, ())) | set(_EXTRA_EXPANSIONS.get(_term, ()))
    EXPANSIONS[_term] = tuple(sorted(_mates))


def expand_terms(terms: list[str]) -> list[str]:
    """Add the mapped mates of each term, keeping the original order."""
    expanded: list[str] = []
    seen: set[str] = set()
    for term in terms:
        for candidate in (term, *EXPANSIONS.get(term, ())):
            if candidate not in seen:
                seen.add(candidate)
                expanded.append(candidate)
    return expanded


# Mates count less than a word the question actually used, and the two
# kinds count differently. A group mate is a near word, so it counts a
# quarter: at a half, the canary runbook section that mentions
# CrashLoopBackOff in passing scored high enough on a CrashLoopBackOff
# question to pass the relative floor in answer.py and show up as a
# second answer excerpt. A one way link is the same term in short form
# ("oomkilled" for a section that spells out memory and killed), so it
# counts a half: at a quarter the OOMKilled question kept scoring the
# canary section first on exact words like "container".
GROUP_WEIGHT = 0.25
EXTRA_WEIGHT = 0.5


def _weighted_terms(terms: list[str]) -> dict[str, float]:
    weighted: dict[str, float] = {term: 1.0 for term in terms}
    for term in terms:
        for mate in GROUP_EXPANSIONS.get(term, ()):
            weighted.setdefault(mate, GROUP_WEIGHT)
        for mate in _EXTRA_EXPANSIONS.get(term, ()):
            if weighted.get(mate, 0.0) < EXTRA_WEIGHT:
                weighted[mate] = EXTRA_WEIGHT
    return weighted


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
        return self._score_weighted({term: 1.0 for term in query_terms}, doc_index)

    def _score_weighted(self, weighted_terms: dict[str, float], doc_index: int) -> float:
        if not self._avg_length:
            return 0.0
        freqs = self._term_freqs[doc_index]
        length = self._doc_lengths[doc_index]
        total = 0.0
        for term, weight in weighted_terms.items():
            tf = freqs.get(term, 0)
            if not tf:
                continue
            denom = tf + self.k1 * (1 - self.b + self.b * length / self._avg_length)
            total += weight * self._idf(term) * (tf * (self.k1 + 1) / denom)
        return total

    def search(self, query: str, top_k: int = 3) -> list[tuple[Section, float]]:
        """Return up to top_k (section, score) pairs with a positive score."""
        terms = tokenize(query)
        if not terms:
            return []
        weighted = _weighted_terms(terms)
        scored = [
            (section, self._score_weighted(weighted, i))
            for i, section in enumerate(self.sections)
        ]
        scored = [pair for pair in scored if pair[1] > 0]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]
