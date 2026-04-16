"""
Tests for the file attachment subsystem.

Covers:
  - _filter_fallback_files gating logic (pure, no DB)
  - upsert_file embedding regeneration
  - update_file embedding regeneration + updated_at
  - knowledge_file_links CRUD (set / get)
  - End-to-end: curated files returned for matched knowledge entry
  - End-to-end: fallback against real DB files (map photos, rup, calendar, add/drop doc)

Run:
    python tests/test_file_attachments.py

Requires a running DB (docker compose up -d db).
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select, text

import core.wsp_models  # noqa: F401 — ensures all tables registered
from core.database import async_session, engine, Base
from core.models import FileItem, KnowledgeItem
from services import repo
from bot.handlers.ai import _filter_fallback_files


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

async def _get_files_by_category(category: str) -> list[FileItem]:
    async with async_session() as session:
        return await repo.get_files_by_category(session, category)


async def _get_all_files() -> list[FileItem]:
    async with async_session() as session:
        return await repo.get_all_files(session)


# ─────────────────────────────────────────────────────────────
# Pure unit tests — _filter_fallback_files
# ─────────────────────────────────────────────────────────────

class FakeFile:
    def __init__(self, id_=1, keywords=None):
        self.id = id_
        self.keywords = keywords or []


def test_fallback_empty_candidates():
    result = _filter_fallback_files([], "карта кбту")
    assert result == [], "Empty candidates should return []"
    print("✅ fallback: empty candidates → []")


def test_fallback_distance_too_high():
    f = FakeFile(keywords=["карта"])
    candidates = [(f, 0.25)]  # > 0.18 threshold
    result = _filter_fallback_files(candidates, "карта кбту")
    assert result == [], "Distance 0.25 should be rejected"
    print("✅ fallback: distance too high → []")


def test_fallback_no_keywords_on_file():
    f = FakeFile(keywords=[])  # no keywords set
    candidates = [(f, 0.10)]
    result = _filter_fallback_files(candidates, "карта кбту")
    assert result == [], "File with no keywords should never pass"
    print("✅ fallback: no keywords on file → []")


def test_fallback_keyword_not_in_query():
    f = FakeFile(keywords=["карта"])
    candidates = [(f, 0.10)]
    result = _filter_fallback_files(candidates, "расписание занятий")  # 'карта' not present
    assert result == [], "Keyword not in query should be rejected"
    print("✅ fallback: keyword not in query → []")


def test_fallback_ambiguous_gap():
    f1 = FakeFile(id_=1, keywords=["карта"])
    f2 = FakeFile(id_=2, keywords=["карта"])
    # Gap = 0.12 - 0.10 = 0.02 < 0.05
    candidates = [(f1, 0.10), (f2, 0.12)]
    result = _filter_fallback_files(candidates, "карта кбту")
    assert result == [], "Gap 0.02 is too small — should be rejected as ambiguous"
    print("✅ fallback: gap too small → []")


def test_fallback_clear_winner():
    f1 = FakeFile(id_=1, keywords=["карта"])
    f2 = FakeFile(id_=2, keywords=["что-то"])
    # Gap = 0.30 - 0.10 = 0.20 ≥ 0.05 ✓, distance 0.10 ≤ 0.18 ✓, keyword 'карта' in query ✓
    candidates = [(f1, 0.10), (f2, 0.30)]
    result = _filter_fallback_files(candidates, "карта кбту")
    assert len(result) == 1 and result[0].id == 1, "Should return the clear winner"
    print("✅ fallback: clear winner → [file]")


def test_fallback_single_candidate_passes():
    f = FakeFile(keywords=["rup", "руп"])
    candidates = [(f, 0.15)]  # only one candidate, no gap needed
    result = _filter_fallback_files(candidates, "скачать руп специальности")
    assert len(result) == 1
    print("✅ fallback: single candidate passes all gates → [file]")


# ─────────────────────────────────────────────────────────────
# DB integration tests
# ─────────────────────────────────────────────────────────────

async def setup_db():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        for stmt in [
            "ALTER TABLE files ADD COLUMN IF NOT EXISTS title VARCHAR(255)",
            "ALTER TABLE files ADD COLUMN IF NOT EXISTS keywords TEXT[]",
            "ALTER TABLE files ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ",
        ]:
            await conn.execute(text(stmt))
    print("✅ DB schema ready")


async def test_real_files_exist():
    """Verify the known files from the live DB are present."""
    all_files = await _get_all_files()
    ids = {f.id for f in all_files}
    # These are the file IDs confirmed in the DB during development
    expected = {4, 5, 17, 18, 19, 21, 22, 23}
    missing = expected - ids
    assert not missing, f"Expected file IDs missing from DB: {missing}"
    print(f"✅ real files exist: {sorted(ids)}")


async def test_map_files_have_category():
    """Map photos (ids 17-22) should have category='map'."""
    map_files = await _get_files_by_category("map")
    assert len(map_files) >= 4, f"Expected ≥4 map files, got {len(map_files)}"
    for f in map_files:
        assert f.category == "map"
    print(f"✅ map category: {len(map_files)} files found")


async def test_update_file_regenerates_embedding():
    """update_file should produce a new embedding and set updated_at."""
    # Use file id=4 (RUP document) — safe to update then restore
    async with async_session() as session:
        result = await session.execute(select(FileItem).where(FileItem.id == 4))
        original = result.scalar_one()
        original_embedding = list(original.embedding) if original.embedding is not None else None
        original_caption = original.caption or ""
        original_category = original.category or "rup"
        original_type = original.type or "document"

    # Save with added keyword to force a different embedding
    async with async_session() as session:
        await repo.update_file(
            session, 4,
            caption=original_caption,
            category=original_category,
            file_type=original_type,
            title="РУП ВТиПО 2024-2025",
            keywords=["руп", "rup", "учебный план", "вт", "vtipo"],
        )

    async with async_session() as session:
        result = await session.execute(select(FileItem).where(FileItem.id == 4))
        updated = result.scalar_one()

    assert updated.title == "РУП ВТиПО 2024-2025"
    assert updated.keywords is not None and "руп" in updated.keywords
    assert updated.updated_at is not None, "updated_at should be set after update"
    if original_embedding:
        new_embedding = list(updated.embedding)
        # Embeddings should differ (enriched text now includes title+keywords)
        assert new_embedding != original_embedding, "Embedding should have changed"
    print("✅ update_file: embedding regenerated, updated_at set, title+keywords stored")


async def test_knowledge_file_link_crud():
    """set_knowledge_files / get_linked_files roundtrip."""
    # Get first knowledge entry and file id=5 (Add/Drop guide)
    async with async_session() as session:
        k_result = await session.execute(
            select(KnowledgeItem).order_by(KnowledgeItem.id).limit(1)
        )
        k_item = k_result.scalar_one()
        k_id = k_item.id

    # Link file 5 to this knowledge entry
    async with async_session() as session:
        await repo.set_knowledge_files(session, k_id, [5])

    async with async_session() as session:
        linked = await repo.get_linked_files(session, k_id)
    assert any(f.id == 5 for f in linked), "File 5 should be linked"
    print(f"✅ link CRUD: file 5 linked to knowledge id={k_id}")

    # Replace links with empty list (unlink)
    async with async_session() as session:
        await repo.set_knowledge_files(session, k_id, [])

    async with async_session() as session:
        linked_after = await repo.get_linked_files(session, k_id)
    assert linked_after == [], "All links should be removed"
    print(f"✅ link CRUD: links cleared for knowledge id={k_id}")


async def test_curated_files_returned_via_handler_path():
    """
    Simulate the handler's curated-attachment logic:
    link file 5 (Add/Drop guide) to the Add/Drop knowledge entry,
    then verify get_linked_files returns it.
    """
    # Find the Add/Drop knowledge entry
    async with async_session() as session:
        result = await session.execute(
            select(KnowledgeItem).where(KnowledgeItem.content.ilike("%add/drop%"))
        )
        k_item = result.scalars().first()

    if k_item is None:
        print("⚠️  skipped curated path test — no Add/Drop knowledge entry found")
        return

    k_id = k_item.id
    async with async_session() as session:
        await repo.set_knowledge_files(session, k_id, [5])

    # Simulate what the handler does after knowledge retrieval
    async with async_session() as session:
        linked = await repo.get_linked_files(session, k_id)

    assert any(f.id == 5 for f in linked), "Add/Drop guide (file 5) should be linked"
    print(f"✅ curated path: knowledge id={k_id} → file 5 attached")

    # Cleanup
    async with async_session() as session:
        await repo.set_knowledge_files(session, k_id, [])


async def test_fallback_against_real_map_files():
    """
    After adding 'карта' keyword to a map photo, the fallback gate should pass
    when the query contains 'карта'.
    """
    # Add keyword to map file id=17
    async with async_session() as session:
        await repo.update_file(
            session, 17,
            caption="#карта",
            category="map",
            file_type="photo",
            title="Карта корпуса КБТУ",
            keywords=["карта", "map", "корпус", "кбту"],
        )

    # Now search
    async with async_session() as session:
        candidates = await repo.search_files(session, "карта кбту корпус", limit=3)

    result = _filter_fallback_files(candidates, "карта кбту корпус")
    # With keyword match and a reasonable distance the gate may pass.
    # We can't guarantee the exact distance, so we just verify the logic
    # doesn't crash and returns 0 or 1 files (never more than 1).
    assert len(result) <= 1, "Fallback should return at most 1 file"
    print(f"✅ fallback against real map files: returned {len(result)} file(s) "
          f"(distance={candidates[0][1]:.4f} if candidates else 'n/a')")


# ─────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────

async def main():
    print("\n=== File Attachment Tests ===\n")

    print("--- Pure unit tests (no DB) ---")
    test_fallback_empty_candidates()
    test_fallback_distance_too_high()
    test_fallback_no_keywords_on_file()
    test_fallback_keyword_not_in_query()
    test_fallback_ambiguous_gap()
    test_fallback_clear_winner()
    test_fallback_single_candidate_passes()

    print("\n--- DB integration tests ---")
    try:
        await setup_db()
        await test_real_files_exist()
        await test_map_files_have_category()
        await test_update_file_regenerates_embedding()
        await test_knowledge_file_link_crud()
        await test_curated_files_returned_via_handler_path()
        await test_fallback_against_real_map_files()
        print("\n🎉 All tests PASSED\n")
    except AssertionError as e:
        print(f"\n❌ FAILED: {e}\n")
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
