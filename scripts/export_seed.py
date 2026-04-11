"""
export_seed.py — dump current DB content to seed JSON files.

Run once from the project root (with DB running):
    python scripts/export_seed.py

Produces:
    data/seed_knowledge.json   — knowledge_base entries (no embeddings)
    data/seed_schedule.json    — subjects + schedule events (denormalized)
"""

import asyncio
import json
import sys
from pathlib import Path

# Allow imports from the project root regardless of where the script is called from
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

import core.models        # noqa: F401 — registers KnowledgeItem with Base
import core.wsp_models    # noqa: F401 — registers schedule models with Base
from core.database import async_session
from core.models import KnowledgeItem
from core.wsp_models import Subject, ScheduleEvent

DATA_DIR = Path(__file__).parent.parent / "data"


async def export_knowledge() -> list[dict]:
    async with async_session() as session:
        result = await session.execute(
            select(KnowledgeItem).order_by(KnowledgeItem.id)
        )
        items = result.scalars().all()

    rows = []
    for item in items:
        rows.append({
            "title": item.title,
            "category": item.category,
            "keywords": item.keywords or [],
            "content": item.content,
        })
    return rows


async def export_schedule() -> list[dict]:
    async with async_session() as session:
        result = await session.execute(
            select(Subject).order_by(Subject.code)
        )
        subjects = result.scalars().all()

        data = []
        for subj in subjects:
            events_result = await session.execute(
                select(ScheduleEvent).where(ScheduleEvent.subject_id == subj.id)
            )
            events = events_result.scalars().all()

            if not events:
                continue

            event_list = []
            for ev in events:
                await session.refresh(ev, ["instructor", "room"])
                event_list.append({
                    "instructor": ev.instructor.full_name,
                    "room": ev.room.number,
                    "day_of_week": ev.day_of_week.value,
                    "start_time": ev.start_time.strftime("%H:%M"),
                    "end_time": ev.end_time.strftime("%H:%M"),
                    "lesson_type": ev.lesson_type.value,
                    "student_count_current": ev.student_count_current,
                    "student_count_max": ev.student_count_max,
                    "notes": ev.notes,
                })

            data.append({
                "code": subj.code,
                "name_ru": subj.name_ru,
                "name_en": subj.name_en,
                "name_kz": subj.name_kz,
                "department": subj.department,
                "credits": subj.credits,
                "formula": subj.formula,
                "year": subj.year,
                "period": subj.period,
                "events": event_list,
            })

    return data


async def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)

    print("Exporting knowledge_base...")
    knowledge = await export_knowledge()
    knowledge_path = DATA_DIR / "seed_knowledge.json"
    knowledge_path.write_text(
        json.dumps(knowledge, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  {len(knowledge)} entries → {knowledge_path}")

    print("Exporting schedule...")
    schedule = await export_schedule()
    schedule_path = DATA_DIR / "seed_schedule.json"
    schedule_path.write_text(
        json.dumps(schedule, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    total_events = sum(len(s["events"]) for s in schedule)
    print(f"  {len(schedule)} subjects, {total_events} events → {schedule_path}")

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
