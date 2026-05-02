"""Tests for the agent system itself."""

import pytest
from agent_eval_lab.eval_harness import score_test_code, compute_overall_score
from agent_eval_lab.failure_modes import detect_failure_modes


def test_score_valid_test_code():
    code = """
import pytest

def test_add_positive():
    assert 1 + 1 == 2

def test_add_negative():
    assert -1 + -1 == -2

def test_add_zero():
    assert 0 + 0 == 0
"""
    scores = score_test_code(code, expected_min_tests=3)
    assert scores["syntax_valid"] is True
    assert scores["test_count"] == 3
    assert scores["has_assertions"] is True
    assert scores["covers_min_tests"] is True


def test_score_invalid_syntax():
    code = "def test_broken( assert True"
    scores = score_test_code(code, expected_min_tests=3)
    assert scores["syntax_valid"] is False


def test_score_empty_code():
    scores = score_test_code("", expected_min_tests=3)
    assert scores["syntax_valid"] is False
    assert scores["test_count"] == 0


def test_overall_score_perfect():
    scores = {
        "syntax_valid": True,
        "covers_min_tests": True,
        "has_assertions": True,
        "uses_pytest": True,
    }
    assert compute_overall_score(scores) == 100


def test_overall_score_zero():
    scores = {
        "syntax_valid": False,
        "covers_min_tests": False,
        "has_assertions": False,
        "uses_pytest": False,
    }
    assert compute_overall_score(scores) == 0


def test_detect_truncation():
    code = "def test_foo():\n    assert ("
    failures = detect_failure_modes(code, {"history": []})
    assert "truncated_output" in failures


def test_detect_missing_assertions():
    code = "def test_foo():\n    x = 1"
    failures = detect_failure_modes(code, {"history": []})
    assert "missing_assertions" in failures


def test_detect_empty_output():
    failures = detect_failure_modes("", {"history": []})
    assert "empty_output" in failures
