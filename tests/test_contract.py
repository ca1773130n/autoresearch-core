import pytest
from autoresearch_core.contract import parse_metrics_line, validate_metric_spec
from autoresearch_core.types import MetricSpec


def test_parses_first_result_line_numeric_only():
    assert parse_metrics_line('noise\n__RESULT__ {"latency_ms": 180, "ok": "yes"}\nmore') == {
        "latency_ms": 180.0
    }


def test_excludes_bool_values():
    # bool is a subclass of int in Python; must not leak in as 1.0/0.0
    assert parse_metrics_line('__RESULT__ {"passed": true, "n": 3}') == {"n": 3.0}


def test_missing_marker_or_bad_json_returns_empty():
    assert parse_metrics_line("no marker here") == {}
    assert parse_metrics_line("__RESULT__ {not json}") == {}


def test_rejects_nan_and_infinity_like_js():
    # JS JSON.parse rejects these tokens; GRD returns {} — match that.
    assert parse_metrics_line('__RESULT__ {"x": NaN}') == {}
    assert parse_metrics_line('__RESULT__ {"x": Infinity}') == {}


def test_first_of_multiple_result_lines():
    assert parse_metrics_line('__RESULT__ {"a": 1}\n__RESULT__ {"a": 2}') == {"a": 1.0}


def test_validate_metric_spec():
    validate_metric_spec(MetricSpec("recall", ">=", 0.8))  # no raise
    with pytest.raises(ValueError):
        validate_metric_spec(MetricSpec("", ">=", 0.8))
    with pytest.raises(ValueError):
        validate_metric_spec(MetricSpec("x", "!=", 0.8))  # type: ignore[arg-type]


def test_greedy_regex_drops_line_with_trailing_junk_grd_parity():
    # INTENTIONAL: GRD's runner.ts regex is greedy (\{.*\}), so a line with
    # trailing JSON-shaped junk captures the whole span, JSON.parse fails, and
    # the result is dropped. We MATCH that behavior on purpose. Do not "fix" to
    # non-greedy — that would diverge from GRD. The __RESULT__ contract is one
    # clean `{json}` per line.
    assert parse_metrics_line('__RESULT__ {"a": 1} junk {"b": 2}') == {}


def test_validate_metric_spec_rejects_bool_target():
    with pytest.raises(ValueError):
        validate_metric_spec(MetricSpec("x", ">=", True))  # type: ignore[arg-type]


def test_parse_metrics_drops_overflow_to_inf():
    # 1e999 overflows to float('inf') in Python JSON; must be dropped (non-finite guard).
    assert parse_metrics_line('__RESULT__ {"x": 1e999}') == {}


def test_parse_metrics_drops_neg_inf():
    # -1e999 overflows to float('-inf'); must also be dropped.
    assert parse_metrics_line('__RESULT__ {"x": -1e999}') == {}


def test_validate_metric_spec_rejects_inf_target():
    with pytest.raises(ValueError):
        validate_metric_spec(MetricSpec("x", ">=", float("inf")))


def test_validate_metric_spec_rejects_nan_target():
    with pytest.raises(ValueError):
        validate_metric_spec(MetricSpec("x", ">=", float("nan")))
