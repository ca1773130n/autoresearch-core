# Tutorial — building an autoresearch loop on autoresearch-core

This tutorial builds, step by step, a minimal but complete
**hypothesis → experiment → measure → learn** loop on top of
`autoresearch-core`. Along the way it covers every public surface of the
library: the contract, the deterministic verdict, failure classes, decision
policy, dead-end promotion, gates, the infrastructure ports, custom verdict
strategies, and the life-harness round contracts (§11).

If you just want a working verdict in five minutes, read
[QUICKSTART.md](QUICKSTART.md) first — this tutorial assumes you've seen it.

```bash
pip install autoresearch-core   # Python 3.11+, zero dependencies
```

## The mental model

An autoresearch loop iterates:

```
HYPOTHESIZE → DESIGN → RUN → MEASURE → LEARN → DECIDE
     ▲                                            │
     └──────────────── revise ────────────────────┘
```

`autoresearch-core` owns the **decision points** (bold below) and *nothing
else* — no I/O, no LLM calls, no persistence:

| Loop phase | Library surface |
|---|---|
| HYPOTHESIZE | **`should_skip`** (don't re-propose known dead-ends), `Hypothesis` |
| DESIGN | **`MetricSpec`**, **`validate_metric_spec`** (the falsifiability contract) |
| RUN | **`parse_metrics_line`**, **`classify_run_failure`**, `ExperimentResult` |
| MEASURE | **`measure`** / `DeterministicVerdict` → `VerdictRecord` |
| LEARN | **`should_promote_dead_end`**, **`build_dead_end_record`**, `KnowhowRecord` |
| DECIDE | **`decide`** (`decide_branch` + `should_terminate`), **`detect_plateau`** |
| (anywhere) | **`resolve_gates`** / **`check_gate`** (approval pauses) |

Everything with side effects — spawning an LLM, retrieving documents, running
code, saving records — goes through *your* implementations of the `Protocol`s
in `ports.py` (§8).

---

## 1. The contract: `MetricSpec`

A hypothesis without a falsifiable success condition isn't testable. The
contract forces one **before** any experiment runs:

```python
from autoresearch_core import MetricSpec, validate_metric_spec

spec = MetricSpec(metric_key="recall_at_10", comparator=">=", target=0.8)
validate_metric_spec(spec)   # raises ValueError on a spec that can't drive a verdict
```

`validate_metric_spec` rejects: empty/non-string `metric_key`, a comparator
outside `>=  <=  >  <  ==`, a non-numeric or boolean target, and non-finite
targets (`inf`, `nan`). Fail here, at design time — not after burning an
experiment run.

All library dataclasses are frozen — a spec, result, or verdict can't be
quietly mutated after the fact.

## 2. Running an experiment: the `__RESULT__` line

The library never runs anything. Your experiment is any process that prints
one machine-readable line to stdout:

```
__RESULT__ {"recall_at_10": 0.83, "latency_ms": 41}
```

`parse_metrics_line` extracts the **first** occurrence and keeps only finite
numbers (booleans and strings are dropped; `1e999`/`NaN` reject the whole
line, matching JS `JSON.parse` semantics):

```python
from autoresearch_core import parse_metrics_line

parse_metrics_line('setup...\n__RESULT__ {"recall_at_10": 0.83}\ndone')
# {'recall_at_10': 0.83}
```

## 3. Classifying failures: H2 / H3 / H4

When a run fails, *how* it failed determines what to revise. The classifier
is a pure function of stderr + a timeout flag:

```python
from autoresearch_core import classify_run_failure

classify_run_failure("ModuleNotFoundError: No module named 'faiss'", False)  # 'H2'
classify_run_failure("data/corpus.jsonl: No such file or directory", False)  # 'H3'
classify_run_failure("", True)                                               # 'H4'
classify_run_failure("", False)                                              # 'none'
```

| Class | Meaning | Typical fix |
|---|---|---|
| `H2` | Missing dependency (`command not found`, `ModuleNotFoundError`, `ImportError`) | install / environment |
| `H3` | Missing file or permission (`No such file or directory`, `ENOENT`, `permission denied`) | paths / setup |
| `H4` | Timeout or any other runtime failure | the experiment itself |
| `none` | Empty stderr — no failure signal | — |

Bundle everything into a frozen `ExperimentResult`:

```python
from autoresearch_core import ExperimentResult

result = ExperimentResult(
    metrics=parse_metrics_line(proc.stdout),
    exit_code=proc.returncode,
    failure_class=classify_run_failure(proc.stderr, timed_out=False),
    runner="subprocess",          # default; document your runner
    duration_ms=1834,
    stdout_excerpt=proc.stdout[-500:],
)
```

## 4. Measuring: the deterministic verdict

```python
from autoresearch_core import measure

record = measure(spec, result)    # VerdictRecord
record.verdict          # 'supported' | 'refuted' | 'inconclusive'
record.strategy         # 'deterministic'
record.evidence_level   # 'deterministic'
record.detail           # 'recall_at_10=0.83 >= 0.8 → pass'
```

The decision table — and the key asymmetry:

- `exit_code != 0` → **inconclusive** (`"experiment run failed (H2)"`). A
  broken run is *not* evidence against the hypothesis.
- metric missing from `result.metrics` → **inconclusive** (`'metric
  "recall_at_10" not reported'`). A contract violation isn't a refutation
  either.
- otherwise → `compare(value, comparator, target)` →
  **supported** or **refuted**.

`detail` is human-readable provenance; only the verdict *outcome* is the
parity-guaranteed contract.

## 5. Deciding: branch, terminate, plateau

```python
from autoresearch_core import decide, decide_branch, should_terminate, detect_plateau

branch, done, status = decide(iteration=2, max_iterations=5, verdict=record.verdict)
```

- `decide_branch(verdict)` → `'finalize'` if supported, else `'revise'`.
- `should_terminate(iteration, max_iterations, last_verdict)` →
  `(True, 'supported')` on success, `(True, 'exhausted')` when the iteration
  budget is hit, `(False, 'active')` otherwise.
- `detect_plateau(verdicts, window=3)` → `True` when the last `window`
  verdicts are all non-supported — your signal to widen the approach space
  (re-survey, change hypothesis family) instead of grinding variations.

## 6. Learning: dead-ends and knowhow

This is the library's central rule — **promotion authority**:

```python
from autoresearch_core import should_promote_dead_end

should_promote_dead_end(record)
# True  ⟺  record.verdict == 'refuted' AND record.evidence_level == 'deterministic'
```

Only a deterministic refutation may write to the dead-ends registry. An LLM
judge saying "this looks wrong" or a non-zero exit code is advisory — it never
auto-promotes.

When promotion is allowed, build the (shape-only) record:

```python
from autoresearch_core import Hypothesis, build_dead_end_record, approach_hash, should_skip

hyp = Hypothesis(
    id="hyp-3", iteration=3,
    statement="BM25 alone reaches recall@10 ≥ 0.8 on the eval set",
    predicted_outcome="recall_at_10 >= 0.8",
)

dead_end = build_dead_end_record(hyp, record)   # raises ValueError unless
                                                # should_promote_dead_end(record)
dead_end.approach_hash   # 16-hex stable hash of the normalized statement
dead_end.reason          # record.detail — the measured refutation
```

`approach_hash` is case- and whitespace-insensitive, which makes dedupe work
at HYPOTHESIZE time:

```python
hashes = {dead_end.approach_hash}                          # your Store persists this
should_skip("bm25  alone reaches recall@10 ≥ 0.8 on the eval set", hashes)  # True
```

Positive learnings use the `KnowhowRecord(statement, content, iteration)`
shape, and richer typed takeaways use
`Takeaway(kind, content, confidence, evidence, failure_class, iteration)` with
`kind` in `success_pattern | failure_root_cause | constraint | domain_fact |
tool_pattern`. The library defines the shapes; persistence is yours (§8).

## 7. Gates: approval pauses

Two named gates control the loop's risky transitions: `execute` (run
experiments) and `kg_write` (persist findings to the knowledge graph). Both
default **on** — meaning they *require approval*:

```python
from autoresearch_core import resolve_gates, check_gate

config = {"research_gates": {"experiment_execution": True, "kg_write": False}}
gates = resolve_gates(config, no_gates=False)
# GateState(execute=True, kg_write=False)

check_gate(gates, "execute", approved=False)   # GateCheck(proceed=False, pending_gate='execute')
check_gate(gates, "execute", approved=True)    # GateCheck(proceed=True,  pending_gate=None)
check_gate(gates, "kg_write", approved=False)  # GateCheck(proceed=True,  pending_gate=None) — gate off
```

Notes that bite in practice:

- The config sub-key for the `execute` gate is **`experiment_execution`**, not
  `execute`. Any value other than literal `False` leaves a gate on.
- `no_gates=True` disables both (autonomous mode).
- An unknown gate name raises `ValueError` — fail fast, don't silently proceed.
- When `proceed` is `False`, *your* loop pauses the thread and records
  `pending_gate`; the library only renders the decision.

## 8. Binding your infrastructure: the ports

`ports.py` declares five `runtime_checkable` `Protocol`s. The library ships
**no implementations** — each project binds its own:

| Port | Shape | Typical binding |
|---|---|---|
| `Spawn` | `async __call__(prompt) -> str` | your LLM/agent backend |
| `Retriever` | `async retrieve(query, k=8) -> Sequence[dict]` | hybrid search, vector DB |
| `KnowledgeGraph` | `async prior_findings(query)`, `async write_finding(finding)` | your KG / notes store |
| `ExperimentRunner` | `run(plan, workdir) -> ExperimentResult` | subprocess, Docker, cluster |
| `Store` | `save_verdict`, `load_dead_end_hashes`, `save_dead_end` | files, SQLite, anything |

A minimal local runner and store:

```python
import json, subprocess, sys
from pathlib import Path
from typing import Any

from autoresearch_core import ExperimentResult, classify_run_failure, parse_metrics_line


class SubprocessRunner:
    """Binds ExperimentRunner: plan = {'code': '<python source>'}."""

    def run(self, plan: dict[str, Any], workdir: str) -> ExperimentResult:
        try:
            proc = subprocess.run(
                [sys.executable, "-c", plan["code"]],
                capture_output=True, text=True, timeout=300, cwd=workdir,
            )
            stdout, stderr, code, timed_out = proc.stdout, proc.stderr, proc.returncode, False
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, code, timed_out = (exc.stdout or ""), (exc.stderr or ""), 124, True
        return ExperimentResult(
            metrics=parse_metrics_line(stdout),
            exit_code=code,
            failure_class=classify_run_failure(stderr, timed_out),
            stdout_excerpt=stdout[-500:],
        )


class JsonStore:
    """Binds Store: one JSON file per scope."""

    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def save_verdict(self, thread_id: str, record: Any) -> None:
        path = self.root / f"{thread_id}.verdicts.jsonl"
        with path.open("a") as f:
            f.write(json.dumps(record.__dict__) + "\n")

    def load_dead_end_hashes(self, scope: str) -> set[str]:
        path = self.root / f"{scope}.dead-ends.jsonl"
        if not path.exists():
            return set()
        return {json.loads(line)["approach_hash"] for line in path.open()}

    def save_dead_end(self, scope: str, record: Any) -> None:
        path = self.root / f"{scope}.dead-ends.jsonl"
        with path.open("a") as f:
            f.write(json.dumps(record.__dict__) + "\n")
```

Because the protocols are `runtime_checkable`, you can sanity-check bindings:

```python
from autoresearch_core import ExperimentRunner, Store
assert isinstance(SubprocessRunner(), ExperimentRunner)
assert isinstance(JsonStore("/tmp/demo"), Store)
```

## 9. Putting it together: a complete minimal loop

Save as `loop.py` and run with `python loop.py`. Three canned "approaches"
stand in for hypothesis generation; everything else is the real discipline:

```python
"""A minimal but complete autoresearch loop on autoresearch-core."""
import subprocess
import sys

from autoresearch_core import (
    ExperimentResult, Hypothesis, MetricSpec,
    build_dead_end_record, classify_run_failure, decide, detect_plateau,
    measure, parse_metrics_line, should_promote_dead_end, should_skip,
    validate_metric_spec,
)

SPEC = MetricSpec(metric_key="accuracy", comparator=">=", target=0.9)

APPROACHES = [  # (hypothesis statement, stand-in measured accuracy)
    ("baseline threshold classifier reaches 0.9", 0.72),
    ("adding bigram features reaches 0.9", 0.85),
    ("tuned regularization reaches 0.9", 0.93),
]


def run_experiment(accuracy: float) -> ExperimentResult:
    code = f"import json; print('__RESULT__ ' + json.dumps({{'accuracy': {accuracy}}}))"
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    return ExperimentResult(
        metrics=parse_metrics_line(proc.stdout),
        exit_code=proc.returncode,
        failure_class=classify_run_failure(proc.stderr, timed_out=False),
    )


def main() -> None:
    validate_metric_spec(SPEC)                       # DESIGN: contract first
    dead_ends: set[str] = set()                      # real loop: store.load_dead_end_hashes(scope)
    history = []

    for iteration, (statement, accuracy) in enumerate(APPROACHES, start=1):
        if should_skip(statement, dead_ends):        # HYPOTHESIZE: dedupe
            print(f"[{iteration}] skip (known dead end): {statement}")
            continue
        hyp = Hypothesis(id=f"hyp-{iteration}", iteration=iteration, statement=statement,
                         predicted_outcome=f"{SPEC.metric_key} {SPEC.comparator} {SPEC.target}")

        result = run_experiment(accuracy)            # RUN
        record = measure(SPEC, result)               # MEASURE: computed, not judged
        history.append(record.verdict)
        print(f"[{iteration}] {record.verdict:12s} {record.detail}")

        if should_promote_dead_end(record):          # LEARN: deterministic refutations only
            dead_ends.add(build_dead_end_record(hyp, record).approach_hash)

        branch, done, status = decide(iteration, len(APPROACHES), record.verdict)  # DECIDE
        if done:
            print(f"→ {status}")
            return
        if detect_plateau(history):
            print("→ plateau: widen the approach space (re-survey) before iterating further")

    print("→ exhausted")


if __name__ == "__main__":
    main()
```

Output:

```
[1] refuted      accuracy=0.72 >= 0.9 → fail
[2] refuted      accuracy=0.85 >= 0.9 → fail
[3] supported    accuracy=0.93 >= 0.9 → pass
→ supported
```

Iterations 1–2 are deterministic refutations, so both statements enter the
dead-end set and would be skipped if re-proposed. Iteration 3 supports the
hypothesis → `decide` returns `('finalize', True, 'supported')`.

In a real loop, an LLM (bound through `Spawn`) generates the statements and
experiment code, `Retriever`/`KnowledgeGraph` ground them in prior findings,
and `Store` persists verdicts and dead-ends across sessions — the decision
points stay exactly as above.

## 10. Custom verdict strategies — and their limits

`VerdictStrategy` is a protocol: anything with a `name` and an
`evaluate(spec, result) -> VerdictRecord` qualifies.

```python
from autoresearch_core import VerdictRecord, measure

class ExitCodeVerdict:
    """Weaker evidence: did the run merely succeed?"""
    name = "exit_code"

    def evaluate(self, spec, result):
        ok = result.exit_code == 0
        return VerdictRecord(
            verdict="supported" if ok else "refuted",
            strategy=self.name,
            evidence_level="exit_code",
            detail=f"exit_code={result.exit_code}",
        )

record = measure(spec, result, strategy=ExitCodeVerdict())
```

An LLM-judge strategy works the same way (`evidence_level="llm"`). But the
authority rule holds regardless of strategy:

```python
from autoresearch_core import should_promote_dead_end
should_promote_dead_end(record)   # False — evidence_level is 'exit_code', not 'deterministic'
```

Non-deterministic strategies can *inform* (rank candidates, flag suspicious
runs); they can never *conclude*. Every `VerdictRecord` carries its `strategy`
and `evidence_level`, so an audit of the decision trail always shows which
authority produced which conclusion.

## 11. Life-harness rounds: the loop pointed at itself (0.4.3)

Everything above measures *experiments*. The `rounds` module applies the same
discipline to the harness's own evolution: session evidence in, one
eval-gated, reversible patch to the harness's primitives out.

The shape mirrors the research loop deliberately:

| Research loop | Life-harness round |
|---|---|
| `Hypothesis` | `RoundPatch` (one focused change + rationale + confidence) |
| experiment run | host applies the patch in a scratch worktree |
| `ExperimentResult` | `EvalReport` (lint/tests/structural checks as `EvalCheck`s) |
| deterministic verdict | `should_apply` gate (kill switch > eval > review-mode > confidence) |
| dead-end promotion | `patch_hash` dedupe — a deterministically rejected patch is never re-proposed |
| gates | `AutonomyState` (`resolve_autonomy(config)`: review-mode default, opt-in auto, kill switch) |

```python
from autoresearch_core import (
    AutonomyState, EvalCheck, EvalReport, Finding, PatchEntry, RoundPatch,
    decide_round, patch_hash, resolve_autonomy, select_evidence,
)

# 1. Evidence (your host queries it — e.g. Tesserae session findings)
evidence = select_evidence([
    Finding(kind="takeaway", content="executor forgets to commit", source="s1"),
    Finding(kind="decision", content="always run lint first", source="s2"),
    Finding(kind="insight", content="plans drift after wave 3", source="s3"),
], max_items=25, min_items=3)

# 2. A proposal agent turns evidence into ONE patch (host-bound via PatchProposer)
patch = RoundPatch(round_id="r1", entries=(
    PatchEntry(path="commands/execute-phase.md", kind="markdown", op="modify",
               content="...", rationale=evidence[0].content),
), summary="commit reminder in executor prompt", confidence=0.9)

# 3. The kernel decides; the host acts
autonomy = resolve_autonomy({"harness": {"autonomy": "review"}})
status, detail = decide_round(patch, autonomy, seen_hashes=set(),
                              eval_report=EvalReport(checks=(EvalCheck("lint", 0),)))
# ('evaluated', 'awaiting review (harness_review)')
```

Safety is kernel-enforced: paths must be repo-relative (no `..`, never
`.git/`), patch kinds must be within `allowed_targets`, and a deny-list plus a
`current_harness` check stop a round from patching its own driver or autonomy
config. Hosts bind five protocols (`FindingsSource`, `PatchProposer`,
`RoundEvaluator`, `Applier`, `RoundStore`) and anchor every applied round to a
git commit, so revert is `git revert`. The reference host is GRD's
`gd harness round`; the full design is in
[docs/superpowers/specs/2026-06-06-life-harness-rounds-design.md](docs/superpowers/specs/2026-06-06-life-harness-rounds-design.md).

## 12. Parity with GRD

The behaviour here is parity-tested (`tests/test_parity.py`) against the
TypeScript implementation in [GRD](https://github.com/ca1773130n/GetResearchDone)
(`verdict.ts`, `gates.ts`, `runner.ts`). Guarantees and deliberate deviations:

- **Guaranteed:** verdict outcomes, metric parsing (including JSON-constant
  rejection), failure classes, gate resolution.
- **Not guaranteed:** `VerdictRecord.detail` strings are human-readable, not
  byte-for-byte identical.
- **Deliberately stricter:** `check_gate` raises `ValueError` on unknown gate
  names (GRD silently proceeds); `build_dead_end_record` refuses
  non-deterministic refutations.

## Where to go next

- [README.md](README.md) — API map, design rationale, development setup.
- [CHANGELOG.md](CHANGELOG.md) — release history.
- The source itself is ~400 lines and dependency-free — `autoresearch_core/`
  reads in one sitting.
