"""Multi-agent system: Generator writes tests, Reviewer critiques them, Judge evaluates.
Also includes caching, logging, and usage tracking.
"""

import os
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.callbacks import BaseCallbackHandler

from .llm_providers import LLMProvider, create_structured_chain
from .instrumentation import log


# ---------- Schemas ----------
class GeneratedTest(BaseModel):
    """Schema-validated output from the Generator agent."""
    test_code: str = Field(..., description="Complete PyTest test code")
    test_count: int = Field(..., description="Number of test cases generated")
    reasoning: str = Field(..., description="Why these tests cover the function")


class ReviewFeedback(BaseModel):
    """Schema-validated output from the Reviewer agent."""
    is_acceptable: bool = Field(..., description="Whether tests are good enough")
    issues: List[str] = Field(default_factory=list, description="Problems found")
    suggestions: List[str] = Field(default_factory=list, description="Improvements")
    quality_score: int = Field(..., ge=0, le=10, description="Score 0-10")


class JudgeFeedback(BaseModel):
    """Schema-validated output from the Judge agent (LLM-as-judge)."""
    semantic_score: int = Field(..., ge=0, le=10, description="Semantic quality score 0-10")
    edge_case_coverage: str = Field(..., description="Assessment of edge case coverage")
    test_effectiveness: str = Field(..., description="How effective the tests are")
    improvements: List[str] = Field(default_factory=list, description="Specific improvement suggestions")
    would_run_in_production: bool = Field(..., description="Whether these tests are production-worthy")


# ---------- Prompts ----------
GENERATOR_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a test generation agent. Your job is to write comprehensive PyTest test cases for the given Python function.

Rules:
1. Generate at least 4 test cases covering: happy path, edge cases, invalid inputs, boundary conditions
2. Use clear, descriptive test names (test_<scenario>)
3. Include assertions with informative messages
4. Return ONLY valid Python code that can run with pytest
5. Do not include the original function - only the test code

Output your response as JSON matching this schema:
{{"test_code": "<full pytest code>", "test_count": <number>, "reasoning": "<why these tests are good>"}}"""),
    ("user", "Generate PyTest tests for this function:\n\n```python\n{function_code}\n```")
])

REVIEWER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a test review agent. Critique the generated PyTest tests for quality.

Check:
1. Do the tests cover edge cases (empty input, None, negative numbers, etc.)?
2. Are assertions meaningful?
3. Is the syntax valid Python/PyTest?
4. Are there missing scenarios?

Output as JSON:
{{"is_acceptable": <bool>, "issues": [<list of problems>], "suggestions": [<list of improvements>], "quality_score": <0-10>}}"""),
    ("user", "Function:\n```python\n{function_code}\n```\n\nGenerated tests:\n```python\n{test_code}\n```\n\nReview them.")
])

JUDGE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert test quality judge. Evaluate the generated tests for semantic correctness and usefulness.

Consider:
1. Do the tests actually verify the function's behavior correctly?
2. Are edge cases and boundary conditions comprehensive?
3. Would these tests catch real bugs?
4. Is the test structure maintainable and clear?

Provide a candid assessment. Output as JSON:
{{"semantic_score": <0-10>, "edge_case_coverage": "<description>", "test_effectiveness": "<description>", "improvements": [<list>], "would_run_in_production": <bool>}}"""),
    ("user", "Function:\n```python\n{function_code}\n```\n\nGenerated tests:\n```python\n{test_code}\n```\n\nJudge the quality.")
])


# ---------- Caching ----------
_agent_cache: Dict[tuple, Any] = {}


def _make_cache_key(
    agent_type: str,
    function_code: str,
    test_code: Optional[str] = None,
    provider: Optional[LLMProvider] = None,
    temperature: float = 0.2,
) -> tuple:
    """Create a hashable cache key."""
    provider_name = provider.get_provider_name() if provider else "default"
    model = getattr(provider, "model", "unknown")
    return (agent_type, function_code, test_code, provider_name, model, temperature)


# ---------- Usage Tracking ----------
class UsageCallbackHandler(BaseCallbackHandler):
    """Callback to track token usage from LLM calls."""
    def __init__(self, usage_store: Dict[str, int]):
        self.usage_store = usage_store

    def on_llm_end(self, response, **kwargs):
        # Try to extract token usage from response metadata
        token_usage = {}
        if hasattr(response, "llm_output") and response.llm_output:
            token_usage = response.llm_output.get("token_usage", {})
        elif hasattr(response, "response_metadata"):
            token_usage = response.response_metadata.get("token_usage", {})
        # Accumulate
        self.usage_store["prompt_tokens"] += token_usage.get("prompt_tokens", 0)
        self.usage_store["completion_tokens"] += token_usage.get("completion_tokens", 0)
        self.usage_store["total_tokens"] += token_usage.get("total_tokens", 0)


# ---------- Agent Functions ----------
def generator_agent(
    function_code: str,
    provider: Optional[LLMProvider] = None,
    temperature: float = 0.2,
    callbacks: Optional[list] = None,
) -> Optional[GeneratedTest]:
    """Generator agent: writes PyTest tests for a function."""
    if provider is None:
        provider = get_provider()
    cache_key = _make_cache_key("generator", function_code, None, provider, temperature)
    if cache_key in _agent_cache:
        log.debug("Generator cache hit")
        return _agent_cache[cache_key]
    log.debug("Generator cache miss")
    chain = create_structured_chain(
        prompt=GENERATOR_PROMPT,
        provider=provider,
        output_schema=GeneratedTest,
        temperature=temperature,
    )
    try:
        if callbacks:
            result = chain.invoke({"function_code": function_code}, config={"callbacks": callbacks})
        else:
            result = chain.invoke({"function_code": function_code})
        if result is not None:
            _agent_cache[cache_key] = result
        return result
    except Exception as e:
        log.error(f"[Generator] Failed: {e}")
        return None


def reviewer_agent(
    function_code: str,
    test_code: str,
    provider: Optional[LLMProvider] = None,
    temperature: float = 0.1,
    callbacks: Optional[list] = None,
) -> Optional[ReviewFeedback]:
    """Reviewer agent: critiques the generated tests."""
    if provider is None:
        provider = get_provider()
    cache_key = _make_cache_key("reviewer", function_code, test_code, provider, temperature)
    if cache_key in _agent_cache:
        log.debug("Reviewer cache hit")
        return _agent_cache[cache_key]
    log.debug("Reviewer cache miss")
    chain = create_structured_chain(
        prompt=REVIEWER_PROMPT,
        provider=provider,
        output_schema=ReviewFeedback,
        temperature=temperature,
    )
    try:
        if callbacks:
            result = chain.invoke({
                "function_code": function_code,
                "test_code": test_code
            }, config={"callbacks": callbacks})
        else:
            result = chain.invoke({
                "function_code": function_code,
                "test_code": test_code
            })
        if result is not None:
            _agent_cache[cache_key] = result
        return result
    except Exception as e:
        log.error(f"[Reviewer] Failed: {e}")
        return None


def judge_agent(
    function_code: str,
    test_code: str,
    provider: Optional[LLMProvider] = None,
    temperature: float = 0.0,
    callbacks: Optional[list] = None,
) -> Optional[JudgeFeedback]:
    """Judge agent: provides semantic evaluation of test quality."""
    if provider is None:
        provider = get_provider()
    cache_key = _make_cache_key("judge", function_code, test_code, provider, temperature)
    if cache_key in _agent_cache:
        log.debug("Judge cache hit")
        return _agent_cache[cache_key]
    log.debug("Judge cache miss")
    chain = create_structured_chain(
        prompt=JUDGE_PROMPT,
        provider=provider,
        output_schema=JudgeFeedback,
        temperature=temperature,
    )
    try:
        if callbacks:
            result = chain.invoke({
                "function_code": function_code,
                "test_code": test_code
            }, config={"callbacks": callbacks})
        else:
            result = chain.invoke({
                "function_code": function_code,
                "test_code": test_code
            })
        if result is not None:
            _agent_cache[cache_key] = result
        return result
    except Exception as e:
        log.error(f"[Judge] Failed: {e}")
        return None


# ---------- Provider ----------
def get_provider() -> LLMProvider:
    """Get the configured LLM provider."""
    from .llm_providers import get_provider
    return get_provider()


# ---------- Agent Loop ----------
def run_agent_loop(
    function_code: str,
    max_iterations: int = 2,
    provider: Optional[LLMProvider] = None,
    use_judge: bool = False,
) -> dict:
    """Run the full Generator -> Reviewer loop with retries.

    Args:
        function_code: The Python function to generate tests for
        max_iterations: Max number of generate-review cycles
        provider: Optional LLM provider (uses configured default if None)
        use_judge: Whether to run the judge agent for semantic evaluation

    Returns:
        dict with final_test_code, history, judge_feedback, usage, passed flag
    """
    # Resolve provider once
    if provider is None:
        provider = get_provider()

    # Initialize usage tracking
    usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "model": getattr(provider, "model", "unknown"),
        "provider": provider.get_provider_name(),
    }
    usage_handler = UsageCallbackHandler(usage)
    callbacks = [usage_handler]

    history = []
    judge_feedback = None

    for iteration in range(max_iterations):
        # Clear generator cache on retries so each iteration gets a fresh LLM call
        if iteration > 0:
            cache_key = _make_cache_key("generator", function_code, None, provider, 0.2)
            _agent_cache.pop(cache_key, None)
        gen_result = generator_agent(function_code, provider=provider, callbacks=callbacks)
        if gen_result is None:
            history.append({"iteration": iteration, "status": "generator_failed"})
            continue
        review = reviewer_agent(function_code, gen_result.test_code, provider=provider, callbacks=callbacks)
        if review is None:
            history.append({
                "iteration": iteration,
                "test_code": gen_result.test_code,
                "test_count": gen_result.test_count,
                "status": "reviewer_failed"
            })
            continue
        history.append({
            "iteration": iteration,
            "test_code": gen_result.test_code,
            "test_count": gen_result.test_count,
            "review": review.model_dump(),
        })
        if review.is_acceptable and review.quality_score >= 7:
            if use_judge:
                judge_feedback = judge_agent(function_code, gen_result.test_code, provider=provider, callbacks=callbacks)
            return {
                "final_test_code": gen_result.test_code,
                "history": history,
                "passed": True,
                "judge_feedback": judge_feedback.model_dump() if judge_feedback else None,
                "usage": usage,
            }

    best = max(
        [h for h in history if "review" in h],
        key=lambda h: h["review"]["quality_score"],
        default=None
    )
    final_code = best["test_code"] if best else None
    if use_judge and final_code:
        judge_feedback = judge_agent(function_code, final_code, provider=provider, callbacks=callbacks)
    return {
        "final_test_code": final_code,
        "history": history,
        "passed": False,
        "judge_feedback": judge_feedback.model_dump() if judge_feedback else None,
        "usage": usage,
    }
