"""Adapter protocols. Each project binds these to its own infra (no impl here)."""
from __future__ import annotations

from typing import Any, Protocol, Sequence, runtime_checkable

from .types import ExperimentResult


@runtime_checkable
class Spawn(Protocol):
    async def __call__(self, prompt: str) -> str: ...


@runtime_checkable
class Retriever(Protocol):
    async def retrieve(self, query: str, k: int = 8) -> Sequence[dict[str, Any]]: ...


@runtime_checkable
class KnowledgeGraph(Protocol):
    async def prior_findings(self, query: str) -> Sequence[dict[str, Any]]: ...
    async def write_finding(self, finding: dict[str, Any]) -> None: ...


@runtime_checkable
class ExperimentRunner(Protocol):
    def run(self, plan: dict[str, Any], workdir: str) -> ExperimentResult: ...


@runtime_checkable
class Store(Protocol):
    def save_verdict(self, thread_id: str, record: Any) -> None: ...
    def load_dead_end_hashes(self, scope: str) -> set[str]: ...
    def save_dead_end(self, scope: str, record: Any) -> None: ...
