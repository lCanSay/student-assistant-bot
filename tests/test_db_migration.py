"""
Test SA 2.0 model migration.
Tests: User CRUD, KnowledgeItem vector insert, vector similarity search.
Run: python tests/test_db_migration.py
"""
import asyncio
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from core.database import engine, Base
from core.database import async_session
from core.models import KnowledgeItem, User


async def setup():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created")


async def teardown():
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM knowledge_base WHERE category = '_test'"))
        await conn.execute(text("DELETE FROM users WHERE telegram_id = 9999999"))
    print("✅ Test data cleaned up")


async def test_user_crud():
    async with async_session() as session:
        user = User(telegram_id=9999999, full_name="Test User", username="test_user")
        session.add(user)
        await session.commit()

        from sqlalchemy import select
        result = await session.execute(select(User).where(User.telegram_id == 9999999))
        fetched = result.scalar_one_or_none()

        assert fetched is not None, "❌ User not found after insert"
        assert fetched.full_name == "Test User", f"❌ Wrong name: {fetched.full_name}"
        assert fetched.requests_left == 50, f"❌ Wrong default quota: {fetched.requests_left}"
        print("✅ Test 1 PASSED: User CRUD")


async def test_vector_insert():
    vector = np.random.rand(768).tolist()

    async with async_session() as session:
        item = KnowledgeItem(content="test content", category="_test", embedding=vector)
        session.add(item)
        await session.commit()
        assert item.id is not None, "❌ KnowledgeItem ID not set after commit"
        print(f"✅ Test 2 PASSED: Vector insert (id={item.id})")


async def test_vector_search():
    # Two vectors: one close to query, one far
    query_vec = np.ones(768, dtype=float)
    query_vec /= np.linalg.norm(query_vec)

    close_vec = query_vec + np.random.rand(768) * 0.01   # very close
    far_vec   = -query_vec + np.random.rand(768) * 0.01  # opposite direction

    async with async_session() as session:
        close_item = KnowledgeItem(content="close item", category="_test", embedding=close_vec.tolist())
        far_item   = KnowledgeItem(content="far item",   category="_test", embedding=far_vec.tolist())
        session.add_all([close_item, far_item])
        await session.commit()

        from sqlalchemy import select
        distance_col = KnowledgeItem.embedding.cosine_distance(query_vec.tolist()).label("distance")
        stmt = (
            select(KnowledgeItem, distance_col)
            .where(KnowledgeItem.category == "_test")
            .order_by(distance_col)
            .limit(2)
        )
        result = await session.execute(stmt)
        rows = result.all()

        assert len(rows) >= 2, f"❌ Expected 2+ results, got {len(rows)}"
        top_item, top_dist = rows[0]
        assert top_item.content == "close item", f"❌ Wrong top result: {top_item.content} (dist={top_dist:.4f})"
        print(f"✅ Test 3 PASSED: Vector search — top result='{top_item.content}' dist={top_dist:.4f}")


async def main():
    print("\n=== SA 2.0 Migration Tests ===\n")
    try:
        await setup()
        await test_user_crud()
        await test_vector_insert()
        await test_vector_search()
        print("\n🎉 All tests PASSED\n")
    except AssertionError as e:
        print(f"\n{e}")
        sys.exit(1)
    finally:
        await teardown()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
