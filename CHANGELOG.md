# Changelog

All notable changes to `autoresearch-core` are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/), and the project
adheres to [Semantic Versioning](https://semver.org/).

## [0.4.3] - 2026-06-07
### Changed
- **Versioning now tracks GRD's version line** (GRD is the reference
  implementation): this release ships what was staged as 0.2.0, renumbered to
  match GRD v0.4.3. Versions 0.2.x–0.4.2 of this package never existed.
### Added
- Life-harness rounds (pure): `Finding`/`PatchEntry`/`RoundPatch`/`EvalReport`/
  `AutonomyState`/`RoundRecord` types; `rounds.py` policy (`resolve_autonomy`,
  `select_evidence`, `validate_round_patch` with path guards + self-protection,
  `patch_hash` dedupe, `should_apply`, `decide_round`); adapter protocols
  `FindingsSource`/`PatchProposer`/`RoundEvaluator`/`Applier`/`RoundStore`.
  Design: docs/superpowers/specs/2026-06-06-life-harness-rounds-design.md.

## [0.1.2] - 2026-06-04
### Added
- `QUICKSTART.md` (zero to a working verdict, complete runnable script) and
  `TUTORIAL.md` (full hypothesis → experiment → measure → learn walkthrough:
  contracts, failure classes, gates, dead-end promotion, ports, custom
  strategies). All examples executed and verified against the public API.
### Changed
- README: design rationale ("Why"), module-by-module API map, doc links.
- No code changes — docs-only release so PyPI renders the new README.

## [0.1.1] - 2026-06-03
### Fixed
- Reject non-finite metric values (`1e999` → `inf`, `nan`) in `parse_metrics_line`
  and `validate_metric_spec`, matching JS `JSON.parse` semantics.
- `approach_hash` collapses internal whitespace before hashing.
- `build_dead_end_record` raises unless the verdict is a deterministic refutation.
- `resolve_gates` tolerates a non-mapping `research_gates` config value.
- `ExperimentResult` defensively copies `metrics` so the frozen instance is immutable.

## [0.1.0] - 2026-06-03
### Added
- Initial release: `MetricSpec`, deterministic `Verdict` (`measure`), failure
  classifier (H2/H3/H4), gate model, decision policy (`decide`,
  `detect_plateau`, `should_promote_dead_end`), promotion record shapes, and the
  adapter `Protocol`s (`Spawn`, `Retriever`, `KnowledgeGraph`, `ExperimentRunner`,
  `Store`). Pure-Python, zero runtime dependencies; behaviour parity-tested
  against the GRD autoresearch loop.
