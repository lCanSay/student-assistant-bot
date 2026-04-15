"""
Locust load test for the RAG pipeline.

Run:
  locust -f scripts/locustfile.py --headless -u 50 -r 5 -t 3m --host http://localhost:8000

  -u 50    = max 50 concurrent users
  -r 5     = spawn 5 users per second
  -t 3m    = run for 3 minutes
"""

import random
from locust import HttpUser, task, between, events

# Typical student queries in different languages / styles
QUERIES = [
    "как взять ретейк?",
    "как пересдать экзамен?",
    "что такое add drop?",
    "где находится деканат?",
    "как получить транскрипт?",
    "как заселиться в общежитие?",
    "что нужно для военной кафедры?",
    "какие документы нужны для отсрочки?",
    "как перевестись на другую специальность?",
    "где взять справку об обучении?",
    "какие кабинеты свободны?",
    "расписание экзаменов",
    "retake алгоритмы",
    "как оплатить обучение?",
    "где медцентр кбту?",
    "как записаться на элективы?",
    "формула оценки gpa",
    "что такое fx оценка?",
    "как подать апелляцию?",
    "где офис регистратора?",
]


class RAGUser(HttpUser):
    """Simulates a student asking questions to the bot."""
    wait_time = between(1, 3)

    @task(5)
    def search_only(self):
        """Vector search — heaviest task, tests pgvector throughput."""
        query = random.choice(QUERIES)
        with self.client.post(
            "/test-search",
            json={"query": query},
            name="/test-search",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")

    @task(3)
    def embed_only(self):
        """Embedding generation — tests E5 model throughput."""
        query = random.choice(QUERIES)
        with self.client.post(
            "/test-embed",
            json={"text": query},
            name="/test-embed",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")

    @task(1)
    def full_rag(self):
        """Full RAG pipeline — tests everything end-to-end."""
        query = random.choice(QUERIES)
        with self.client.post(
            "/test-rag",
            json={"query": query},
            name="/test-rag",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 429:
                # Expected: Groq free tier rate limit
                resp.success()
                events.request.fire(
                    request_type="POST",
                    name="/test-rag [RATE LIMITED]",
                    response_time=resp.elapsed.total_seconds() * 1000,
                    response_length=0,
                    exception=None,
                )
            else:
                resp.failure(f"HTTP {resp.status_code}")
