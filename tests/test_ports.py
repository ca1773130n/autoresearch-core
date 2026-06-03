from autoresearch_core.ports import ExperimentRunner, Store
from autoresearch_core.types import ExperimentResult


class FakeRunner:
    def run(self, plan: dict, workdir: str) -> ExperimentResult:
        return ExperimentResult(metrics={"x": 1.0}, exit_code=0)


class FakeStore:
    def __init__(self):
        self.dead_ends: dict[str, list] = {}

    def save_verdict(self, thread_id: str, record) -> None:
        pass

    def load_dead_end_hashes(self, scope: str) -> set[str]:
        return set()

    def save_dead_end(self, scope: str, record) -> None:
        self.dead_ends.setdefault(scope, []).append(record)


def test_fakes_satisfy_protocols():
    assert isinstance(FakeRunner(), ExperimentRunner)
    assert isinstance(FakeStore(), Store)
