from sentence_transformers import SentenceTransformer

# Load model once when the module is imported
# This acts like a singleton without needing a class
model = SentenceTransformer('intfloat/multilingual-e5-base')

def get_vector(text: str, is_query: bool = False) -> list[float]:
    """
    Convert text to a vector using the loaded model.
    Adds 'query: ' or 'passage: ' prefix for E5 models.
    """
    prefix = "query: " if is_query else "passage: "
    return model.encode(prefix + text).tolist()
