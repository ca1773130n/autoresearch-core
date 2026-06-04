# Quickstart

Zero to a working deterministic verdict in five minutes.

## 1. Install

```bash
pip install autoresearch-core
```

Python 3.11+. No runtime dependencies.

## 2. The three-step core

Everything in `autoresearch-core` reduces to three steps:

1. **Contract** — declare, *before* running anything, what would make your
   hypothesis true: a `MetricSpec` (metric key, comparator, target).
2. **Measure** — run your experiment; it prints one machine-readable line
   (`__RESULT__ {"accuracy": 0.93}`); the library computes the verdict.
3. **Decide** — the verdict drives the loop: `finalize` on success, `revise`
   otherwise, terminate on success or budget exhaustion.

No LLM judges anything on this path.

## 3. A complete runnable script

Save as `quickstart.py` and run with `python quickstart.py`:

```python
import subprocess
import sys

from autoresearch_core import (
    ExperimentResult,
    MetricSpec,
    classify_run_failure,
    decide,
    measure,
    parse_metrics_line,
    should_promote_dead_end,
    validate_metric_spec,
)

# ── 1. Contract: what would make the hypothesis TRUE? ──────────────────────
spec = MetricSpec(metric_key="accuracy", comparator=">=", target=0.9)
validate_metric_spec(spec)  # raises ValueError if the spec can't drive a verdict

# ── 2. Run the experiment (any subprocess that prints the contract line) ───
# Stand-in experiment: your real one trains a model, runs a benchmark, etc.
experiment = "import json; print('__RESULT__ ' + json.dumps({'accuracy': 0.93}))"
proc = subprocess.run(
    [sys.executable, "-c", experiment],
    capture_output=True, text=True, timeout=60,
)

result = ExperimentResult(
    metrics=parse_metrics_line(proc.stdout),          # {"accuracy": 0.93}
    exit_code=proc.returncode,
    failure_class=classify_run_failure(proc.stderr, timed_out=False),
)

# ── 3. Measure: the verdict is computed, not judged ────────────────────────
record = measure(spec, result)
print(record.verdict)   # "supported"
print(record.detail)    # "accuracy=0.93 >= 0.9 → pass"

# ── 4. Decide: branch + termination ────────────────────────────────────────
branch, done, status = decide(iteration=1, max_iterations=5, verdict=record.verdict)
print(branch, done, status)            # finalize True supported

# A deterministic refutation (and only that) may auto-promote a dead-end:
print(should_promote_dead_end(record))  # False — this verdict is "supported"
```

Expected output:

```
supported
accuracy=0.93 >= 0.9 → pass
finalize True supported
False
```

## 4. What the verdict can be

| Verdict | When |
|---|---|
| `supported` | Experiment succeeded (`exit_code == 0`), metric present, comparison passes |
| `refuted` | Experiment succeeded, metric present, comparison fails |
| `inconclusive` | Experiment failed (`exit_code != 0`) **or** the metric was never reported |

A failed run is *never* a refutation — `inconclusive` keeps broken
infrastructure from being recorded as scientific evidence.

## 5. The `__RESULT__` contract, precisely

`parse_metrics_line` extracts the **first** `__RESULT__ {json}` occurrence from
stdout and keeps only finite numbers:

```python
parse_metrics_line('__RESULT__ {"acc": 0.9, "n": 100}')   # {"acc": 0.9, "n": 100.0}
parse_metrics_line('__RESULT__ {"ok": true, "note": "x"}') # {} — bools/strings dropped
parse_metrics_line('__RESULT__ {"acc": 1e999}')            # {} — non-finite rejected
parse_metrics_line('no contract line here')                # {}
```

Emit it from any language — it's just a stdout line:

```python
print("__RESULT__", json.dumps({"accuracy": acc}))           # Python
```
```js
console.log("__RESULT__", JSON.stringify({ accuracy: acc })); // JavaScript
```
```bash
echo "__RESULT__ {\"accuracy\": $ACC}"                        # shell
```

## 6. Next steps

- **[TUTORIAL.md](TUTORIAL.md)** — build a full hypothesis → experiment →
  measure → learn loop: failure classes, gates, dead-end promotion and dedupe,
  binding your own runner/store via ports, and custom verdict strategies.
- **[README.md](README.md)** — the API map and the design rationale.
