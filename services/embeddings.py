from sentence_transformers import SentenceTransformer

model = None

def get_vector(text: str, is_query: bool = False) -> list[float]:
    global model
    if model is None:
        print("Loading embedding model...")
        model = SentenceTransformer('intfloat/multilingual-e5-base')
        print("Model loaded.")

    prefix = "query: " if is_query else "passage: "
    return model.encode(prefix + text).tolist()


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
