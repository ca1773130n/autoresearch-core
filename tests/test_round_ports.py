# tests/test_round_ports.py
"""Round adapter protocols accept minimal structural fakes."""
from autoresearch_core.ports import (
    Applier, FindingsSource, PatchProposer, RoundEvaluator, RoundStore,
)
from autoresearch_core.types import EvalReport, Finding, PatchEntry, RoundPatch, RoundRecord


class _Findings:
    def findings(self, since):
        return [Finding(kind="takeaway", content="x", source="s")]


class _Proposer:
    def propose(self, evidence_md, workdir):
        e = PatchEntry(path="a.md", kind="markdown", op="create", content="x", rationale="r")
        return RoundPatch(round_id="r", entries=(e,), summary="s", confidence=0.9)


class _Evaluator:
    def evaluate(self, patch, workdir):
        return EvalReport(checks=())


class _Applier:
    def apply(self, patch, workdir):
        return "deadbeef"

    def revert(self, sha):
        return "feedface"


class _Store:
    def save_round(self, record):
        return None

    def load_patch_hashes(self):
        return set()

    def last_round_at(self):
        return None


def test_fakes_satisfy_protocols():
    assert isinstance(_Findings(), FindingsSource)
    assert isinstance(_Proposer(), PatchProposer)
    assert isinstance(_Evaluator(), RoundEvaluator)
    assert isinstance(_Applier(), Applier)
    assert isinstance(_Store(), RoundStore)
