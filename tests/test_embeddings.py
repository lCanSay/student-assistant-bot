import importlib
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from services import embeddings


def test_build_enriched_text_includes_all_sections():
    text = embeddings.build_enriched_text(
        content="Основной текст",
        title="Заголовок",
        category="Категория",
        keywords=["ключ1", "ключ2"],
    )

    assert "Title: Заголовок" in text
    assert "Category: Категория" in text
    assert "Keywords: ключ1, ключ2" in text
    assert "Content: Основной текст" in text


def test_build_enriched_text_omits_empty_sections():
    text = embeddings.build_enriched_text(content="Текст", title=None, category=None, keywords=None)
    assert text == "Content: Текст"


def test_get_vector_uses_query_prefix(monkeypatch):
    dummy_calls = []

    class DummyModel:
        def encode(self, value):
            dummy_calls.append(value)

            class Result:
                def tolist(self):
                    return [0.5, 0.6]

            return Result()

    monkeypatch.setattr(embeddings, "model", DummyModel())
    result = embeddings.get_vector("привет", is_query=True)

    assert result == [0.5, 0.6]
    assert dummy_calls == ["query: привет"]


def test_get_vector_loads_sentence_transformer(monkeypatch):
    created = []

    class DummySentenceTransformer:
        def __init__(self, model_name):
            created.append(model_name)

        def encode(self, value):
            class Result:
                def tolist(self):
                    return [1.0, 2.0, 3.0]

            return Result()

    monkeypatch.setattr(embeddings, "model", None)
    monkeypatch.setattr(embeddings, "SentenceTransformer", DummySentenceTransformer)

    result = embeddings.get_vector("тест")

    assert result == [1.0, 2.0, 3.0]
    assert created == ["intfloat/multilingual-e5-base"]
