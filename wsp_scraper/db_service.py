from __future__ import annotations
import logging
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from core.wsp_models import (
    Instructor,
    LessonType,
    Room,
    ScheduleEvent,
    Subject,
)
from .schemas import SubjectEntry

log = logging.getLogger("scraper.db_service")

LESSON_TYPE_MAP: dict[str, LessonType] = {
    "Л":   LessonType.LECTURE,
    "П":   LessonType.PRACTICE,
    "Лаб": LessonType.LAB,
    "Лб":  LessonType.LAB,
}


async def get_or_create_instructor(session: AsyncSession, name: str) -> Instructor:
    result = await session.execute(
        select(Instructor).where(Instructor.full_name == name)
    )
    inst = result.scalar_one_or_none()
    if inst is None:
        inst = Instructor(full_name=name)
        session.add(inst)
        await session.flush()
    return inst


async def get_or_create_room(session: AsyncSession, number: str) -> Room:
    result = await session.execute(
        select(Room).where(Room.number == number)
    )
    room = result.scalar_one_or_none()
    if room is None:
        room = Room(number=number)
        session.add(room)
        await session.flush()
    return room


async def save_subject_to_db(session: AsyncSession, entry: SubjectEntry) -> None:
    base_code = "".join(ch for ch in entry.code if ch.isalnum())
    entry.code = base_code

    new_valid_count = sum(1 for b in entry.blocks if b.is_valid)
    result = await session.execute(
        select(Subject).where(Subject.code == base_code)
    )
    subj = result.scalar_one_or_none()

    if subj is not None:
        existing_count = (await session.execute(
            select(func.count()).where(ScheduleEvent.subject_id == subj.id)
        )).scalar() or 0

        if new_valid_count > existing_count:
            log.info("Replacing schedule for %s (New: %d > Old: %d)", base_code, new_valid_count, existing_count)
            await session.execute(delete(ScheduleEvent).where(ScheduleEvent.subject_id == subj.id))
            
            if entry.name_en: subj.name_en = entry.name_en
            if entry.name_ru: subj.name_ru = entry.name_ru
            if entry.name_kz: subj.name_kz = entry.name_kz
            if entry.department: subj.department = entry.department
            if entry.credits is not None: subj.credits = entry.credits
            if entry.formula: subj.formula = entry.formula
            if entry.year is not None: subj.year = entry.year
            if entry.period is not None: subj.period = entry.period
        else:
            log.info("Keeping existing schedule for %s (New: %d <= Old: %d)", base_code, new_valid_count, existing_count)
            return
    else:
        subj = Subject(
            code=base_code,
            name_en=entry.name_en or None,
            name_ru=entry.name_ru or None,
            name_kz=entry.name_kz or None,
            department=entry.department or None,
            credits=entry.credits,
            formula=entry.formula or None,
            year=entry.year,
            period=entry.period,
        )
        session.add(subj)
        await session.flush()

    seen_keys: set[tuple] = set()
    inserted_count = 0
    
    for block in entry.blocks:
        if not block.is_valid:
            continue

        if not block.instructor or not block.room:
            continue

        if block.day_of_week is None or block.start_time is None:
            continue

        lt = LESSON_TYPE_MAP.get(block.lesson_type)
        if lt is None:
            continue

        dedup_key = (block.day_of_week, block.start_time, lt, block.room)
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        instructor = await get_or_create_instructor(session, block.instructor)
        room = await get_or_create_room(session, block.room)

        event = ScheduleEvent(
            subject_id=subj.id,
            instructor_id=instructor.id,
            room_id=room.id,
            day_of_week=block.day_of_week,
            start_time=block.start_time,
            end_time=block.end_time,
            lesson_type=lt,
            group_info=f"{block.current_students}/{block.max_students}"
            if block.max_students is not None
            else str(block.current_students) if block.current_students is not None else None,
            student_count_current=block.current_students,
            student_count_max=block.max_students,
        )
        session.add(event)
        inserted_count += 1

    await session.flush()
    if inserted_count > 0:
        log.info("Saved subject %s to DB (id=%d, events=%d)", base_code, subj.id, inserted_count)
