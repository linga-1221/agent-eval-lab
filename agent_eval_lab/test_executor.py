"""Test execution via subprocess: runs generated pytest tests and reports results."""

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass, field, asdict

from agent_eval_lab.failure_modes import detect_failure_modes


@dataclass
class TestExecutionResult:
    """Results from executing generated tests in a subprocess."""
    success: bool  # all tests passed
    exit_code: int
    passed: int
    failed: int
    skipped: int
    total: int
    output: str
    error: str = ""
    duration: float = 0.0
    coverage: Optional[float] = None  # line coverage percentage for the function code
    failure_modes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["pass_rate"] = self.pass_rate
        return d

    @property
    def pass_rate(self) -> float:
        return (self.passed / self.total * 100) if self.total > 0 else 0.0

    @classmethod
    def from_dict(cls, data: dict) -> "TestExecutionResult":
        return cls(**data)


def _extract_function_name(function_code: str) -> Optional[str]:
    """Extract the first top-level function name from code using AST."""
    try:
        tree = ast.parse(function_code)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return node.name
    except SyntaxError:
        return None
    return None


def _parse_pytest_summary(output: str) -> Tuple[int, int, int]:
    """Parse pytest output to get passed, failed, skipped counts."""
    # Look for summary pattern in final lines. Examples:
    # "3 passed, 1 failed in 0.12s"
    # "2 passed, 1 skipped in 0.05s"
    # "All 3 tests passed"
    for line in reversed(output.strip().split('\n')):
        line = line.strip()
        if not line:
            continue
        passed_match = re.search(r'(\d+)\s+passed', line)
        failed_match = re.search(r'(\d+)\s+failed', line)
        skipped_match = re.search(r'(\d+)\s+skipped', line)
        if passed_match or failed_match or skipped_match:
            passed = int(passed_match.group(1)) if passed_match else 0
            failed = int(failed_match.group(1)) if failed_match else 0
            skipped = int(skipped_match.group(1)) if skipped_match else 0
            return passed, failed, skipped
    return 0, 0, 0


def _collect_coverage_data(temp_dir: Path, target_pattern: str = "target.py") -> Optional[float]:
    """Collect coverage data for the target file from coverage.json."""
    try:
        coverage_json_path = temp_dir / "coverage.json"
        if not coverage_json_path.exists():
            return None
        with open(coverage_json_path, 'r') as f:
            data = json.load(f)
        # Find coverage for target file
        for file_path, file_data in data.get("files", {}).items():
            if file_path.endswith(target_pattern):
                summary = file_data.get("summary", {})
                covered = summary.get("covered_lines", 0)
                total = summary.get("num_statements", 0)
                if total > 0:
                    return (covered / total) * 100
        return None
    except Exception:
        return None


def run_tests(
    function_code: str,
    test_code: str,
    timeout: int = 30,
    collect_coverage: bool = False,
) -> TestExecutionResult:
    """Run generated tests in a subprocess via pytest.

    Args:
        function_code: Python function code under test
        test_code: Generated pytest test code
        timeout: Timeout in seconds for test execution
        collect_coverage: Whether to measure code coverage

    Returns:
        TestExecutionResult with detailed results
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="agent_eval_"))
    start_time = time.time()

    try:
        # Write target.py (function code)
        target_path = temp_dir / "target.py"
        target_path.write_text(function_code)

        # Write test_generated.py
        # We import * from target to expose the function(s) directly in global namespace
        # This matches the expectation that generated tests call the function without prefix
        test_content = f"""# Auto-generated test wrapper
from target import *
{test_code}
"""
        test_path = temp_dir / "test_generated.py"
        test_path.write_text(test_content)

        # Build command
        if collect_coverage:
            cmd = [
                sys.executable, "-m", "coverage", "run", "-m", "pytest",
                "test_generated.py", "-q", "--tb=short"
            ]
        else:
            cmd = [sys.executable, "-m", "pytest", "test_generated.py", "-q", "--tb=short"]

        proc = subprocess.run(
            cmd,
            cwd=temp_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration = time.time() - start_time

        output = proc.stdout + proc.stderr
        passed, failed, skipped = _parse_pytest_summary(output)
        total = passed + failed + skipped

        success = proc.returncode == 0 and total > 0 and failed == 0

        result = TestExecutionResult(
            success=success,
            exit_code=proc.returncode,
            passed=passed,
            failed=failed,
            skipped=skipped,
            total=total,
            output=output,
            duration=duration,
        )

        # Collect coverage if requested
        if collect_coverage:
            coverage = _collect_coverage_data(temp_dir)
            result.coverage = coverage

        # Detect additional failure modes from execution
        failure_modes = detect_failure_modes(test_code, {"history": []})
        if proc.returncode != 0:
            if "ImportError" in output or "ModuleNotFoundError" in output or "cannot import" in output:
                failure_modes.append("test_import_error")
            elif "SyntaxError" in output or "IndentationError" in output:
                failure_modes.append("test_syntax_error")
            elif "Timeout" in output or "timed out" in output:
                failure_modes.append("test_timeout")
            elif total == 0 and "collected" not in output.lower():
                failure_modes.append("test_collection_error")
            else:
                failure_modes.append("test_execution_failed")
        result.failure_modes = failure_modes

        return result

    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        return TestExecutionResult(
            success=False,
            exit_code=-1,
            passed=0,
            failed=0,
            skipped=0,
            total=0,
            output="",
            error="Test execution timed out",
            duration=duration,
            failure_modes=["test_timeout"],
        )
    except Exception as e:
        duration = time.time() - start_time
        return TestExecutionResult(
            success=False,
            exit_code=-1,
            passed=0,
            failed=0,
            skipped=0,
            total=0,
            output="",
            error=str(e),
            duration=duration,
            failure_modes=["test_execution_exception"],
        )
    finally:
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except Exception as e:
            import warnings
            warnings.warn(f"Failed to clean up temp dir {temp_dir}: {e}")
