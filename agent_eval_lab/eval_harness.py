"""Eval harness: scores agent output against the golden set, runs tests, tracks usage, snapshots."""

import ast
import json
import os
import difflib
import time
from pathlib import Path
from typing import Optional, Dict, Any

from agent_eval_lab.agents import run_agent_loop
from agent_eval_lab.golden_set import GOLDEN_SET
from agent_eval_lab.failure_modes import detect_failure_modes
from agent_eval_lab.test_executor import run_tests, TestExecutionResult
from agent_eval_lab.instrumentation import log

# Default weights for AST scoring
DEFAULT_WEIGHTS = {
    "syntax_valid": 30,
    "covers_min_tests": 25,
    "has_assertions": 25,
    "uses_pytest": 20,
}

def get_weights() -> Dict[str, int]:
    """Get scoring weights from environment or defaults."""
    env_weights = os.getenv("EVAL_WEIGHTS")
    if env_weights:
        try:
            custom = json.loads(env_weights)
            return custom
        except Exception as e:
            log.warning(f"Invalid EVAL_WEIGHTS: {e}. Using defaults.")
    return DEFAULT_WEIGHTS.copy()

def compute_overall_score(scores: Dict[str, bool], weights: Optional[Dict[str, int]] = None) -> float:
    """Weighted score 0-100."""
    if weights is None:
        weights = get_weights()
    total = 0
    for key, weight in weights.items():
        if scores.get(key):
            total += weight
    return total


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


def evaluate_one(
    item: dict,
    test_timeout: int = 30,
    collect_coverage: bool = False,
    snapshot_dir: Optional[str] = None,
    update_snapshots: bool = False,
) -> dict:
    """Run agents on one golden-set item, score output, and execute tests.

    Args:
        item: Golden set item with code, name, min_tests, etc.
        test_timeout: Timeout in seconds for test execution
        collect_coverage: Whether to measure code coverage
        snapshot_dir: Directory for snapshot files (if None, snapshots disabled)
        update_snapshots: If True, write new snapshots instead of comparing

    Returns:
        Dict with scores, agent results, execution results, usage, and snapshot diff
    """
    name = item["name"]
    log.info(f"Evaluating '{name}'...")
    agent_start = time.time()
    agent_result = run_agent_loop(item["code"], max_iterations=2, use_judge=True)
    agent_elapsed = time.time() - agent_start

    test_code = agent_result.get("final_test_code") or ""
    scores = score_test_code(test_code, item["min_tests"])
    overall = compute_overall_score(scores)
    failure_modes = detect_failure_modes(test_code, agent_result)

    # Execute tests via subprocess if we have test code
    execution_result = None
    if test_code:
        exec_start = time.time()
        exec_result = run_tests(
            function_code=item["code"],
            test_code=test_code,
            timeout=test_timeout,
            collect_coverage=collect_coverage,
        )
        exec_elapsed = time.time() - exec_start
        exec_dict = exec_result.to_dict()
        exec_dict["agent_elapsed_sec"] = round(agent_elapsed, 2)
        exec_dict["exec_elapsed_sec"] = round(exec_elapsed, 2)
        execution_result = exec_dict
        failure_modes.extend(exec_result.failure_modes)
    else:
        failure_modes.append("no_test_code_generated")

    # Snapshot handling
    snapshot_diff = None
    if snapshot_dir and test_code:
        snap_path = Path(snapshot_dir) / f"{name}.txt"
        if update_snapshots:
            snap_path.parent.mkdir(parents=True, exist_ok=True)
            snap_path.write_text(test_code)
        elif snap_path.exists():
            old = snap_path.read_text()
            if old != test_code:
                failure_modes.append("snapshot_mismatch")
                diff = ''.join(difflib.unified_diff(
                    old.splitlines(keepends=True),
                    test_code.splitlines(keepends=True),
                    fromfile=f"{name}_old",
                    tofile=f"{name}_new",
                ))
                snapshot_diff = diff

    return {
        "name": name,
        "scores": scores,
        "overall_score": overall,
        "failure_modes": list(set(failure_modes)),
        "iterations": len(agent_result["history"]),
        "agent_passed": agent_result["passed"],
        "agent_elapsed_sec": round(agent_elapsed, 2),
        "execution": execution_result,
        "judge_feedback": agent_result.get("judge_feedback"),
        "agent_usage": agent_result.get("usage", {}),
        "snapshot_diff": snapshot_diff,
    }


def run_eval(
    output_path: str = "runs/eval_results.json",
    test_timeout: int = 30,
    collect_coverage: bool = False,
    workers: int = 1,
    show_progress: bool = False,
    snapshot_dir: Optional[str] = None,
    update_snapshots: bool = False,
) -> dict:
    """Run full eval suite and save results.

    Args:
        output_path: Where to save JSON results
        test_timeout: Timeout for test execution in seconds
        collect_coverage: Whether to collect code coverage metrics
        workers: Number of parallel workers (1 = sequential)
        show_progress: Whether to show a progress bar (sequential only)
        snapshot_dir: Directory for snapshot files (None to disable)
        update_snapshots: If True, update snapshots instead of comparing

    Returns:
        Summary dict with averages and detailed results
    """
    Path("runs").mkdir(exist_ok=True)
    items = GOLDEN_SET
    results = []

    if workers == 1:
        # Sequential execution
        if show_progress:
            from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            )
            with progress:
                task = progress.add_task("[green]Evaluating...", total=len(items))
                for item in items:
                    res = evaluate_one(
                        item,
                        test_timeout=test_timeout,
                        collect_coverage=collect_coverage,
                        snapshot_dir=snapshot_dir,
                        update_snapshots=update_snapshots,
                    )
                    results.append(res)
                    progress.update(task, advance=1)
        else:
            for item in items:
                results.append(evaluate_one(
                    item,
                    test_timeout=test_timeout,
                    collect_coverage=collect_coverage,
                    snapshot_dir=snapshot_dir,
                    update_snapshots=update_snapshots,
                ))
    else:
        import concurrent.futures
        # Parallel execution with order preservation
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
            # Prepare argument tuples
            args_list = [
                (item, test_timeout, collect_coverage, snapshot_dir, update_snapshots)
                for item in items
            ]
            def _eval_wrapper(args):
                return evaluate_one(*args)
            results = list(executor.map(_eval_wrapper, args_list))
        if show_progress:
            log.info("Parallel evaluation completed (progress bar not shown in parallel mode)")

    # Compute aggregate statistics
    if not results:
        return {}

    avg_score = sum(r["overall_score"] for r in results) / len(results)
    agent_pass_count = sum(1 for r in results if r["agent_passed"])
    agent_pass_rate = (agent_pass_count / len(results) * 100)

    exec_results = [r for r in results if r.get("execution")]
    if exec_results:
        exec_pass_count = sum(1 for r in exec_results if r["execution"]["success"])
        exec_pass_rate = (exec_pass_count / len(exec_results) * 100)
        coverages = [
            r["execution"].get("coverage")
            for r in exec_results
            if r["execution"].get("coverage") is not None
        ]
        avg_coverage = (sum(coverages) / len(coverages)) if coverages else None
    else:
        exec_pass_rate = 0.0
        avg_coverage = None

    # Total usage across all runs
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for r in results:
        u = r.get("agent_usage", {})
        for k in total_usage:
            total_usage[k] += u.get(k, 0)

    summary = {
        "average_score": round(avg_score, 2),
        "agent_pass_rate_percent": round(agent_pass_rate, 2),
        "execution_pass_rate_percent": round(exec_pass_rate, 2),
        "average_coverage_percent": round(avg_coverage, 2) if avg_coverage is not None else None,
        "total_items": len(results),
        "total_usage": total_usage,
        "results": results,
    }

    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)

    return summary
