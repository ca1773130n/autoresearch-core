# autoresearch-core

[![CI](https://github.com/ca1773130n/autoresearch-core/actions/workflows/ci.yml/badge.svg)](https://github.com/ca1773130n/autoresearch-core/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/autoresearch-core.svg)](https://pypi.org/project/autoresearch-core/)
[![Python](https://img.shields.io/pypi/pyversions/autoresearch-core.svg)](https://pypi.org/project/autoresearch-core/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A tiny, **pure-Python decision-contracts library** for autoresearch / agentic
loops: a *deterministic* verdict (metric / comparator / target), failure
classification, gates, and promotion record shapes — the disciplined decision
core, with **zero runtime dependencies** and **no I/O**.

You bring the loop, the retrieval, the runner, and the storage; you bind them to
the library's `Protocol`s and call `measure` / `decide` / `should_promote_dead_end`
at your decision points. The verdict logic is parity-tested against the
[GRD](https://github.com/ca1773130n/GetResearchDone) autoresearch loop.

## Why

Agentic research loops fail in a predictable way: the model grades its own
homework. An LLM proposes a hypothesis, runs an experiment, then *judges*
whether the result supports the hypothesis — and judgment drifts.
`autoresearch-core` removes the judge from the control path:

1. Every hypothesis must carry a **machine-readable contract**
   (`MetricSpec`: *which metric, which comparator, which target*).
2. Experiments report results through a **machine-readable line**
   (`__RESULT__ {"accuracy": 0.93}` on stdout).
3. The verdict is **computed, not judged**: metric vs target →
   `supported` / `refuted` / `inconclusive`.
4. Only a **deterministic refutation** may auto-promote a dead-end. Anything
   judged by an LLM or inferred from an exit code is advisory.

## Install

```bash
pip install autoresearch-core
```

Requires Python 3.11+. No runtime dependencies. Fully typed (`py.typed`).

## Quickstart

```python
from autoresearch_core import (
    MetricSpec, ExperimentResult, measure, parse_metrics_line, should_promote_dead_end,
)

spec = MetricSpec(metric_key="recall_at_10", comparator=">=", target=0.8)

# An experiment prints `__RESULT__ {"recall_at_10": 0.83}` on stdout:
metrics = parse_metrics_line(stdout)        # -> {"recall_at_10": 0.83}
verdict = measure(spec, ExperimentResult(metrics=metrics, exit_code=0))

verdict.verdict          # "supported" | "refuted" | "inconclusive"  (deterministic)
verdict.evidence_level   # "deterministic"
should_promote_dead_end(verdict)            # True only for a deterministic refutation
```

## Documentation

- **[QUICKSTART](https://github.com/ca1773130n/autoresearch-core/blob/main/QUICKSTART.md)** —
  zero to a working deterministic verdict in five minutes, with a complete
  runnable script.
- **[TUTORIAL](https://github.com/ca1773130n/autoresearch-core/blob/main/TUTORIAL.md)** —
  build a full hypothesis → experiment → measure → learn loop on top of the
  library: contracts, failure classes, gates, dead-end promotion, infrastructure
  ports, and custom verdict strategies.
- **[CHANGELOG](https://github.com/ca1773130n/autoresearch-core/blob/main/CHANGELOG.md)**

## What it owns (and what it doesn't)

**Owns — the decision discipline:**

| Module | Public surface | Job |
|---|---|---|
| `types` | `MetricSpec`, `ExperimentResult`, `VerdictRecord`, `Hypothesis`, `Takeaway`, `GateState`, `GateCheck` | Frozen dataclasses; pure data, no logic |
| `contract` | `parse_metrics_line`, `validate_metric_spec` | The `__RESULT__ {json}` experiment-result contract |
| `verdict` | `compare`, `DeterministicVerdict`, `VerdictStrategy` | Metric vs target → supported / refuted / inconclusive |
| `failures` | `classify_run_failure` | stderr → `H2` (missing dep) / `H3` (missing file / permission) / `H4` (timeout / runtime) / `none` |
| `gates` | `resolve_gates`, `check_gate` | Approval gates (`execute`, `kg_write`) resolved from config |
| `policy` | `measure`, `decide`, `decide_branch`, `should_terminate`, `detect_plateau`, `should_promote_dead_end` | The loop's branch / terminate / promote decisions |
| `promote` | `DeadEndRecord`, `KnowhowRecord`, `approach_hash`, `build_dead_end_record`, `should_skip` | Promotion record shapes + approach dedupe |

**Doesn't own — bind these via `ports.py` `Protocol`s to your own infra:**
`Spawn` (LLM call), `Retriever`, `KnowledgeGraph`, `ExperimentRunner`, `Store`.
No implementations ship in this package; the
[tutorial](https://github.com/ca1773130n/autoresearch-core/blob/main/TUTORIAL.md)
shows minimal bindings.

## Verdict authority

`DeterministicVerdict` is the default and the reason this package exists. Other
strategies (an LLM judge, an exit-code check) can be plugged in via the
`VerdictStrategy` protocol, but **only a deterministic refutation auto-promotes a
dead-end** — non-deterministic verdicts are advisory. Every verdict records its
`strategy` and `evidence_level`, so the decision trail stays auditable.

## Development

```bash
pip install -e ".[dev]"
pytest -q --cov=autoresearch_core
```

The test suite includes a parity suite (`tests/test_parity.py`) that pins
behaviour to the GRD TypeScript implementation.

## License

MIT © Cameleon X — see [LICENSE](LICENSE).
