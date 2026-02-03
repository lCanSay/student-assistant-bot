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
