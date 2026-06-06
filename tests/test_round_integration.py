# tests/test_round_integration.py
"""One full round, all ports faked: gather -> select -> propose -> decide -> record."""
from autoresearch_core.rounds import (
    decide_round, patch_hash, resolve_autonomy, select_evidence,
)
from autoresearch_core.types import (
    EvalCheck, EvalReport, Finding, PatchEntry, RoundPatch, RoundRecord,
)


def _run_round(config, findings, eval_report, seen):
    autonomy = resolve_autonomy(config)
    if autonomy.kill_switch:
        return RoundRecord(round_id="r1", status="skipped", detail="kill switch is on")
    evidence = select_evidence(findings, max_items=25, min_items=2)
    if not evidence:
        return RoundRecord(round_id="r1", status="skipped", detail="not enough evidence")
    entry = PatchEntry(path="commands/execute-phase.md", kind="markdown", op="modify",
                       content="improved", rationale=evidence[0].content)
    patch = RoundPatch(round_id="r1", entries=(entry,), summary="apply takeaway", confidence=0.9)
    status, detail = decide_round(patch, autonomy, seen, eval_report)
    return RoundRecord(round_id="r1", status=status, detail=detail,
                       evidence_count=len(evidence), patch_hash=patch_hash(patch),
                       eval_report=eval_report)


FINDINGS = [
    Finding(kind="takeaway", content="executor forgets to commit", source="s1", created_at="2026-06-01"),
    Finding(kind="decision", content="always run lint", source="s2", created_at="2026-06-02"),
]
GREEN = EvalReport(checks=(EvalCheck("lint", 0),))
RED = EvalReport(checks=(EvalCheck("jest", 1),))


def test_review_mode_round_awaits_review():
    rec = _run_round({}, FINDINGS, GREEN, set())
    assert rec.status == "evaluated" and rec.evidence_count == 2


def test_auto_mode_green_round_applies():
    rec = _run_round({"harness": {"autonomy": "auto"}}, FINDINGS, GREEN, set())
    assert rec.status == "applied"


def test_failed_eval_rejects_and_hash_feeds_dedupe():
    rec = _run_round({"harness": {"autonomy": "auto"}}, FINDINGS, RED, set())
    assert rec.status == "rejected"
    rec2 = _run_round({"harness": {"autonomy": "auto"}}, FINDINGS, GREEN, {rec.patch_hash})
    assert rec2.status == "skipped"  # deterministic rejection became a dead-end


def test_kill_switch_skips_before_anything():
    rec = _run_round({"harness": {"kill_switch": True}}, FINDINGS, GREEN, set())
    assert rec.status == "skipped"


def test_thin_evidence_skips():
    rec = _run_round({}, FINDINGS[:1], GREEN, set())
    assert rec.status == "skipped"
