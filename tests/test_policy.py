from autoresearch_core.policy import (
    decide_branch, should_terminate, detect_plateau, should_promote_dead_end,
    measure, decide,
)
from autoresearch_core.types import MetricSpec, ExperimentResult, VerdictRecord


def test_decide_branch():
    assert decide_branch("supported") == "finalize"
    assert decide_branch("refuted") == "revise"
    assert decide_branch("inconclusive") == "revise"


def test_should_terminate():
    assert should_terminate(2, 8, "supported") == (True, "supported")
    assert should_terminate(8, 8, "refuted") == (True, "exhausted")
    assert should_terminate(3, 8, "refuted") == (False, "active")


def test_detect_plateau():
    assert detect_plateau(["refuted", "refuted"], window=3) is False       # too few
    assert detect_plateau(["refuted", "inconclusive", "refuted"]) is True
    assert detect_plateau(["refuted", "supported", "refuted"]) is False


def test_promotion_authority_deterministic_only():
    det = VerdictRecord("refuted", "deterministic", "deterministic", "x<y")
    llm = VerdictRecord("refuted", "reviewer", "llm", "looks wrong")
    ok = VerdictRecord("supported", "deterministic", "deterministic", "x>=y")
    assert should_promote_dead_end(det) is True
    assert should_promote_dead_end(llm) is False    # advisory only
    assert should_promote_dead_end(ok) is False      # supported never promotes


def test_measure_and_decide_facades():
    spec = MetricSpec("recall", ">=", 0.8)
    rec = measure(spec, ExperimentResult(metrics={"recall": 0.9}, exit_code=0))
    assert rec.verdict == "supported" and rec.evidence_level == "deterministic"
    assert decide(2, 8, rec.verdict) == ("finalize", True, "supported")
    assert decide(3, 8, "refuted") == ("revise", False, "active")
