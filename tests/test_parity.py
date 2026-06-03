# tests/test_parity.py
"""Vectors transcribed from GRD lib/research/{verdict.ts,runner.ts,gates.ts}.
If GRD changes these behaviors, update here deliberately — do not loosen."""
import autoresearch_core as ac
from autoresearch_core.types import MetricSpec, ExperimentResult


def test_public_surface_exports():
    for name in [
        "MetricSpec", "ExperimentResult", "VerdictRecord", "GateState",
        "parse_metrics_line", "classify_run_failure", "compare",
        "DeterministicVerdict", "resolve_gates", "check_gate",
        "decide_branch", "should_terminate", "detect_plateau",
        "should_promote_dead_end", "measure", "decide",
        "approach_hash", "build_dead_end_record",
    ]:
        assert hasattr(ac, name), f"missing public export: {name}"


def test_end_to_end_supported_path():
    spec = MetricSpec("recall_at_10", ">=", 0.8)
    stdout = 'log line\n__RESULT__ {"recall_at_10": 0.83}\n'
    metrics = ac.parse_metrics_line(stdout)
    result = ExperimentResult(metrics=metrics, exit_code=0)
    rec = ac.DeterministicVerdict().evaluate(spec, result)
    assert rec.verdict == "supported"
    assert ac.decide_branch(rec.verdict) == "finalize"
    assert ac.should_promote_dead_end(rec) is False


def test_end_to_end_refuted_then_promote():
    spec = MetricSpec("latency_ms", "<", 200)
    result = ExperimentResult(metrics={"latency_ms": 300.0}, exit_code=0)
    rec = ac.DeterministicVerdict().evaluate(spec, result)
    assert rec.verdict == "refuted"
    assert ac.decide_branch(rec.verdict) == "revise"
    assert ac.should_promote_dead_end(rec) is True


def test_end_to_end_failed_run_is_inconclusive():
    spec = MetricSpec("x", ">=", 1)
    err = ExperimentResult(metrics={}, exit_code=127, failure_class="H2")
    rec = ac.DeterministicVerdict().evaluate(spec, err)
    assert rec.verdict == "inconclusive"
    assert ac.should_promote_dead_end(rec) is False  # inconclusive never promotes


def test_invalid_comparator_returns_false():
    assert ac.compare(1, "!=", 1) is False  # type: ignore[arg-type]


def test_exit_code_precedence_over_metrics():
    # non-zero exit -> inconclusive even when a metric is present
    spec = MetricSpec("x", ">=", 1)
    rec = ac.DeterministicVerdict().evaluate(
        spec, ExperimentResult(metrics={"x": 5.0}, exit_code=1, failure_class="H4")
    )
    assert rec.verdict == "inconclusive"
