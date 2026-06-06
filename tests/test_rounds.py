# tests/test_rounds.py
"""Pure round policy: autonomy resolution, evidence selection, validation,
dedupe, apply gate, and the decide_round facade."""
from autoresearch_core.rounds import resolve_autonomy


def test_resolve_autonomy_defaults_on_empty_config():
    a = resolve_autonomy({})
    assert a.mode == "review"
    assert a.kill_switch is False
    assert a.min_confidence == 0.7
    assert a.min_interval_hours == 24
    assert a.allowed_targets == ("markdown", "config", "code")


def test_resolve_autonomy_reads_harness_block():
    cfg = {"harness": {"autonomy": "auto", "kill_switch": True, "min_confidence": 0.9,
                       "min_interval_hours": 6, "allowed_targets": ["markdown"]}}
    a = resolve_autonomy(cfg)
    assert a.mode == "auto" and a.kill_switch is True
    assert a.min_confidence == 0.9 and a.min_interval_hours == 6
    assert a.allowed_targets == ("markdown",)


def test_resolve_autonomy_tolerates_garbage():
    cfg = {"harness": {"autonomy": "yolo", "kill_switch": "yes", "min_confidence": 7,
                       "min_interval_hours": -2, "allowed_targets": ["markdown", "exe", 3]}}
    a = resolve_autonomy(cfg)
    assert a.mode == "review"
    assert a.kill_switch is False
    assert a.min_confidence == 0.7
    assert a.min_interval_hours == 24
    assert a.allowed_targets == ("markdown",)


def test_resolve_autonomy_non_mapping_harness():
    assert resolve_autonomy({"harness": "bogus"}).mode == "review"


def test_resolve_autonomy_no_gates_forces_auto_but_not_kill_switch():
    cfg = {"harness": {"kill_switch": True}}
    a = resolve_autonomy(cfg, no_gates=True)
    assert a.mode == "auto"
    assert a.kill_switch is True


def test_resolve_autonomy_empty_targets_falls_back():
    a = resolve_autonomy({"harness": {"allowed_targets": []}})
    assert a.allowed_targets == ("markdown", "config", "code")
