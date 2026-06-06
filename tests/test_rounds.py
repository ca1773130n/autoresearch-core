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


from autoresearch_core.rounds import select_evidence
from autoresearch_core.types import Finding


def _f(kind, content, at):
    return Finding(kind=kind, content=content, source="s", created_at=at)


def test_select_evidence_priority_order():
    fs = [_f("question", "q", "2026-01-01"), _f("takeaway", "t", "2026-01-01"),
          _f("insight", "i", "2026-01-01"), _f("decision", "d", "2026-01-01")]
    out = select_evidence(fs, max_items=10, min_items=1)
    assert [x.kind for x in out] == ["takeaway", "decision", "insight", "question"]


def test_select_evidence_recency_breaks_ties():
    fs = [_f("takeaway", "old", "2026-01-01"), _f("takeaway", "new", "2026-02-01")]
    out = select_evidence(fs, max_items=10, min_items=1)
    assert [x.content for x in out] == ["new", "old"]


def test_select_evidence_caps_at_max_items():
    fs = [_f("insight", f"i{i}", "2026-01-01") for i in range(30)]
    assert len(select_evidence(fs, max_items=5, min_items=1)) == 5


def test_select_evidence_below_min_returns_empty():
    fs = [_f("takeaway", "only one", "2026-01-01")]
    assert select_evidence(fs, max_items=10, min_items=3) == ()
