import dataclasses
import pytest
from autoresearch_core.types import (
    MetricSpec, ExperimentResult, VerdictRecord, Hypothesis, Takeaway, GateState,
)

def test_dataclasses_construct_and_are_frozen():
    spec = MetricSpec(metric_key="recall", comparator=">=", target=0.8)
    assert spec.metric_key == "recall" and spec.comparator == ">=" and spec.target == 0.8
    res = ExperimentResult(metrics={"recall": 0.9}, exit_code=0)
    assert res.failure_class == "none" and res.runner == "subprocess"
    rec = VerdictRecord(verdict="supported", strategy="deterministic",
                        evidence_level="deterministic", detail="ok")
    assert rec.raw_evidence_ref is None
    gates = GateState()
    assert gates.execute is True and gates.kg_write is True
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.target = 0.5  # type: ignore[misc]


def test_experiment_result_defensive_copy():
    # Mutating the source dict after construction must not alter .metrics.
    src = {"recall": 0.9, "latency_ms": 120.0}
    res = ExperimentResult(metrics=src, exit_code=0)
    src["recall"] = 0.0
    src["new_key"] = 999.0
    assert res.metrics["recall"] == 0.9
    assert "new_key" not in res.metrics


def test_experiment_result_metrics_is_still_frozen():
    # The defensive copy must not make metrics itself mutable via setattr.
    res = ExperimentResult(metrics={"x": 1.0}, exit_code=0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        res.metrics = {}  # type: ignore[misc]
