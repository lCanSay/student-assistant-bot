import logging
import time
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from services.metrics import EMBEDDING_DURATION

logger = logging.getLogger(__name__)

MODEL_NAME = 'intfloat/multilingual-e5-base'

# ── Eager model loading ──────────────────────────────────────────────
# Load the model once at import time so the 30-34 s cold-start penalty
# is paid during application startup, not on the first user request.
logger.info("Loading embedding model %s …", MODEL_NAME)
_model = SentenceTransformer(MODEL_NAME)
logger.info("Embedding model loaded")


# ── LRU cache for repeated queries ──────────────────────────────────
# Student queries repeat heavily (e.g. "как взять ретейк?"), so an
# in-memory cache avoids redundant ~100 ms encode() calls.
_CACHE_SIZE = 512


@lru_cache(maxsize=_CACHE_SIZE)
def _cached_encode(prefixed_text: str) -> tuple[float, ...]:
    """Encode text and return as a hashable tuple (for LRU cache)."""
    return tuple(_model.encode(prefixed_text).tolist())


def get_vector(text: str, is_query: bool = False) -> list[float]:
    prefix = "query: " if is_query else "passage: "
    prefixed = prefix + text

    start = time.perf_counter()
    result = list(_cached_encode(prefixed))
    EMBEDDING_DURATION.observe(time.perf_counter() - start)
    return result


def preload_model() -> None:
    """Explicit no-op — model is already loaded at import time.

    Kept as a public API so callers (main.py, load_test_server.py)
    can document intent and trigger the import side-effect.
    """
    pass


def build_enriched_text(
    content: str,
    title: str | None = None,
    category: str | None = None,
    keywords: list[str] | None = None,
) -> str:
    """Build the enriched passage text used for embedding generation.

    Unified format so add and update always produce the same embedding quality.
    Sections with empty/None values are omitted.
    """
    parts = []
    if title:
        parts.append(f"Title: {title}")
    if category:
        parts.append(f"Category: {category}")
    if keywords:
        parts.append(f"Keywords: {', '.join(keywords)}")
    parts.append(f"Content: {content}")
    return ". ".join(parts)
