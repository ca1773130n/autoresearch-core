from autoresearch_core.failures import classify_run_failure


def test_classify():
    assert classify_run_failure("", True) == "H4"                       # timeout wins
    assert classify_run_failure("ModuleNotFoundError: x", False) == "H2"
    assert classify_run_failure("ImportError: bad", False) == "H2"
    assert classify_run_failure("bash: foo: command not found", False) == "H2"
    assert classify_run_failure("not found: foo", False) == "H2"
    assert classify_run_failure("ENOENT: no such file", False) == "H3"
    assert classify_run_failure("permission denied", False) == "H3"
    assert classify_run_failure("", False) == "none"                    # empty stderr
    assert classify_run_failure("segfault boom", False) == "H4"         # other runtime


def test_h2_takes_precedence_over_h3_when_both_present():
    # GRD checks H2 before H3
    assert classify_run_failure("ImportError and No such file or directory", False) == "H2"
