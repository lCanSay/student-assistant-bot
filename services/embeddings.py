from sentence_transformers import SentenceTransformer

# Load model once when the module is imported
model = SentenceTransformer('intfloat/multilingual-e5-base')

def get_vector(text: str, is_query: bool = False) -> list[float]:
    prefix = "query: " if is_query else "passage: "
    return model.encode(prefix + text).tolist()
