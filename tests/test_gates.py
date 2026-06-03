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
