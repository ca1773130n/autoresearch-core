"""autoresearch-core: pure-Python decision contracts for autoresearch loops."""

__version__ = "0.1.0"

from .types import (
    Comparator, EvidenceLevel, ExperimentResult, FailureClass, GateState,
    Hypothesis, MetricSpec, Takeaway, Verdict, VerdictRecord,
)
from .contract import parse_metrics_line, validate_metric_spec
from .failures import classify_run_failure
from .verdict import compare, DeterministicVerdict, VerdictStrategy
from .gates import resolve_gates, check_gate
from .policy import (
    decide_branch, should_terminate, detect_plateau, should_promote_dead_end,
    measure, decide,
)
from .promote import (
    DeadEndRecord, KnowhowRecord, approach_hash, build_dead_end_record, should_skip,
)
from .ports import Spawn, Retriever, KnowledgeGraph, ExperimentRunner, Store

__all__ = [
    "Comparator", "EvidenceLevel", "ExperimentResult", "FailureClass", "GateState",
    "Hypothesis", "MetricSpec", "Takeaway", "Verdict", "VerdictRecord",
    "parse_metrics_line", "validate_metric_spec", "classify_run_failure",
    "compare", "DeterministicVerdict", "VerdictStrategy", "resolve_gates", "check_gate",
    "decide_branch", "should_terminate", "detect_plateau", "should_promote_dead_end",
    "measure", "decide",
    "DeadEndRecord", "KnowhowRecord", "approach_hash", "build_dead_end_record", "should_skip",
    "Spawn", "Retriever", "KnowledgeGraph", "ExperimentRunner", "Store",
]
