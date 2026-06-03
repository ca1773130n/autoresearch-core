"""Core data definitions for autoresearch-core. Pure data, no logic, no I/O."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Verdict = Literal["supported", "refuted", "inconclusive"]
Comparator = Literal[">=", "<=", ">", "<", "=="]
FailureClass = Literal["H2", "H3", "H4", "none"]
EvidenceLevel = Literal["deterministic", "exit_code", "llm"]
HypothesisStatus = Literal[
    "open", "testing", "supported", "refuted", "inconclusive", "superseded"
]
TakeawayKind = Literal[
    "success_pattern", "failure_root_cause", "constraint", "domain_fact", "tool_pattern"
]


@dataclass(frozen=True)
class MetricSpec:
    """The machine-readable verdict contract a hypothesis must carry."""
    metric_key: str
    comparator: Comparator
    target: float


@dataclass(frozen=True)
class ExperimentResult:
    metrics: dict[str, float]
    exit_code: int
    failure_class: FailureClass = "none"
    runner: str = "subprocess"
    duration_ms: int = 0
    stdout_excerpt: str = ""


@dataclass(frozen=True)
class VerdictRecord:
    verdict: Verdict
    strategy: str
    evidence_level: EvidenceLevel
    detail: str
    raw_evidence_ref: str | None = None


@dataclass(frozen=True)
class Hypothesis:
    id: str
    iteration: int
    statement: str
    predicted_outcome: str
    status: HypothesisStatus = "open"
    parent_id: str | None = None
    verdict: Verdict | None = None


@dataclass(frozen=True)
class Takeaway:
    kind: TakeawayKind
    content: str
    confidence: float
    evidence: str
    failure_class: FailureClass
    iteration: int


@dataclass(frozen=True)
class GateState:
    execute: bool = True
    kg_write: bool = True


@dataclass(frozen=True)
class GateCheck:
    proceed: bool
    pending_gate: str | None = None
