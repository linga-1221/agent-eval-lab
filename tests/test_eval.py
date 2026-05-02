"""Tests for the eval harness logic."""

from agent_eval_lab.golden_set import GOLDEN_SET


def test_golden_set_not_empty():
    assert len(GOLDEN_SET) >= 15


def test_golden_set_structure():
    for item in GOLDEN_SET:
        assert "name" in item
        assert "code" in item
        assert "expected_edge_cases" in item
        assert "min_tests" in item
        assert isinstance(item["min_tests"], int)
        assert item["min_tests"] >= 3
