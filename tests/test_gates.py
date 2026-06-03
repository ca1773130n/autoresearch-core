from autoresearch_core.gates import resolve_gates, check_gate
from autoresearch_core.types import GateState


def test_resolve_defaults_on():
    g = resolve_gates({}, no_gates=False)
    assert g.execute is True and g.kg_write is True


def test_resolve_disable_execute_via_experiment_execution_key():
    g = resolve_gates({"research_gates": {"experiment_execution": False}}, no_gates=False)
    assert g.execute is False and g.kg_write is True


def test_no_gates_disables_all():
    g = resolve_gates({"research_gates": {"experiment_execution": True}}, no_gates=True)
    assert g.execute is False and g.kg_write is False


def test_check_gate_pause_vs_proceed():
    gates = GateState(execute=True, kg_write=True)
    paused = check_gate(gates, "execute", approved=False)
    assert paused.proceed is False and paused.pending_gate == "execute"
    assert check_gate(gates, "execute", approved=True).proceed is True
    assert check_gate(GateState(execute=False), "execute", approved=False).proceed is True


def test_check_gate_unknown_gate_raises():
    import pytest
    with pytest.raises(ValueError):
        check_gate(GateState(), "nope", approved=False)  # type: ignore[arg-type]


def test_resolve_gates_non_dict_research_gates_treated_as_empty():
    # When research_gates is a non-dict (e.g. True), fall back to defaults (both on).
    g = resolve_gates({"research_gates": True}, no_gates=False)
    assert g.execute is True and g.kg_write is True

    g2 = resolve_gates({"research_gates": 1}, no_gates=False)
    assert g2.execute is True and g2.kg_write is True

    g3 = resolve_gates({"research_gates": "yes"}, no_gates=False)
    assert g3.execute is True and g3.kg_write is True
