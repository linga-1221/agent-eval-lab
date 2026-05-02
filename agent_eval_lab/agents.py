"""Multi-agent system: Generator writes tests, Reviewer critiques them."""

import os
from typing import Optional
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate


class GeneratedTest(BaseModel):
    """Schema-validated output from the Generator agent."""
    test_code: str = Field(..., description="Complete PyTest test code")
    test_count: int = Field(..., description="Number of test cases generated")
    reasoning: str = Field(..., description="Why these tests cover the function")


class ReviewFeedback(BaseModel):
    """Schema-validated output from the Reviewer agent."""
    is_acceptable: bool = Field(..., description="Whether tests are good enough")
    issues: list[str] = Field(default_factory=list, description="Problems found")
    suggestions: list[str] = Field(default_factory=list, description="Improvements")
    quality_score: int = Field(..., ge=0, le=10, description="Score 0-10")


def get_llm(temperature: float = 0.2) -> ChatGroq:
    """Initialize the Groq LLM client."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set. Copy .env.example to .env and fill it in.")
    model = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")
    return ChatGroq(model=model, temperature=temperature, api_key=api_key)


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


def generator_agent(function_code: str) -> Optional[GeneratedTest]:
    """Generator agent: writes PyTest tests for a function."""
    llm = get_llm(temperature=0.2)
    structured_llm = llm.with_structured_output(GeneratedTest)
    chain = GENERATOR_PROMPT | structured_llm
    try:
        return chain.invoke({"function_code": function_code})
    except Exception as e:
        print(f"[Generator] Failed: {e}")
        return None


def reviewer_agent(function_code: str, test_code: str) -> Optional[ReviewFeedback]:
    """Reviewer agent: critiques the generated tests."""
    llm = get_llm(temperature=0.1)
    structured_llm = llm.with_structured_output(ReviewFeedback)
    chain = REVIEWER_PROMPT | structured_llm
    try:
        return chain.invoke({
            "function_code": function_code,
            "test_code": test_code
        })
    except Exception as e:
        print(f"[Reviewer] Failed: {e}")
        return None


def run_agent_loop(function_code: str, max_iterations: int = 2) -> dict:
    """Run the full Generator -> Reviewer loop with retries."""
    history = []
    for iteration in range(max_iterations):
        gen_result = generator_agent(function_code)
        if gen_result is None:
            history.append({"iteration": iteration, "status": "generator_failed"})
            continue
        review = reviewer_agent(function_code, gen_result.test_code)
        if review is None:
            history.append({"iteration": iteration, "status": "reviewer_failed"})
            continue
        history.append({
            "iteration": iteration,
            "test_code": gen_result.test_code,
            "test_count": gen_result.test_count,
            "review": review.model_dump(),
        })
        if review.is_acceptable and review.quality_score >= 7:
            return {"final_test_code": gen_result.test_code, "history": history, "passed": True}

    best = max(
        [h for h in history if "review" in h],
        key=lambda h: h["review"]["quality_score"],
        default=None
    )
    return {
        "final_test_code": best["test_code"] if best else None,
        "history": history,
        "passed": False
    }
