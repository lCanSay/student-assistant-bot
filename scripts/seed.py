"""
seed.py — populate a fresh DB from exported seed files.

Run from the project root after starting the DB:
    docker compose up -d db
    python scripts/seed.py

Requires:
    data/seed_knowledge.json   (produced by scripts/export_seed.py)
    data/seed_schedule.json    (produced by scripts/export_seed.py)

Knowledge embeddings are recomputed on import (slow first run, model downloads ~1GB).
Schedule data is inserted without embeddings.
"""

import asyncio
import json
import sys
from datetime import time as dt_time
from pathlib import Path

# Allow imports from the project root regardless of where the script is called from
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

import core.models      # noqa: F401
import core.wsp_models  # noqa: F401
from core.database import async_session, engine, Base
from core.wsp_models import DayOfWeek, LessonType
from services import repo
from wsp_scraper.db_service import save_subject_to_db
from wsp_scraper.schemas import ParsedBlock, SubjectEntry

DATA_DIR = Path(__file__).parent.parent / "data"
KNOWLEDGE_FILE = DATA_DIR / "seed_knowledge.json"
SCHEDULE_FILE = DATA_DIR / "seed_schedule.json"

_DAY_MAP = {d.value: d for d in DayOfWeek}
_TYPE_MAP = {lt.value: lt for lt in LessonType}


async def run_migrations() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        for stmt in [
            "ALTER TABLE knowledge_base ADD COLUMN IF NOT EXISTS title VARCHAR(255)",
            "ALTER TABLE knowledge_base ADD COLUMN IF NOT EXISTS keywords TEXT[]",
            "ALTER TABLE knowledge_base ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ",
        ]:
            await conn.execute(text(stmt))
    print("Database schema ready.")


async def seed_knowledge() -> None:
    if not KNOWLEDGE_FILE.exists():
        print(f"  {KNOWLEDGE_FILE} not found — skipping knowledge seed.")
        return

    entries = json.loads(KNOWLEDGE_FILE.read_text(encoding="utf-8"))
    print(f"Seeding {len(entries)} knowledge entries (embeddings will be computed)...")

    inserted = 0
    async with async_session() as session:
        for entry in entries:
            content = entry.get("content", "").strip()
            if not content:
                continue
            # add_knowledge is idempotent: skips exact content duplicates
            await repo.add_knowledge(
                session,
                content=content,
                category=entry.get("category"),
                title=entry.get("title"),
                keywords=entry.get("keywords") or None,
            )
            inserted += 1

    print(f"  {inserted} entries processed (duplicates silently skipped by repo).")


async def seed_schedule() -> None:
    if not SCHEDULE_FILE.exists():
        print(f"  {SCHEDULE_FILE} not found — skipping schedule seed.")
        return

    subjects = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
    print(f"Seeding {len(subjects)} subjects...")

    total_events = 0
    async with async_session() as session:
        for subj_data in subjects:
            blocks: list[ParsedBlock] = []
            for ev in subj_data.get("events", []):
                start_h, start_m = map(int, ev["start_time"].split(":"))
                end_h, end_m = map(int, ev["end_time"].split(":"))

                block = ParsedBlock(
                    subject_code=subj_data["code"],
                    instructor=ev["instructor"],
                    room=ev["room"],
                    day_of_week=_DAY_MAP.get(ev["day_of_week"]),
                    start_time=dt_time(start_h, start_m),
                    end_time=dt_time(end_h, end_m),
                    lesson_type=ev["lesson_type"],
                    current_students=ev.get("student_count_current"),
                    max_students=ev.get("student_count_max"),
                    is_valid=True,
                )
                blocks.append(block)
                total_events += 1

            entry = SubjectEntry(
                code=subj_data["code"],
                name_ru=subj_data.get("name_ru") or "",
                name_en=subj_data.get("name_en") or "",
                name_kz=subj_data.get("name_kz") or "",
                department=subj_data.get("department") or "",
                credits=subj_data.get("credits"),
                formula=subj_data.get("formula") or "",
                year=subj_data.get("year"),
                period=subj_data.get("period"),
                blocks=blocks,
            )
            await save_subject_to_db(session, entry)

        await session.commit()

    print(f"  {len(subjects)} subjects, {total_events} events seeded.")


async def main() -> None:
    await run_migrations()
    await seed_knowledge()
    await seed_schedule()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
