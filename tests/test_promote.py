import pytest
from autoresearch_core.promote import (
    approach_hash, build_dead_end_record, should_skip, DeadEndRecord,
)
from autoresearch_core.types import Hypothesis, VerdictRecord


def test_approach_hash_is_normalized_and_stable():
    a = approach_hash("  Memoize The Tokenizer  ")
    b = approach_hash("memoize the tokenizer")
    assert a == b and len(a) == 16


def test_build_dead_end_record():
    h = Hypothesis(id="h1", iteration=2, statement="cache embeddings",
                   predicted_outcome="faster")
    rec = VerdictRecord("refuted", "deterministic", "deterministic", "latency=300 < 200 -> fail")
    de = build_dead_end_record(h, rec)
    assert isinstance(de, DeadEndRecord)
    assert de.statement == "cache embeddings" and de.iteration == 2
    assert de.evidence_level == "deterministic" and de.reason.endswith("fail")


def test_should_skip_against_known_hashes():
    seen = {approach_hash("cache embeddings")}
    assert should_skip("Cache Embeddings", seen) is True
    assert should_skip("use a bloom filter", seen) is False


def test_approach_hash_whitespace_normalization():
    # Internal runs of whitespace must collapse to a single space.
    assert approach_hash("cache   embeddings") == approach_hash("cache embeddings")
    assert approach_hash("cache\t\tembeddings") == approach_hash("cache embeddings")
    assert approach_hash("cache\n embeddings") == approach_hash("cache embeddings")


def test_build_dead_end_record_raises_on_non_deterministic_refutation():
    h = Hypothesis(id="h2", iteration=1, statement="use llm scoring",
                   predicted_outcome="better")
    # supported + llm — neither condition of should_promote_dead_end is met
    rec_supported = VerdictRecord("supported", "deterministic", "deterministic", "ok")
    with pytest.raises(ValueError, match="deterministic refutation"):
        build_dead_end_record(h, rec_supported)
    # refuted but evidence_level=llm — not deterministic
    rec_llm = VerdictRecord("refuted", "deterministic", "llm", "llm said no")
    with pytest.raises(ValueError, match="deterministic refutation"):
        build_dead_end_record(h, rec_llm)
