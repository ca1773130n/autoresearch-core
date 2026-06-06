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


from autoresearch_core.rounds import patch_hash, should_skip_patch
from autoresearch_core.types import PatchEntry, RoundPatch


def _patch(summary="tighten executor prompt", path="commands/execute-phase.md"):
    e = PatchEntry(path=path, kind="markdown", op="modify", content="x", rationale="r")
    return RoundPatch(round_id="r1", entries=(e,), summary=summary, confidence=0.8)


def test_patch_hash_stable_16_hex():
    h = patch_hash(_patch())
    assert h == patch_hash(_patch())
    assert len(h) == 16 and int(h, 16) >= 0


def test_patch_hash_ignores_case_whitespace_and_round_id():
    a = _patch(summary="Tighten   Executor prompt")
    b = RoundPatch(round_id="r999", entries=_patch().entries,
                   summary="tighten executor prompt", confidence=0.1)
    assert patch_hash(a) == patch_hash(b)


def test_patch_hash_differs_on_different_target():
    assert patch_hash(_patch()) != patch_hash(_patch(path="agents/grd-executor.md"))


def test_should_skip_patch():
    h = patch_hash(_patch())
    assert should_skip_patch(h, {h}) is True
    assert should_skip_patch(h, set()) is False


import json as _json

from autoresearch_core.rounds import validate_round_patch
from autoresearch_core.types import AutonomyState


def _entry(**over):
    base = dict(path="commands/x.md", kind="markdown", op="modify",
                content="body", rationale="because")
    base.update(over)
    return PatchEntry(**base)


def _vpatch(*entries, confidence=0.8):
    return RoundPatch(round_id="r1", entries=tuple(entries), summary="s", confidence=confidence)


AUTO = AutonomyState()


def test_validate_accepts_well_formed_patch():
    assert validate_round_patch(_vpatch(_entry()), AUTO) == []


def test_validate_rejects_empty_patch_and_bad_confidence():
    errs = validate_round_patch(_vpatch(confidence=1.5), AUTO)
    assert any("no entries" in e for e in errs)
    assert any("confidence" in e for e in errs)


def test_validate_rejects_traversal_absolute_and_git_paths():
    for bad in ("../etc/passwd", "/etc/passwd", ".git/config", "a/../../b", "C:\\x"):
        errs = validate_round_patch(_vpatch(_entry(path=bad)), AUTO)
        assert errs, bad


def test_validate_rejects_kind_outside_allowed_targets():
    md_only = AutonomyState(allowed_targets=("markdown",))
    errs = validate_round_patch(_vpatch(_entry(kind="code", path="lib/x.ts")), md_only)
    assert any("allowed_targets" in e for e in errs)


def test_validate_content_rules():
    errs = validate_round_patch(_vpatch(_entry(op="delete", content="x")), AUTO)
    assert any("delete must not carry content" in e for e in errs)
    errs = validate_round_patch(_vpatch(_entry(content=None)), AUTO)
    assert any("requires content" in e for e in errs)
    errs = validate_round_patch(_vpatch(_entry(rationale="  ")), AUTO)
    assert any("rationale" in e for e in errs)


def test_validate_deny_list():
    errs = validate_round_patch(
        _vpatch(_entry(path="bin/harness_driver.py", kind="code")), AUTO,
        deny_paths=("bin/harness_driver.py",),
    )
    assert any("deny-listed" in e for e in errs)


def test_validate_config_kind_must_be_json():
    errs = validate_round_patch(
        _vpatch(_entry(path="some.json", kind="config", content="{not json")), AUTO)
    assert any("valid JSON" in e for e in errs)


def test_validate_protects_harness_config_block():
    current = {"autonomy": "review", "kill_switch": False}
    sneaky = _json.dumps({"harness": {"autonomy": "auto", "kill_switch": False}})
    errs = validate_round_patch(
        _vpatch(_entry(path=".planning/config.json", kind="config", content=sneaky)),
        AUTO, current_harness=current)
    assert any("harness config block" in e for e in errs)

    unchanged = _json.dumps({"harness": current, "other": 1})
    errs = validate_round_patch(
        _vpatch(_entry(path=".planning/config.json", kind="config", content=unchanged)),
        AUTO, current_harness=current)
    assert errs == []


def test_validate_may_not_delete_project_config():
    errs = validate_round_patch(
        _vpatch(_entry(path=".planning/config.json", kind="config", op="delete", content=None)),
        AUTO)
    assert any("may not delete the project config" in e for e in errs)
