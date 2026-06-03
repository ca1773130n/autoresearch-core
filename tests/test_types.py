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
    import dataclasses, pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.target = 0.5  # type: ignore[misc]
