from autoresearch_core.verdict import compare, DeterministicVerdict
from autoresearch_core.types import MetricSpec, ExperimentResult


def test_compare_all_operators():
    assert compare(0.8, ">=", 0.8) is True
    assert compare(199, "<", 200) is True
    assert compare(5, "==", 5) is True
    assert compare(5, ">", 5) is False
    assert compare(5, "<=", 4) is False


def test_deterministic_supported_and_refuted():
    strat = DeterministicVerdict()
    spec = MetricSpec("recall", ">=", 0.8)
    rec = strat.evaluate(spec, ExperimentResult(metrics={"recall": 0.9}, exit_code=0))
    assert rec.verdict == "supported" and rec.evidence_level == "deterministic"
    assert rec.detail == "recall=0.9 >= 0.8 → pass"
    rec2 = strat.evaluate(spec, ExperimentResult(metrics={"recall": 0.5}, exit_code=0))
    assert rec2.verdict == "refuted"


def test_deterministic_inconclusive_paths():
    strat = DeterministicVerdict()
    spec = MetricSpec("recall", ">=", 0.8)
    bad = strat.evaluate(spec, ExperimentResult(metrics={}, exit_code=1, failure_class="H2"))
    assert bad.verdict == "inconclusive" and "H2" in bad.detail
    missing = strat.evaluate(spec, ExperimentResult(metrics={"other": 1.0}, exit_code=0))
    assert missing.verdict == "inconclusive" and "not reported" in missing.detail
