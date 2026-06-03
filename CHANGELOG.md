# Changelog

All notable changes to `autoresearch-core` are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/), and the project
adheres to [Semantic Versioning](https://semver.org/).

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
