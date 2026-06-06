"""Lightweight instrumentation for latency and call tracking."""

import time
import logging
from contextlib import contextmanager
from pathlib import Path

log = logging.getLogger("agent_eval_lab")


def _setup_logging() -> None:
    """Configure logging to file + stderr. Safe to call multiple times."""
    if log.handlers:
        return
    runs_dir = Path("runs")
    runs_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(runs_dir / "agent_eval.log"),
            logging.StreamHandler(),
        ],
    )


_setup_logging()  # configure on first import of this module


@contextmanager
def timed(label: str):
    """Context manager that logs how long a block took."""
    start = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start
        log.info(f"[timing] {label}: {elapsed:.2f}s")
