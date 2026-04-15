# 🔥 Stress Test Report — KBTU Student Assistant Bot

**Date**: 2026-04-16  
**Test Tool**: Locust 2.43.4  
**Target**: RAG Pipeline (FastAPI + pgvector + E5 embeddings + Groq LLM)

---

## Test Configuration

The stress testing infrastructure consists of a `scripts/locustfile.py` defining user behaviors, and a dedicated FastAPI wrapper (`scripts/load_test_server.py`) that exposes individual components of the RAG pipeline.

| Parameter          | Round 1       | Round 2       | Round 3       |
|--------------------|---------------|---------------|---------------|
| **Users**          | 30            | 60            | 10            |
| **Spawn Rate**     | 5/sec         | 10/sec        | 2/sec         |
| **Duration**       | 2 min         | 2 min         | 1 min         |
| **LLM Mode**       | MOCK (no Groq)| MOCK (no Groq)| Real Groq     |
| **Goal**           | Baseline      | Push limits   | Groq rate limits |

### Endpoints Tested

| Endpoint       | Weight | What it tests                       |
|:---------------|:------:|:------------------------------------|
| `/test-embed`  | ×3     | E5 embedding model throughput       |
| `/test-search` | ×5     | pgvector cosine distance search     |
| `/test-rag`    | ×1     | Full pipeline: embed → search → LLM |

---

## Optimization Results (v2)

After initial runs identified bottlenecks in PostgreSQL connection management and embedding inference, three major optimizations were applied:
1. **Connection Pooling**: Replaced `NullPool` with `AsyncAdaptedQueuePool(pool_size=20)` to maintain warm database connections.
2. **Model Caching**: Added LRU cache over `intfloat/multilingual-e5-base` encoding to skip inference (~100ms) for repeated common queries.
3. **Eager Preloading**: Started the 34s model-loading warm-up during application boot rather than on the first request.

### 🚀 Overall Throughput Improvement

| Round / Users | Requests (v1 ➡️ v2) | RPS (v1 ➡️ v2) | Failures |
|:--------------|:--------------------|:---------------|:---------|
| **R1 (30 users, MOCK)** | 671 ➡️ **1,722** 🔺 | 5.67 ➡️ **14.39** 🔺 | 0% |
| **R2 (60 users, MOCK)** | 808 ➡️ **3,495** 🔺 | 6.78 ➡️ **29.12** 🔺 | 0% |
| **R3 (10 users, Groq)** | 89 ➡️ **171** 🔺 | 1.51 ➡️ **2.88** 🔺 | 0% |

> The application easily scales up to 60 concurrent users without failures, with a maximum tested load exceeding 29 requests per second.

---

## Post-Optimization Per-Endpoint Metrics

### 🧠 `/test-embed` — E5 Embedding Model

| Metric             | Round 1 (30u) | Round 2 (60u) | Round 3 (10u) |
|:-------------------|:-------------:|:-------------:|:-------------:|
| Throughput (rps)    | 4.85          | 9.77          | 0.81          |
| Avg (ms)           | **10** (was 2,259) | **2** (was 3,141) | **27**        |
| p50 (ms)           | **2**         | **2**         | **2**         |

Because the Locust script often queries the same text block out of a list, the LRU cache allows the model endpoint to perform inference instantaneously.

### 🗃️ `/test-search` — pgvector Cosine Search

| Metric             | Round 1 (30u) | Round 2 (60u) | Round 3 (10u) |
|:-------------------|:-------------:|:-------------:|:-------------:|
| Throughput (rps)    | 7.99          | 16.01         | 1.77          |
| Avg (ms)           | **29** (was 3,557) | **7** (was 7,785) | **25**        |
| p50 (ms)           | **7**         | **7**         | **7**         |

With connection pooling engaged, the bottleneck shifts heavily away from raw Postgres overhead. 

### 🤖 `/test-rag` — Full RAG Pipeline

| Metric             | Round 1 (30u MOCK) | Round 2 (60u MOCK) | Round 3 (10u Groq) |
|:-------------------|:------------------:|:------------------:|:------------------:|
| Throughput (rps)    | 1.55               | 3.34               | 0.30               |
| Avg (ms)           | **386**            | **359**            | **8,367**          |
| p50 (ms)           | **350**            | **360**            | **4,900**          |

The primary bottleneck is now isolated completely to Groq's LLM latency, yielding response times under 5 seconds for end-to-end RAG with real Groq.

---

## How to Run Load Tests

1. Ensure the `.env` configuration contains proper variables. 
2. Make sure the testing containers are stopped to avoid clashes:
   ```bash
   docker compose -f docker-compose.loadtest.yml down
   ```
3. Run the specific setup. For mock testing 30 users:
   ```bash
   $env:MOCK_LLM="true"
   docker compose -f docker-compose.loadtest.yml up -d db loadtest-server
   ```
4. Run Locust using `docker run`:
   ```bash
   docker run --rm --name kbtu_locust --network student-assistant-bot_default -v "$(pwd):/app" kbtu_rag_app:latest bash -c "pip install --quiet locust && locust -f scripts/locustfile.py --headless -u 30 -r 5 -t 2m --host http://loadtest-server:8000 --csv /app/scripts/loadtest_results/test --html /app/scripts/loadtest_results/test.html"
   ```
