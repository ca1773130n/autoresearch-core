# tests/test_vectors.py
"""Executable parity vectors shared with GRD.

Canonical copy: parity/vectors.json (this repo).
Vendored copy:  GetResearchDone tests/fixtures/autoresearch-parity-vectors.json.
The two must stay byte-identical; behavior changes in either implementation
must update both copies deliberately in the same change.
"""
import json
from pathlib import Path

import autoresearch_core as ac
from autoresearch_core.types import ExperimentResult, GateState, MetricSpec

VECTORS = json.loads(
    (Path(__file__).resolve().parent.parent / "parity" / "vectors.json").read_text()
)


def test_compare_vectors():
    for c in VECTORS["compare"]:
        got = ac.compare(c["value"], c["comparator"], c["target"])
        assert got is c["expect"], c


def test_evaluate_verdict_vectors():
    for c in VECTORS["evaluate_verdict"]:
        spec = MetricSpec(
            metric_key=c["metric_key"], comparator=c["comparator"], target=c["target"]
        )
        result = ExperimentResult(
            metrics=c["metrics"], exit_code=c["exit_code"], failure_class=c["failure_class"]
        )
        rec = ac.measure(spec, result)
        assert rec.verdict == c["expect_verdict"], c["name"]


def test_parse_metrics_line_vectors():
    for c in VECTORS["parse_metrics_line"]:
        assert ac.parse_metrics_line(c["stdout"]) == c["expect"], c["name"]


def test_classify_run_failure_vectors():
    for c in VECTORS["classify_run_failure"]:
        assert ac.classify_run_failure(c["stderr"], c["timed_out"]) == c["expect"], c


def test_resolve_gates_vectors():
    for c in VECTORS["resolve_gates"]:
        gates = ac.resolve_gates(c["config"], c["no_gates"])
        assert gates.execute is c["expect"]["execute"], c
        assert gates.kg_write is c["expect"]["kg_write"], c


def test_check_gate_vectors():
    for c in VECTORS["check_gate"]:
        gates = GateState(execute=c["gates"]["execute"], kg_write=c["gates"]["kg_write"])
        out = ac.check_gate(gates, c["gate"], c["approved"])
        assert out.proceed is c["expect_proceed"], c
        assert out.pending_gate == c["expect_pending_gate"], c


def test_decide_branch_vectors():
    for c in VECTORS["decide_branch"]:
        assert ac.decide_branch(c["verdict"]) == c["expect"], c


def test_should_terminate_vectors():
    for c in VECTORS["should_terminate"]:
        done, status = ac.should_terminate(
            c["iteration"], c["max_iterations"], c["last_verdict"]
        )
        assert done is c["expect_done"], c
        assert status == c["expect_status"], c


def test_detect_plateau_vectors():
    for c in VECTORS["detect_plateau"]:
        assert ac.detect_plateau(c["verdicts"], window=c["window"]) is c["expect"], c
