from runbook_assistant.index import BM25Index
from runbook_assistant.loading import Section


def make_section(source: str, heading: str, text: str) -> Section:
    return Section(source=source, heading=heading, level=2, text=text, title=heading)


def test_bm25_ranks_obvious_match_first():
    sections = [
        make_section("certs.md", "Expired certificates", "The certificate expired and TLS handshakes fail with x509 errors."),
        make_section("disk.md", "Node disk pressure", "The node disk is full and pods are being evicted."),
        make_section("rollback.md", "Rolling back", "Roll back the deployment to the previous revision."),
    ]
    index = BM25Index(sections)
    results = index.search("certificate expired x509 handshake", top_k=3)
    assert results[0][0].source == "certs.md"
    assert results[0][1] > 0


def test_bm25_no_overlap_returns_nothing():
    sections = [make_section("a.md", "Certificates", "Renew the certificate before it expires.")]
    index = BM25Index(sections)
    assert index.search("sourdough bread baking") == []


def test_bm25_repeated_relevant_terms_rank_higher():
    sections = [
        make_section("one.md", "Connections", "The database connection pool is exhausted."),
        make_section(
            "two.md",
            "Connection saturation",
            "Database connections are saturated. Too many connections open. "
            "Connection count keeps climbing past max_connections.",
        ),
    ]
    index = BM25Index(sections)
    results = index.search("database connections saturated", top_k=2)
    assert results[0][0].source == "two.md"
