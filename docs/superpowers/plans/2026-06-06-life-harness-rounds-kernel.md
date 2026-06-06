# Life-Harness Rounds Kernel (autoresearch-core 0.2.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the pure life-harness round logic (types, policy, ports) to `autoresearch-core` and release 0.2.0.

**Architecture:** Pure decision-contracts only — frozen dataclasses in `types.py`, policy functions in a new `rounds.py`, I/O declared as `Protocol`s in `ports.py`. No filesystem, subprocess, or network access anywhere. Hosts (GRD first) bind the ports. Spec: `docs/superpowers/specs/2026-06-06-life-harness-rounds-design.md`.

**Tech Stack:** Python 3.11+, stdlib only, pytest. Repo conventions: one file per concern, frozen dataclasses, `Literal` types, tests mirror modules.

**Working directory:** `/Users/neo/Developer/Projects/autoresearch-core` (run `pip install -e ".[dev]"` once if pytest is missing).

---

### Task 1: Round data types in `types.py`

**Files:**
- Modify: `autoresearch_core/types.py` (append after `GateCheck`)
- Test: `tests/test_round_types.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_round_types.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_round_types.py -q`
Expected: FAIL — `ImportError: cannot import name 'Finding'`

- [ ] **Step 3: Append the types to `autoresearch_core/types.py`**

Append at end of file (the module already imports `dataclass` and `Literal`):

```python
FindingKind = Literal["insight", "decision", "question", "todo", "hypothesis", "takeaway"]
PatchKind = Literal["markdown", "config", "code"]
PatchOp = Literal["modify", "create", "delete"]
AutonomyMode = Literal["review", "auto"]
RoundStatus = Literal[
    "skipped", "gathered", "proposed", "validated", "evaluated", "applied", "rejected", "reverted"
]


@dataclass(frozen=True)
class Finding:
    """One Tesserae Session finding projected into the kernel."""
    kind: FindingKind
    content: str
    source: str
    created_at: str = ""


@dataclass(frozen=True)
class PatchEntry:
    path: str
    kind: PatchKind
    op: PatchOp
    content: str | None
    rationale: str
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoundPatch:
    round_id: str
    entries: tuple[PatchEntry, ...]
    summary: str
    confidence: float


@dataclass(frozen=True)
class EvalCheck:
    name: str
    exit_code: int
    detail: str = ""


@dataclass(frozen=True)
class EvalReport:
    checks: tuple[EvalCheck, ...]

    @property
    def passed(self) -> bool:
        return all(c.exit_code == 0 for c in self.checks)


@dataclass(frozen=True)
class AutonomyState:
    mode: AutonomyMode = "review"
    kill_switch: bool = False
    min_confidence: float = 0.7
    min_interval_hours: int = 24
    allowed_targets: tuple[PatchKind, ...] = ("markdown", "config", "code")


@dataclass(frozen=True)
class RoundRecord:
    round_id: str
    status: RoundStatus
    detail: str = ""
    evidence_count: int = 0
    patch_hash: str | None = None
    eval_report: EvalReport | None = None
    applied_sha: str | None = None
    created_at: str = ""
```

Note: the spec's §3.1 names the eval field `eval`; it is implemented as
`eval_report` to avoid shadowing the builtin. This is the canonical name.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_round_types.py -q`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add autoresearch_core/types.py tests/test_round_types.py
git commit -m "feat(rounds): round data types — Finding, PatchEntry, RoundPatch, EvalReport, AutonomyState, RoundRecord"
```

---

### Task 2: `resolve_autonomy` in new `rounds.py`

**Files:**
- Create: `autoresearch_core/rounds.py`
- Test: `tests/test_rounds.py` (create)

- [ ] **Step 1: Write the failing test**

```python
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
    assert a.mode == "review"            # unknown mode -> review
    assert a.kill_switch is False        # only literal True engages it
    assert a.min_confidence == 0.7       # out-of-range -> default
    assert a.min_interval_hours == 24    # negative -> default
    assert a.allowed_targets == ("markdown",)  # unknown kinds dropped


def test_resolve_autonomy_non_mapping_harness():
    assert resolve_autonomy({"harness": "bogus"}).mode == "review"


def test_resolve_autonomy_no_gates_forces_auto_but_not_kill_switch():
    cfg = {"harness": {"kill_switch": True}}
    a = resolve_autonomy(cfg, no_gates=True)
    assert a.mode == "auto"
    assert a.kill_switch is True  # safety: no_gates never disables the kill switch


def test_resolve_autonomy_empty_targets_falls_back():
    a = resolve_autonomy({"harness": {"allowed_targets": []}})
    assert a.allowed_targets == ("markdown", "config", "code")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_rounds.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'autoresearch_core.rounds'`

- [ ] **Step 3: Create `autoresearch_core/rounds.py` with `resolve_autonomy`**

```python
"""Pure life-harness round policy. No I/O — hosts bind the ports.

Spec: docs/superpowers/specs/2026-06-06-life-harness-rounds-design.md
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence

from .types import (
    AutonomyState, EvalReport, Finding, GateCheck, PatchKind, RoundPatch, RoundStatus,
)

_ALL_TARGETS: tuple[PatchKind, ...] = ("markdown", "config", "code")


def resolve_autonomy(config: Mapping[str, Any], no_gates: bool = False) -> AutonomyState:
    """Read the host's `harness` config block (tolerant, like resolve_gates).

    `no_gates=True` forces auto mode but NEVER overrides the kill switch.
    """
    _h = config.get("harness")
    h: dict[str, object] = _h if isinstance(_h, dict) else {}

    raw_targets = h.get("allowed_targets")
    if isinstance(raw_targets, list):
        targets = tuple(t for t in raw_targets if t in _ALL_TARGETS)
    else:
        targets = ()
    if not targets:
        targets = _ALL_TARGETS

    conf = h.get("min_confidence")
    min_confidence = (
        float(conf)
        if isinstance(conf, (int, float)) and not isinstance(conf, bool) and 0.0 <= float(conf) <= 1.0
        else 0.7
    )

    hours = h.get("min_interval_hours")
    min_interval = hours if isinstance(hours, int) and not isinstance(hours, bool) and hours >= 0 else 24

    return AutonomyState(
        mode="auto" if (no_gates or h.get("autonomy") == "auto") else "review",
        kill_switch=h.get("kill_switch") is True,
        min_confidence=min_confidence,
        min_interval_hours=min_interval,
        allowed_targets=targets,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_rounds.py -q`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add autoresearch_core/rounds.py tests/test_rounds.py
git commit -m "feat(rounds): resolve_autonomy — tolerant harness-config resolution"
```

---

### Task 3: `select_evidence`

**Files:**
- Modify: `autoresearch_core/rounds.py`
- Modify: `tests/test_rounds.py`

- [ ] **Step 1: Add failing tests to `tests/test_rounds.py`**

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_rounds.py -q`
Expected: FAIL — `ImportError: cannot import name 'select_evidence'`

- [ ] **Step 3: Implement in `rounds.py`**

```python
_PRIORITY: dict[str, int] = {
    "takeaway": 0, "decision": 1, "insight": 2, "hypothesis": 3, "todo": 4, "question": 5,
}


def select_evidence(
    findings: Sequence[Finding], *, max_items: int = 25, min_items: int = 3
) -> tuple[Finding, ...]:
    """Deterministic evidence selection: kind priority, then recency.

    Returns () when there is too little evidence to justify a round.
    """
    pool = sorted(findings, key=lambda f: f.created_at, reverse=True)
    pool.sort(key=lambda f: _PRIORITY.get(f.kind, 99))  # stable: keeps recency order
    if len(pool) < min_items:
        return ()
    return tuple(pool[:max_items])
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_rounds.py -q`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add autoresearch_core/rounds.py tests/test_rounds.py
git commit -m "feat(rounds): select_evidence — priority + recency, min/max thresholds"
```

---

### Task 4: `patch_hash` + `should_skip_patch`

**Files:**
- Modify: `autoresearch_core/rounds.py`
- Modify: `tests/test_rounds.py`

- [ ] **Step 1: Add failing tests**

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_rounds.py -q`
Expected: FAIL — `ImportError: cannot import name 'patch_hash'`

- [ ] **Step 3: Implement in `rounds.py`**

```python
def patch_hash(patch: RoundPatch) -> str:
    """Stable, case/whitespace-insensitive dedupe hash (round_id/confidence excluded)."""
    parts = sorted(f"{e.op} {e.kind} {e.path}".lower() for e in patch.entries)
    normalized = re.sub(r"\s+", " ", " | ".join(parts + [patch.summary.strip().lower()]))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def should_skip_patch(hash_: str, seen_hashes: set[str]) -> bool:
    """Don't re-propose a patch already applied OR deterministically rejected."""
    return hash_ in seen_hashes
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_rounds.py -q`
Expected: PASS (14 tests)

- [ ] **Step 5: Commit**

```bash
git add autoresearch_core/rounds.py tests/test_rounds.py
git commit -m "feat(rounds): patch_hash dedupe + should_skip_patch"
```

---

### Task 5: `validate_round_patch`

**Files:**
- Modify: `autoresearch_core/rounds.py`
- Modify: `tests/test_rounds.py`

- [ ] **Step 1: Add failing tests**

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_rounds.py -q`
Expected: FAIL — `ImportError: cannot import name 'validate_round_patch'`

- [ ] **Step 3: Implement in `rounds.py`**

```python
def _bad_path(p: str) -> str | None:
    if not p:
        return "empty path"
    if p.startswith("/") or "\\" in p or re.match(r"^[A-Za-z]:", p):
        return "absolute or non-posix path"
    parts = p.split("/")
    if ".." in parts:
        return "path traversal"
    if parts[0] == ".git":
        return "may not touch .git"
    return None


def validate_round_patch(
    patch: RoundPatch,
    autonomy: AutonomyState,
    deny_paths: Iterable[str] = (),
    config_path: str = ".planning/config.json",
    current_harness: Mapping[str, Any] | None = None,
) -> list[str]:
    """Return validation errors ([] = valid). Pure — no filesystem access.

    `deny_paths` is the host's self-protection list (its driver file etc.);
    `current_harness` (the live `harness` config block) lets the kernel reject
    a config patch that rewrites the loop's own controls.
    """
    errors: list[str] = []
    if not patch.entries:
        errors.append("patch has no entries")
    if not (
        isinstance(patch.confidence, (int, float))
        and not isinstance(patch.confidence, bool)
        and 0.0 <= patch.confidence <= 1.0
    ):
        errors.append("confidence must be within [0, 1]")

    denied = {d.strip() for d in deny_paths}
    for i, e in enumerate(patch.entries):
        tag = f"entries[{i}] ({e.path or '?'})"
        reason = _bad_path(e.path)
        if reason:
            errors.append(f"{tag}: {reason}")
        if e.kind not in autonomy.allowed_targets:
            errors.append(f"{tag}: kind {e.kind!r} not in allowed_targets")
        if e.op == "delete":
            if e.content is not None:
                errors.append(f"{tag}: delete must not carry content")
        elif not e.content:
            errors.append(f"{tag}: {e.op} requires content")
        if not e.rationale.strip():
            errors.append(f"{tag}: rationale required")
        if e.path in denied:
            errors.append(f"{tag}: path is deny-listed")
        if e.path == config_path and e.op == "delete":
            errors.append(f"{tag}: may not delete the project config")
        if e.kind == "config" and e.op != "delete" and e.content:
            try:
                parsed = json.loads(e.content)
            except ValueError:
                errors.append(f"{tag}: config patch is not valid JSON")
                continue
            if (
                e.path == config_path
                and current_harness is not None
                and isinstance(parsed, dict)
                and parsed.get("harness") != dict(current_harness)
            ):
                errors.append(f"{tag}: round may not modify its own harness config block")
    return errors
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_rounds.py -q`
Expected: PASS (23 tests)

- [ ] **Step 5: Commit**

```bash
git add autoresearch_core/rounds.py tests/test_rounds.py
git commit -m "feat(rounds): validate_round_patch — path guards, target scope, self-protection"
```

---

### Task 6: `should_apply` + `decide_round`

**Files:**
- Modify: `autoresearch_core/rounds.py`
- Modify: `tests/test_rounds.py`

- [ ] **Step 1: Add failing tests**

```python
from autoresearch_core.rounds import decide_round, should_apply
from autoresearch_core.types import EvalCheck, EvalReport

GREEN = EvalReport(checks=(EvalCheck("lint", 0),))
RED = EvalReport(checks=(EvalCheck("jest", 1, "boom"),))


def test_should_apply_kill_switch_blocks_everything():
    a = AutonomyState(mode="auto", kill_switch=True)
    out = should_apply(GREEN, a, confidence=1.0)
    assert out.proceed is False and out.pending_gate == "kill_switch"


def test_should_apply_eval_failure_blocks():
    out = should_apply(RED, AutonomyState(mode="auto"), confidence=1.0)
    assert out.proceed is False and out.pending_gate == "eval_failed"


def test_should_apply_review_mode_waits():
    out = should_apply(GREEN, AutonomyState(mode="review"), confidence=1.0)
    assert out.proceed is False and out.pending_gate == "harness_review"


def test_should_apply_low_confidence_waits():
    out = should_apply(GREEN, AutonomyState(mode="auto", min_confidence=0.9), confidence=0.5)
    assert out.proceed is False and out.pending_gate == "low_confidence"


def test_should_apply_auto_green_confident_proceeds():
    out = should_apply(GREEN, AutonomyState(mode="auto", min_confidence=0.7), confidence=0.8)
    assert out.proceed is True and out.pending_gate is None


def test_decide_round_full_matrix():
    ok = _vpatch(_entry())
    auto = AutonomyState(mode="auto")

    assert decide_round(ok, AutonomyState(kill_switch=True), set(), GREEN)[0] == "skipped"
    assert decide_round(_vpatch(), auto, set(), GREEN)[0] == "rejected"            # invalid
    seen = {patch_hash(ok)}
    assert decide_round(ok, auto, seen, GREEN)[0] == "skipped"                     # duplicate
    assert decide_round(ok, auto, set(), RED)[0] == "rejected"                     # eval failed
    status, detail = decide_round(ok, AutonomyState(mode="review"), set(), GREEN)
    assert status == "evaluated" and "review" in detail                            # awaiting review
    assert decide_round(ok, auto, set(), GREEN)[0] == "applied"                    # auto green
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_rounds.py -q`
Expected: FAIL — `ImportError: cannot import name 'should_apply'`

- [ ] **Step 3: Implement in `rounds.py`**

```python
def should_apply(eval_report: EvalReport, autonomy: AutonomyState, confidence: float) -> GateCheck:
    """The apply gate. Order matters: kill switch > eval > mode > confidence."""
    if autonomy.kill_switch:
        return GateCheck(proceed=False, pending_gate="kill_switch")
    if not eval_report.passed:
        return GateCheck(proceed=False, pending_gate="eval_failed")
    if autonomy.mode == "review":
        return GateCheck(proceed=False, pending_gate="harness_review")
    if confidence < autonomy.min_confidence:
        return GateCheck(proceed=False, pending_gate="low_confidence")
    return GateCheck(proceed=True, pending_gate=None)


def decide_round(
    patch: RoundPatch,
    autonomy: AutonomyState,
    seen_hashes: set[str],
    eval_report: EvalReport,
    *,
    deny_paths: Iterable[str] = (),
    config_path: str = ".planning/config.json",
    current_harness: Mapping[str, Any] | None = None,
) -> tuple[RoundStatus, str]:
    """Facade: validate -> dedupe -> apply gate, as one (status, detail)."""
    if autonomy.kill_switch:
        return ("skipped", "kill switch is on")
    errors = validate_round_patch(patch, autonomy, deny_paths, config_path, current_harness)
    if errors:
        return ("rejected", "; ".join(errors))
    h = patch_hash(patch)
    if should_skip_patch(h, seen_hashes):
        return ("skipped", f"duplicate of a prior round (patch_hash {h})")
    gate = should_apply(eval_report, autonomy, patch.confidence)
    if gate.proceed:
        return ("applied", "eval passed; autonomy approved")
    if gate.pending_gate == "eval_failed":
        return ("rejected", "eval failed")
    return ("evaluated", f"awaiting review ({gate.pending_gate})")
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_rounds.py -q`
Expected: PASS (29 tests)

- [ ] **Step 5: Commit**

```bash
git add autoresearch_core/rounds.py tests/test_rounds.py
git commit -m "feat(rounds): should_apply gate + decide_round facade"
```

---

### Task 7: Round ports (`ports.py`)

**Files:**
- Modify: `autoresearch_core/ports.py` (append)
- Test: `tests/test_round_ports.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_round_ports.py
"""Round adapter protocols accept minimal structural fakes."""
from autoresearch_core.ports import (
    Applier, FindingsSource, PatchProposer, RoundEvaluator, RoundStore,
)
from autoresearch_core.types import EvalReport, Finding, PatchEntry, RoundPatch, RoundRecord


class _Findings:
    def findings(self, since):
        return [Finding(kind="takeaway", content="x", source="s")]


class _Proposer:
    def propose(self, evidence_md, workdir):
        e = PatchEntry(path="a.md", kind="markdown", op="create", content="x", rationale="r")
        return RoundPatch(round_id="r", entries=(e,), summary="s", confidence=0.9)


class _Evaluator:
    def evaluate(self, patch, workdir):
        return EvalReport(checks=())


class _Applier:
    def apply(self, patch, workdir):
        return "deadbeef"

    def revert(self, sha):
        return "feedface"


class _Store:
    def save_round(self, record):
        return None

    def load_patch_hashes(self):
        return set()

    def last_round_at(self):
        return None


def test_fakes_satisfy_protocols():
    assert isinstance(_Findings(), FindingsSource)
    assert isinstance(_Proposer(), PatchProposer)
    assert isinstance(_Evaluator(), RoundEvaluator)
    assert isinstance(_Applier(), Applier)
    assert isinstance(_Store(), RoundStore)
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_round_ports.py -q`
Expected: FAIL — `ImportError: cannot import name 'FindingsSource'`

- [ ] **Step 3: Append to `autoresearch_core/ports.py`**

The module already imports `Protocol`, `runtime_checkable`, `Sequence`, `Any`.
Add the round types import and the protocols:

```python
from .types import EvalReport, Finding, RoundPatch, RoundRecord


@runtime_checkable
class FindingsSource(Protocol):
    def findings(self, since: str | None) -> Sequence[Finding]: ...


@runtime_checkable
class PatchProposer(Protocol):
    def propose(self, evidence_md: str, workdir: str) -> RoundPatch: ...


@runtime_checkable
class RoundEvaluator(Protocol):
    def evaluate(self, patch: RoundPatch, workdir: str) -> EvalReport: ...


@runtime_checkable
class Applier(Protocol):
    def apply(self, patch: RoundPatch, workdir: str) -> str: ...
    def revert(self, sha: str) -> str: ...


@runtime_checkable
class RoundStore(Protocol):
    def save_round(self, record: RoundRecord) -> None: ...
    def load_patch_hashes(self) -> set[str]: ...
    def last_round_at(self) -> str | None: ...
```

(Adjust the existing `from .types import ExperimentResult` line to a single
combined import if the linter prefers; either form is fine.)

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_round_ports.py -q`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add autoresearch_core/ports.py tests/test_round_ports.py
git commit -m "feat(rounds): adapter protocols — FindingsSource/PatchProposer/RoundEvaluator/Applier/RoundStore"
```

---

### Task 8: Integration test — a full round with fake ports

**Files:**
- Test: `tests/test_round_integration.py` (create)

- [ ] **Step 1: Write the test (drives the whole surface together; should pass immediately)**

```python
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
```

- [ ] **Step 2: Run to verify pass**

Run: `python3 -m pytest tests/test_round_integration.py -q`
Expected: PASS (5 tests). If any fail, fix the kernel — not the test.

- [ ] **Step 3: Commit**

```bash
git add tests/test_round_integration.py
git commit -m "test(rounds): full-round integration with fake ports"
```

---

### Task 9: Public surface, version 0.2.0, CHANGELOG

**Files:**
- Modify: `autoresearch_core/__init__.py`
- Modify: `pyproject.toml` (version line)
- Modify: `CHANGELOG.md`
- Modify: `tests/test_parity.py` (extend the export check)

- [ ] **Step 1: Extend the failing export test in `tests/test_parity.py`**

In `test_public_surface_exports`, append to the name list:

```python
        "Finding", "PatchEntry", "RoundPatch", "EvalCheck", "EvalReport",
        "AutonomyState", "RoundRecord",
        "resolve_autonomy", "select_evidence", "validate_round_patch",
        "patch_hash", "should_skip_patch", "should_apply", "decide_round",
        "FindingsSource", "PatchProposer", "RoundEvaluator", "Applier", "RoundStore",
```

Run: `python3 -m pytest tests/test_parity.py -q` → Expected: FAIL (missing exports)

- [ ] **Step 2: Update `autoresearch_core/__init__.py`**

- Change `__version__ = "0.1.2"` → `__version__ = "0.2.0"`.
- Add imports + `__all__` entries:

```python
from .types import (
    AutonomyState, EvalCheck, EvalReport, Finding, PatchEntry, RoundPatch, RoundRecord,
)
from .rounds import (
    decide_round, patch_hash, resolve_autonomy, select_evidence, should_apply,
    should_skip_patch, validate_round_patch,
)
from .ports import Applier, FindingsSource, PatchProposer, RoundEvaluator, RoundStore
```

(merge into the existing import blocks; extend `__all__` with the same names).

- [ ] **Step 3: Bump `pyproject.toml`**

`version = "0.1.2"` → `version = "0.2.0"`.

- [ ] **Step 4: CHANGELOG entry**

Insert above the 0.1.2 section:

```markdown
## [0.2.0] - <release date>
### Added
- Life-harness rounds (pure): `Finding`/`PatchEntry`/`RoundPatch`/`EvalReport`/
  `AutonomyState`/`RoundRecord` types; `rounds.py` policy (`resolve_autonomy`,
  `select_evidence`, `validate_round_patch` with path guards + self-protection,
  `patch_hash` dedupe, `should_apply`, `decide_round`); adapter protocols
  `FindingsSource`/`PatchProposer`/`RoundEvaluator`/`Applier`/`RoundStore`.
  Design: docs/superpowers/specs/2026-06-06-life-harness-rounds-design.md.
```

- [ ] **Step 5: Run the full suite**

Run: `python3 -m pytest -q`
Expected: ALL PASS (existing 52 + ~43 new), no warnings about imports.

- [ ] **Step 6: Commit**

```bash
git add autoresearch_core/__init__.py pyproject.toml CHANGELOG.md tests/test_parity.py
git commit -m "feat: export rounds surface; bump 0.2.0"
```

---

### Task 10: Release 0.2.0 (operator-gated)

**Do not run without the operator's go-ahead.** Per `RELEASING.md`:

- [ ] **Step 1:** `git push origin main` and confirm CI green (`gh run list --branch main --limit 1`)
- [ ] **Step 2:** Set the real date in the CHANGELOG 0.2.0 heading; commit if changed
- [ ] **Step 3:** `git tag v0.2.0 && git push origin main v0.2.0` → publish workflow (Trusted Publishing)
- [ ] **Step 4:** `gh release create v0.2.0 --title v0.2.0` with the CHANGELOG section as notes
- [ ] **Step 5:** Verify in a clean venv: `pip install autoresearch-core==0.2.0`, import `decide_round`, run one call

---

## Self-review notes (done at plan time)

- Spec §3.1/§3.2/§3.3 → Tasks 1–7; §8 testing → every task + Task 8; §9 versioning → Tasks 9–10. §4/§5/§6/§7 (host) are the companion GRD plan.
- `eval` field renamed `eval_report` (builtin shadow) — noted in Task 1 and consistent throughout.
- All signatures consistent across tasks (checked: `validate_round_patch(patch, autonomy, deny_paths, config_path, current_harness)` matches Task 6's facade pass-through).
