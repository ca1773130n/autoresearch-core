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
