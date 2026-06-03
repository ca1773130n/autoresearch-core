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
at your decision points. The verdict logic is parity-tested against the GRD
autoresearch loop.

## Install

```bash
pip install autoresearch-core
```

Requires Python 3.11+. No runtime dependencies.

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

## What it owns (and what it doesn't)

**Owns — the decision discipline:**
- `MetricSpec` + the `__RESULT__` result contract (`parse_metrics_line`, `validate_metric_spec`)
- `DeterministicVerdict` / `measure` (metric vs target → supported / refuted / inconclusive)
- failure classification (`classify_run_failure` → `H2` / `H3` / `H4`)
- gates (`resolve_gates`, `check_gate`)
- policy (`decide`, `detect_plateau`, `should_promote_dead_end`)
- promotion record shapes (`DeadEndRecord`, `KnowhowRecord`, `approach_hash`, `should_skip`)

**Doesn't own — bind these via `ports.py` `Protocol`s to your own infra:**
`Spawn`, `Retriever`, `KnowledgeGraph`, `ExperimentRunner`, `Store`.

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

## License

MIT © Cameleon X — see [LICENSE](LICENSE).
