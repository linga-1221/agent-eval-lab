"""Eval harness: scores agent output against the golden set."""

import ast
import json
import time
from pathlib import Path
from agent_eval_lab.agents import run_agent_loop
from agent_eval_lab.golden_set import GOLDEN_SET
from agent_eval_lab.failure_modes import detect_failure_modes


def score_test_code(test_code: str, expected_min_tests: int) -> dict:
    """Score generated test code on multiple dimensions."""
    scores = {
        "syntax_valid": False,
        "test_count": 0,
        "has_assertions": False,
        "covers_min_tests": False,
        "uses_pytest": False,
    }
    if not test_code:
        return scores
    try:
        tree = ast.parse(test_code)
        scores["syntax_valid"] = True
    except SyntaxError:
        return scores

    test_functions = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    scores["test_count"] = len(test_functions)
    scores["covers_min_tests"] = len(test_functions) >= expected_min_tests

    has_assert = any(isinstance(node, ast.Assert) for node in ast.walk(tree))
    has_pytest_raises = "pytest.raises" in test_code or "with raises" in test_code
    scores["has_assertions"] = has_assert or has_pytest_raises
    scores["uses_pytest"] = "import pytest" in test_code or "from pytest" in test_code or has_assert

    return scores


def compute_overall_score(scores: dict) -> float:
    """Weighted score 0-100."""
    weights = {
        "syntax_valid": 30,
        "covers_min_tests": 25,
        "has_assertions": 25,
        "uses_pytest": 20,
    }
    total = 0
    for key, weight in weights.items():
        if scores.get(key):
            total += weight
    return total


def evaluate_one(item: dict) -> dict:
    """Run agents on one golden-set item and score the output."""
    name = item["name"]
    print(f"  -> Running agents on '{name}'...")
    start = time.time()
    result = run_agent_loop(item["code"], max_iterations=2)
    elapsed = time.time() - start
    test_code = result.get("final_test_code") or ""
    scores = score_test_code(test_code, item["min_tests"])
    overall = compute_overall_score(scores)
    failures = detect_failure_modes(test_code, result)

    return {
        "name": item["name"],
        "scores": scores,
        "overall_score": overall,
        "failure_modes": failures,
        "iterations": len(result["history"]),
        "passed": result["passed"],
        "elapsed_sec": round(elapsed, 2),
    }


def run_eval(output_path: str = "runs/eval_results.json") -> dict:
    """Run full eval suite and save results."""
    Path("runs").mkdir(exist_ok=True)
    results = []
    for item in GOLDEN_SET:
        results.append(evaluate_one(item))

    avg_score = sum(r["overall_score"] for r in results) / len(results)
    pass_rate = sum(1 for r in results if r["passed"]) / len(results) * 100

    summary = {
        "average_score": round(avg_score, 2),
        "pass_rate_percent": round(pass_rate, 2),
        "total_items": len(results),
        "results": results,
    }

    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)

    return summary
