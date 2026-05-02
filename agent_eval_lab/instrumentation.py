"""Lightweight instrumentation for latency and call tracking."""

import time
import logging
from contextlib import contextmanager
from pathlib import Path

Path("runs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("runs/agent_eval.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("agent_eval_lab")


@contextmanager
def timed(label: str):
    """Context manager that logs how long a block took."""
    start = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start
        log.info(f"[timing] {label}: {elapsed:.2f}s")
