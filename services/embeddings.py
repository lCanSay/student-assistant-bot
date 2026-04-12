import logging
import time

from sentence_transformers import SentenceTransformer

from services.metrics import EMBEDDING_DURATION

logger = logging.getLogger(__name__)

model = None

def get_vector(text: str, is_query: bool = False) -> list[float]:
    global model
    if model is None:
        logger.info("Loading embedding model (first call, may take 2-5s)...")
        model = SentenceTransformer('intfloat/multilingual-e5-base')
        logger.info("Embedding model loaded")

    prefix = "query: " if is_query else "passage: "
    start = time.perf_counter()
    result = model.encode(prefix + text).tolist()
    EMBEDDING_DURATION.observe(time.perf_counter() - start)
    return result


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
