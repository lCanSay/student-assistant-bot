"""
Prometheus metrics for the KBTU Student Assistant Bot.

All metric objects are defined here. Handler/service code imports what it needs.
No other file should define metrics.
"""

import logging
import time
from contextlib import asynccontextmanager

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    start_http_server,
)

logger = logging.getLogger(__name__)

# ── Histograms (latency) ─────────────────────────────────────────────

RAG_STEP_DURATION = Histogram(
    "bot_rag_step_duration_seconds",
    "Duration of individual RAG pipeline steps",
    labelnames=["step"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

LLM_REQUEST_DURATION = Histogram(
    "bot_llm_request_duration_seconds",
    "Duration of a single LLM API call attempt",
    labelnames=["model", "status"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

EMBEDDING_DURATION = Histogram(
    "bot_embedding_duration_seconds",
    "Time to compute a single embedding vector",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.5, 1.0, 5.0),
)

# ── Counters ──────────────────────────────────────────────────────────

REQUESTS_TOTAL = Counter(
    "bot_requests_total",
    "Total messages processed by handler type",
    labelnames=["handler"],
)

RAG_OUTCOME = Counter(
    "bot_rag_outcome_total",
    "Outcome of AI chat handler",
    labelnames=["outcome"],
)

LLM_MODEL_USED = Counter(
    "bot_llm_model_used_total",
    "Which LLM model ultimately provided the answer",
    labelnames=["model"],
)

LLM_FALLBACK_TOTAL = Counter(
    "bot_llm_fallback_total",
    "LLM transient errors triggering fallback",
    labelnames=["model", "error_type"],
)

THROTTLE_DROPS = Counter(
    "bot_throttle_drops_total",
    "Messages dropped by throttle middleware",
)

FILE_SEND_ERRORS = Counter(
    "bot_file_send_errors_total",
    "Errors sending files via Telegram API",
)

FEEDBACK_TOTAL = Counter(
    "bot_feedback_total",
    "User feedback events",
    labelnames=["value"],
)

# ── Gauges ────────────────────────────────────────────────────────────

ACTIVE_LLM_REQUESTS = Gauge(
    "bot_active_llm_requests",
    "Currently in-flight LLM requests",
)

# ── Observation histograms (quality signals) ──────────────────────────

KNOWLEDGE_RESULTS = Histogram(
    "bot_knowledge_results_count",
    "Number of knowledge items passing distance threshold per query",
    buckets=(0, 1, 2, 3),
)

VECTOR_DISTANCE_TOP = Histogram(
    "bot_vector_distance_top1",
    "Cosine distance of the top-1 knowledge result",
    buckets=(0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50),
)

# ── Info ──────────────────────────────────────────────────────────────

BOT_INFO = Info("bot", "Bot build information")

# ── Helpers ───────────────────────────────────────────────────────────


@asynccontextmanager
async def track_step(step_name: str):
    """Async context manager that records duration of a RAG pipeline step."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        RAG_STEP_DURATION.labels(step=step_name).observe(elapsed)


def start_metrics_server(port: int = 9100):
    """Start the Prometheus HTTP server on a background thread."""
    start_http_server(port)
    logger.info("Prometheus metrics server started on port %d", port)
