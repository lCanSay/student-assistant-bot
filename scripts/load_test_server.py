"""
FastAPI wrapper around the RAG pipeline for load testing.

Exposes 3 endpoints to test each layer independently:
  POST /test-embed   — embedding generation only
  POST /test-search  — vector search only (no LLM)
  POST /test-rag     — full pipeline: embed → search → LLM → response

Run:
  python scripts/load_test_server.py          # real Groq
  MOCK_LLM=true python scripts/load_test_server.py  # fake LLM (no Groq)
"""

import asyncio
import os
import sys
import time
import random
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("loadtest")

MOCK_LLM = os.getenv("MOCK_LLM", "").lower() in ("true", "1", "yes")
if MOCK_LLM:
    logger.info("🧪 MOCK_LLM=true — Groq will NOT be called, fake responses used")


# ── Lifespan: init DB on startup ─────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    from core.database import engine, Base
    import core.models
    import core.wsp_models

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database ready")
    yield


app = FastAPI(title="RAG Load Test Server", lifespan=lifespan)


# ── Request / Response models ─────────────────────────────────────────
class QueryRequest(BaseModel):
    query: str = "как взять ретейк?"


class EmbedRequest(BaseModel):
    text: str = "как взять ретейк?"


class EmbedResponse(BaseModel):
    vector_dim: int
    time_ms: float


class SearchResponse(BaseModel):
    items_found: int
    top_distance: float | None
    time_ms: float


class RAGResponse(BaseModel):
    answer: str
    knowledge_found: int
    files_found: int
    time_ms: float
    llm_model: str


# ── Endpoint 1: Embedding only ────────────────────────────────────────
@app.post("/test-embed", response_model=EmbedResponse)
async def test_embed(req: EmbedRequest):
    """Test embedding generation speed (E5 model)."""
    from services.embeddings import get_vector

    t0 = time.perf_counter()
    vec = await asyncio.to_thread(get_vector, req.text, True)
    elapsed = (time.perf_counter() - t0) * 1000

    return EmbedResponse(vector_dim=len(vec), time_ms=round(elapsed, 2))


# ── Endpoint 2: Vector search only ───────────────────────────────────
@app.post("/test-search", response_model=SearchResponse)
async def test_search(req: QueryRequest):
    """Test pgvector cosine distance search (no LLM call)."""
    import services.repo as repo
    from core.database import async_session

    t0 = time.perf_counter()
    async with async_session() as session:
        results = await repo.search_knowledge(session, req.query, limit=3)
    elapsed = (time.perf_counter() - t0) * 1000

    items = [(item, dist) for item, dist in results if dist <= 0.35]
    top_dist = items[0][1] if items else None

    return SearchResponse(
        items_found=len(items),
        top_distance=round(top_dist, 4) if top_dist else None,
        time_ms=round(elapsed, 2),
    )


# ── Endpoint 3: Full RAG pipeline ────────────────────────────────────
@app.post("/test-rag", response_model=RAGResponse)
async def test_rag(req: QueryRequest):
    """Full RAG: embed → search → (optional LLM) → response."""
    import services.repo as repo
    from core.database import async_session

    t0 = time.perf_counter()

    async with async_session() as session:
        # Vector search
        knowledge_with_score = await repo.search_knowledge(session, req.query, limit=3)
        knowledge_items = [(item, dist) for item, dist in knowledge_with_score if dist <= 0.35]

        # Build context
        context_parts = []
        for item, dist in knowledge_items:
            if item.title:
                context_parts.append(f"[{item.title}]\n{item.content}")
            else:
                context_parts.append(item.content)
        context = "\n\n---\n\n".join(context_parts)

        # File search
        file_candidates = await repo.search_files(session, req.query, limit=5)

        # Curated files
        curated_files = []
        seen = set()
        for item, _ in knowledge_items:
            for f in await repo.get_linked_files(session, item.id):
                if f.id not in seen:
                    curated_files.append(f)
                    seen.add(f.id)

    if not context:
        elapsed = (time.perf_counter() - t0) * 1000
        return RAGResponse(
            answer="Нет данных в базе знаний по этому запросу.",
            knowledge_found=0,
            files_found=len(curated_files),
            time_ms=round(elapsed, 2),
            llm_model="none",
        )

    # LLM call (or mock)
    model_used = "mock"
    if MOCK_LLM:
        await asyncio.sleep(random.uniform(0.2, 0.5))
        ai_reply = f"[MOCK] Ответ на основе {len(knowledge_items)} записей базы знаний."
    else:
        try:
            from services.ai_service import get_ai_answer, MODELS
            ai_reply = await get_ai_answer(req.query, context)
            model_used = MODELS[0]  # primary; fallback logged in ai_service
        except Exception as e:
            error_name = type(e).__name__
            if "RateLimit" in error_name or "429" in str(e):
                raise HTTPException(status_code=429, detail=f"Groq rate limit: {e}")
            raise HTTPException(status_code=500, detail=f"LLM error: {error_name}: {e}")

    elapsed = (time.perf_counter() - t0) * 1000
    return RAGResponse(
        answer=ai_reply[:200],
        knowledge_found=len(knowledge_items),
        files_found=len(curated_files) + len(file_candidates),
        time_ms=round(elapsed, 2),
        llm_model=model_used,
    )


# ── Health check ──────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "mock_llm": MOCK_LLM}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
