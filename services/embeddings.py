from sentence_transformers import SentenceTransformer

class EmbeddingsService:
    def __init__(self, model_name='intfloat/multilingual-e5-base'):
        self.model = SentenceTransformer(model_name)

    def get_vector(self, text: str, is_query: bool = False) -> list[float]:
        # E5 models expect 'query: ' prefix for search queries and 'passage: ' for documents
        prefix = "query: " if is_query else "passage: "
        return self.model.encode(prefix + text).tolist()

# Singleton instance
embeddings_service = EmbeddingsService()
