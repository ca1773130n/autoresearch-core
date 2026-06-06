"""Round data shapes: frozen, defaulted, and EvalReport.passed derivation."""
import dataclasses

import pytest

from autoresearch_core.types import (
    AutonomyState, EvalCheck, EvalReport, Finding, PatchEntry, RoundPatch, RoundRecord,
)


def test_finding_defaults_and_frozen():
    f = Finding(kind="takeaway", content="prefer X", source="session:abc")
    assert f.created_at == ""
    with pytest.raises(dataclasses.FrozenInstanceError):
        f.content = "mutated"  # type: ignore[misc]


def test_patch_entry_defaults():
    e = PatchEntry(path="commands/x.md", kind="markdown", op="modify",
                   content="body", rationale="because")
    assert e.evidence_refs == ()


def test_round_patch_holds_entries_tuple():
    e = PatchEntry(path="a.md", kind="markdown", op="create", content="x", rationale="r")
    p = RoundPatch(round_id="r1", entries=(e,), summary="add a.md", confidence=0.9)
    assert p.entries[0].path == "a.md"


def test_eval_report_passed_all_zero():
    rep = EvalReport(checks=(EvalCheck("lint", 0), EvalCheck("tsc", 0)))
    assert rep.passed is True


def test_eval_report_failed_any_nonzero():
    rep = EvalReport(checks=(EvalCheck("lint", 0), EvalCheck("jest", 1, "2 failed")))
    assert rep.passed is False


def test_eval_report_empty_checks_passes():
    assert EvalReport(checks=()).passed is True


def test_autonomy_state_defaults():
    a = AutonomyState()
    assert a.mode == "review"
    assert a.kill_switch is False
    assert a.min_confidence == 0.7
    assert a.min_interval_hours == 24
    assert a.allowed_targets == ("markdown", "config", "code")


def test_round_record_optionals_default_none():
    r = RoundRecord(round_id="r1", status="skipped")
    assert r.patch_hash is None and r.eval_report is None and r.applied_sha is None
    assert r.detail == "" and r.evidence_count == 0
