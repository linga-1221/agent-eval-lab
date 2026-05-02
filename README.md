# Agent Eval Lab

> A multi-agent system for automated PyTest generation, paired with an honest evaluation harness that scores LLM output across syntax, coverage, and failure modes.

Built to explore one question: **how do you trust an LLM that writes code for you?**

---

## What it does

You give it a Python function. Two LLM agents collaborate:

1. **Generator agent** writes PyTest test cases for the function
2. **Reviewer agent** critiques the tests and triggers regeneration if quality is low

Then an **evaluation harness** runs the agent loop over a hand-curated golden set of 15 functions and scores the output on:

- Syntax validity (does the code parse?)
- Test coverage (does it meet the minimum count?)
- Assertion presence (do the tests actually test something?)
- PyTest conformance

It also detects common LLM failure modes — truncation, missing assertions, context drift, hallucinated imports, API-level tool-use failures — and logs them per run.

---

## Why this exists

Most LLM "demo" projects ignore the hard part: knowing when the LLM is wrong. This project takes that seriously.

- **Honest scoring.** No vibes-based "looks good." Every output is scored on objective AST-level criteria.
- **Failure modes documented.** The README has a known-limitations section. The eval harness logs which mode each failure hit.
- **Reproducible.** Same golden set, same prompts, same model — diff your runs across prompt changes to catch regressions.

---

## Tech Stack

- **Python 3.11+** — clean, type-hinted, structured
- **LangChain** — multi-agent orchestration
- **Groq API** — free, fast inference (llama-3.3-70b-versatile)
- **Pydantic** — schema-validated agent outputs
- **PyTest** — testing the test generator
- **Click + Rich** — CLI with pretty output
- **GitHub Actions** — CI runs unit tests on every push
- **Docker** — reproducible eval runs

---

## Architecture

Function Code → Generator Agent (LLM + schema) → PyTest Code → Reviewer Agent (LLM + schema) → if acceptable: Eval Harness + Scoring; if not: Retry up to 2 times.

---

## Quickstart

### 1. Get a free Groq API key

Sign up at console.groq.com — no credit card needed.

### 2. Install

git clone https://github.com/linga-1221/agent-eval-lab.git
cd agent-eval-lab
python -m venv venv
.\venv\Scripts\Activate.ps1   (Windows)
source venv/bin/activate      (Linux / Mac)
pip install -r requirements.txt
pip install -e .
cp .env.example .env
Add your GROQ_API_KEY to .env

### 3. Run unit tests

pytest tests/ -v

### 4. Run the eval suite

python -m agent_eval_lab.cli eval

### 5. Generate tests for a single function

python -m agent_eval_lab.cli generate "def add(a, b): return a + b"

### 6. List golden-set items

python -m agent_eval_lab.cli list-golden

---

## Sample Output

![Eval Results](eval_screenshot.png)

Real run on the golden set:

- Average score: 80/100
- Pass rate: 66.67%
- 15 functions evaluated
- 9 of 15 functions scored 100/100 on first or retry attempt
- 3 of 15 hit empty_output after both retries failed (Groq tool-use bug)
- Several generator_api_failure events were caught and recovered via retry — the system did not crash

---

## Known Failure Modes

The harness explicitly tracks these. They are real, they happen, and pretending otherwise is how LLM products quietly degrade.

- truncated_output — Response cut off mid-function due to context limits
- missing_assertions — LLM writes test functions with no assert statements
- context_drift_natural_language_in_code — Markdown fences or "Here are the tests" leaked into code
- hallucinated_import — Imports a module that does not exist
- malformed_syntax — Missing colons, broken indentation
- generator_api_failure — Groq API returned a 400 (tool-use mis-format), handled by retry
- reviewer_api_failure — Reviewer agent failed to return structured output
- empty_output — Both retries failed, output was empty

Each run logs to runs/agent_eval.log and detailed JSON to runs/eval_results.json.

---

## What I learned building this

- Tool-use is fragile. Groq's structured-output endpoint occasionally returns tool_use_failed 400s even when the model output looks valid. The retry loop catches roughly half of these.
- AST scoring beats string matching. Parsing generated code with Python's ast module gives reliable signals (test count, assertion count) that regex-based scoring misses.
- Two retries is the sweet spot. Three retries did not materially improve pass rate but doubled latency.
- The Reviewer agent helps less than I expected. Most genuine quality wins came from the Generator's own prompt clarity, not from the Reviewer catching issues.

---

## Limitations (honest list)

- Golden set is small (15 functions). Real production eval would need hundreds across diverse domains.
- Reviewer is the same model as Generator. A stronger reviewer (different model) would catch more issues.
- Quality scoring is heuristic, not semantic. I score on AST features, not whether tests are truly useful.
- No human-in-the-loop step yet. A v2 would let me mark generations as good/bad and fine-tune the Reviewer prompt.

---

## Roadmap

- Run generated tests via subprocess and report pass/fail
- Add coverage measurement with coverage.py
- Support multiple LLM providers (OpenAI, Anthropic, local)
- Web UI for browsing eval runs
- LLM-as-judge: third agent that scores Generator + Reviewer outputs

---

## Why I built this

I am a final-year CS student interested in the production side of LLM systems — eval infrastructure, failure-mode analysis, agentic workflows. Most learning resources on agents stop at "look, two LLMs can talk to each other." This project goes one step further: how do you measure if they are actually doing useful work?

---

## Author

**Kuchivaripalli Nagalinga**
Final-year B.Tech CSE — Python + AI Engineering
GitHub: https://github.com/linga-1221
LinkedIn: https://www.linkedin.com/in/nagalinga-k
