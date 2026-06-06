# Life-Harness Rounds — Design

**Date:** 2026-06-06
**Status:** Approved by operator (brainstorm 2026-06-06); awaiting implementation plan.
**Repos:** `autoresearch-core` (kernel — this spec's home) + `GetResearchDone` (first host).

## 1. Context & goal

GRD's `gd evolve` is obsolete: it discovered improvement work by statically
scanning the codebase, and its discovery dimensions saturated (5+ consecutive
iterations of 100% false positives). The replacement is the **life-harness**
approach (designed in Agented, 2026-05-29): improve the harness from
**runtime evidence** — what actually went wrong or was learned in real
sessions — applied as eval-gated, reversible patches to the harness's own
primitives.

Two constraints set by the operator:

1. **Do not re-implement capture/synthesis.** Tesserae already captures
   sessions (`sessions-import`) and synthesizes typed Session findings
   (insight / decision / question / todo / hypothesis / takeaway). The
   life-harness consumes those findings; it never parses transcripts itself.
2. **The round logic lives in `autoresearch-core`** as pure decision
   contracts + ports (the package's existing philosophy: no I/O, zero
   dependencies). Hosts bind the I/O. GRD is the first host; Agented can
   adopt the same module later (its Phase-E convergence).

Patch scope (operator choice): **markdown + config + lib code** — the widest
tier, protected by the eval gate.

## 2. Architecture

```
┌─ Tesserae (exists, untouched) ──────────────────────────────┐
│ sessions-import → compile → Session findings                │
└──────────────┬──────────────────────────────────────────────┘
               │ findings (JSON)
┌─ autoresearch-core 0.2.0 — NEW rounds module (pure) ────────┐
│ evidence selection · patch validation · dedupe (patch_hash) │
│ eval-gate policy · autonomy resolution · round records      │
│ Ports: FindingsSource · PatchProposer · RoundEvaluator ·    │
│        Applier · RoundStore                                 │
└──────────────┬──────────────────────────────────────────────┘
               │ imported by
┌─ GRD: bin/harness_driver.py (~150 lines Python) ────────────┐
│ Binds the 5 ports: tesserae CLI · spawned codex/claude ·    │
│ npm test/lint/tsc · git branch+commit · .planning/harness/  │
└──────────────┬──────────────────────────────────────────────┘
               │ subprocess (like gd → claude/codex/docker)
┌─ gd CLI ────────────────────────────────────────────────────┐
│ gd harness round [--auto|--dry-run] · status · revert <id>  │
│ gd resolves account rotation env and passes it to driver    │
└─────────────────────────────────────────────────────────────┘
```

Boundary rule: the kernel **decides**, hosts **act**. The kernel never
touches Tesserae, git, the filesystem (beyond what hosts hand it as values),
or subprocesses.

## 3. Kernel module (`autoresearch_core`)

New files, following the existing one-file-per-concern layout:

### 3.1 Types (extend `types.py` — it is the package's pure-data home; frozen dataclasses)

- `Finding(kind, content, source, created_at)` —
  `kind: Literal['insight','decision','question','todo','hypothesis','takeaway']`;
  `source` is the Tesserae session/node reference; `created_at` ISO string.
- `PatchKind = Literal['markdown','config','code']`
- `PatchEntry(path, kind: PatchKind, op: Literal['modify','create','delete'], content: str | None, rationale: str, evidence_refs: tuple[str, ...])`
  — `content` is the full post-image for modify/create, `None` for delete.
- `RoundPatch(round_id, entries: tuple[PatchEntry, ...], summary: str, confidence: float)`
- `EvalCheck(name, exit_code, detail)` / `EvalReport(checks: tuple[EvalCheck, ...])`
  with derived `passed` (all exit codes 0).
- `AutonomyState(mode: Literal['review','auto'], kill_switch: bool, min_confidence: float, min_interval_hours: int, allowed_targets: tuple[PatchKind, ...])`
- `RoundStatus = Literal['skipped','gathered','proposed','validated','evaluated','applied','rejected','reverted']`
- `RoundRecord(round_id, status, evidence_count, patch_hash, eval, applied_sha, detail, created_at)`
  (optional fields `None` until reached).

### 3.2 `rounds.py` (pure logic)

- `resolve_autonomy(config, no_gates: bool) -> AutonomyState` — reads the
  host's `harness` config mapping (same tolerant pattern as `resolve_gates`):
  defaults `mode='review'`, `kill_switch=False`, `min_confidence=0.7`,
  `min_interval_hours=24`, `allowed_targets=('markdown','config','code')`.
- `select_evidence(findings, *, max_items, min_items) -> tuple[Finding, ...]`
  — deterministic priority: takeaway > decision > insight > hypothesis >
  todo > question; recency as tie-break; returns `()` when fewer than
  `min_items` (round becomes `skipped`).
- `validate_round_patch(patch, autonomy) -> list[str]` — returns error
  strings (empty = valid): entries non-empty; every `kind` within
  `allowed_targets`; every `path` repo-relative (rejects absolute paths,
  `..` segments, anything under `.git/`); **self-protection deny-list**:
  the host driver file and the `harness` config keys cannot be patched
  (host passes its deny-list paths in; kernel always denies `.git/`).
  `content` required unless `op='delete'`; `confidence` in [0, 1].
- `patch_hash(patch) -> str` — stable 16-hex hash over normalized
  `(path, op, kind)` entries + summary (whitespace/case-insensitive, same
  normalization approach as `approach_hash`).
- `should_skip_patch(hash, seen_hashes) -> bool` — dedupe against
  previously applied **and rejected** rounds (a deterministic rejection is
  a dead-end; don't re-propose it).
- `should_apply(eval_report, autonomy, confidence) -> GateCheck` —
  kill switch → never; eval failed → never; `mode='review'` → proceed=False
  with `pending_gate='harness_review'`; `mode='auto'` and
  `confidence >= min_confidence` → proceed=True.
- `decide_round(...)` — facade composing validate → dedupe → eval-gate into
  a `(RoundStatus, detail)` for hosts that want one call.

### 3.3 Ports (extend `ports.py`)

```python
class FindingsSource(Protocol):
    def findings(self, since: str | None) -> Sequence[Finding]: ...

class PatchProposer(Protocol):
    def propose(self, evidence_md: str, workdir: str) -> RoundPatch: ...

class RoundEvaluator(Protocol):
    def evaluate(self, patch: RoundPatch, workdir: str) -> EvalReport: ...

class Applier(Protocol):
    def apply(self, patch: RoundPatch, workdir: str) -> str: ...   # returns commit sha
    def revert(self, sha: str) -> str: ...

class RoundStore(Protocol):
    def save_round(self, record: RoundRecord) -> None: ...
    def load_patch_hashes(self) -> set[str]: ...
    def last_round_at(self) -> str | None: ...
```

## 4. GRD host (first binding)

### 4.1 `bin/harness_driver.py` (~150 lines, stdlib + autoresearch-core only)

Binds the five ports:

| Port | Binding |
|---|---|
| `FindingsSource` | `tesserae` CLI, JSON output, filtered to finding kinds. Exact subcommand confirmed at implementation against the installed tesserae version; MCP endpoint is the fallback. Fails with `run: tesserae refresh` guidance when the project graph is missing/stale. |
| `PatchProposer` | Spawns the backend CLI (`codex exec` / `claude -p`) in a scratch **git worktree** seeded with `evidence.md`; the agent must write `patch.json` (schema = `RoundPatch`). Backend binary + account env (`CLAUDE_CONFIG_DIR`/`CODEX_HOME`) arrive from gd via env vars — rotation knowledge stays in gd. |
| `RoundEvaluator` | Applies entries in the worktree, then tiers: markdown frontmatter/structure check for `commands/*.md`, `agents/*.md`, skills; JSON-parse + key-whitelist check for `.planning/config.json`; `npm run lint` + `npm run build:check` + targeted jest for touched `lib/**` files (full suite behind `--full-eval`). |
| `Applier` | Squashes the worktree diff into one commit on branch `harness/round-<id>`; auto mode merges it; revert = `git revert <sha>`. |
| `RoundStore` | `.planning/harness/rounds/<id>/{evidence.md,patch.json,eval.json,RECORD.json}` + `.planning/harness/hashes.jsonl`. |

### 4.2 `gd` CLI surface (TypeScript, thin)

- `gd harness round [--auto] [--dry-run] [--full-eval]` — resolves backend +
  account from `superpowers.*` config, execs the driver, prints the round
  summary (review mode: branch name + how to merge).
- `gd harness status` — renders `.planning/harness/` records.
- `gd harness revert <round-id>` — looks up the sha, drives `git revert`.
- Driver-missing/python-missing → actionable error
  (`pip install autoresearch-core>=0.2`).

### 4.3 Config (`.planning/config.json`)

```json
"harness": {
  "autonomy": "review",
  "kill_switch": false,
  "min_confidence": 0.7,
  "min_interval_hours": 24,
  "allowed_targets": ["markdown", "config", "code"],
  "backend": "codex",
  "min_evidence": 3,
  "max_evidence": 25
}
```

## 5. Round lifecycle

1. **Gather** — kill switch / interval check → driver queries Tesserae since
   `last_round_at()` → `select_evidence()`; below `min_evidence` → `skipped`.
2. **Propose** — scratch worktree + `evidence.md` → spawned agent →
   `patch.json` → parse to `RoundPatch`. Malformed output → `rejected`
   (parse error recorded), worktree removed.
3. **Validate (pure)** — `validate_round_patch` + `should_skip_patch`.
   Duplicate → `skipped` with the prior round referenced.
4. **Evaluate** — tiered checks in the worktree → `EvalReport`. Any failure →
   `rejected`, failing check excerpt recorded, **hash enters the dedupe set**
   (deterministic rejection = dead-end; mirrors the research loop's
   promotion-authority rule).
5. **Decide (pure)** — `should_apply`: review mode leaves the branch + prints
   the summary; auto mode merges only when eval passed and
   `confidence ≥ min_confidence`.
6. **Persist** — `RoundRecord` saved; the **git commit is the forge, journal,
   and revert anchor** (no separate materialization/journal machinery — GRD
   primitives are files in a git repo).

## 6. Safety

- Kill switch short-circuits before any I/O.
- Kernel path guards: no absolute paths, no `..`, never `.git/**`.
- Self-protection deny-list: `bin/harness_driver.py` and the `harness` config
  block cannot be patched by a round — changing the loop's own controls stays
  a human commit.
- One commit per round; merge atomic; `gd harness revert` is `git revert`.
- `min_interval_hours` prevents cron/loop spin.
- Review mode is the default; autonomy is opt-in per project config.

## 7. Evolve deprecation

- `gd evolve` prints a deprecation notice pointing at `gd harness round` and
  exits without running discovery; help text moves it under Deprecated.
- `lib/evolve/` stays in-tree for now (`gd singularity` still reads its
  history); deletion is a later cleanup, out of scope.
- `DEPRECATIONS.md` gains the entry.

## 8. Testing

- **Kernel (this repo):** pytest, offline, deterministic — `select_evidence`
  ordering/thresholds; `validate_round_patch` traversal + deny-list +
  target-scope cases; `patch_hash` normalization + dedupe; `should_apply`
  matrix (mode × kill switch × eval × confidence); `resolve_autonomy`
  tolerant-config cases. Plus one integration test running a full round with
  all-fake ports.
- **GRD:** jest tests for the CLI plumbing with an injected fake driver
  (spawn-injection convention); the driver itself stays thin enough that its
  logic is the kernel's.
- **No parity vectors** for rounds: there is deliberately no TS twin of this
  logic — the kernel is the single implementation.

## 9. Versioning & rollout

- Ships as **autoresearch-core 0.2.0** (new API surface = minor, per
  RELEASING.md). HypePaper (`==0.1.1`) and Agented (`>=0.1.1,<0.2`) are
  unaffected until they opt in.
- GRD adds the driver + CLI in the same effort and becomes the first host.

## 10. Out of scope (explicitly deferred)

- Replay-based eval (re-running past trajectories against the patched
  primitives — Agented Phase C analogue).
- Cross-project primitive propagation (Phase E analogue).
- Agented's adoption of this module in place of `harness_evolver`'s inline
  logic — desirable convergence, separate effort in that repo.
- Removal of `lib/evolve/` from GRD.
