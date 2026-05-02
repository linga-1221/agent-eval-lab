"""Detect common LLM failure modes in agent output."""

def detect_failure_modes(test_code: str, agent_result: dict) -> list[str]:
    """Return a list of failure modes detected in the output."""
    failures = []

    if not test_code:
        failures.append("empty_output")
        return failures

    if "import " in test_code:
        if "from nonexistent" in test_code or "import madeupmodule" in test_code:
            failures.append("hallucinated_import")

    if test_code.count("def ") > 0 and "def " in test_code and ":" not in test_code.split("def ")[1][:200]:
        failures.append("malformed_syntax")

    if "def test_" in test_code and "assert" not in test_code and "raises" not in test_code:
        failures.append("missing_assertions")

    if "I will" in test_code or "Here are the tests" in test_code or "```" in test_code:
        failures.append("context_drift_natural_language_in_code")

    if test_code.rstrip().endswith((",", "(", "[", "{")):
        failures.append("truncated_output")

    history = agent_result.get("history", [])
    if any(h.get("status") == "generator_failed" for h in history):
        failures.append("generator_api_failure")
    if any(h.get("status") == "reviewer_failed" for h in history):
        failures.append("reviewer_api_failure")

    return failures
