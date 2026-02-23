from sqlalchemy import select, case, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.wsp_models import ScheduleEvent, Subject, Instructor, Room, DayOfWeek

# Reusable CASE expression to sort DayOfWeek enum chronologically
_DAY_ORDER = case(
    (ScheduleEvent.day_of_week == DayOfWeek.MONDAY, 1),
    (ScheduleEvent.day_of_week == DayOfWeek.TUESDAY, 2),
    (ScheduleEvent.day_of_week == DayOfWeek.WEDNESDAY, 3),
    (ScheduleEvent.day_of_week == DayOfWeek.THURSDAY, 4),
    (ScheduleEvent.day_of_week == DayOfWeek.FRIDAY, 5),
    (ScheduleEvent.day_of_week == DayOfWeek.SATURDAY, 6),
    else_=7,
)


async def search_schedule_by_instructor(
    session: AsyncSession, name_query: str
) -> list[ScheduleEvent]:
    """Search events by instructor name."""
    stmt = (
        select(ScheduleEvent)
        .join(ScheduleEvent.instructor)
        .where(Instructor.full_name.ilike(f"%{name_query}%"))
        .options(
            selectinload(ScheduleEvent.subject),
            selectinload(ScheduleEvent.instructor),
            selectinload(ScheduleEvent.room),
        )
        .order_by(_DAY_ORDER, ScheduleEvent.start_time)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def search_schedule_by_room(
    session: AsyncSession, room_query: str
) -> list[ScheduleEvent]:
    """Search events by room number."""
    stmt = (
        select(ScheduleEvent)
        .join(ScheduleEvent.room)
        .where(Room.number.ilike(f"%{room_query}%"))
        .options(
            selectinload(ScheduleEvent.subject),
            selectinload(ScheduleEvent.instructor),
            selectinload(ScheduleEvent.room),
        )
        .order_by(_DAY_ORDER, ScheduleEvent.start_time)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def search_schedule_by_subject(
    session: AsyncSession, subject_query: str
) -> list[ScheduleEvent]:
    """Search events by subject code or name."""
    pattern = f"%{subject_query}%"
    stmt = (
        select(ScheduleEvent)
        .join(ScheduleEvent.subject)
        .where(
            or_(
                Subject.code.ilike(pattern),
                Subject.name_en.ilike(pattern),
                Subject.name_ru.ilike(pattern),
            )
        )
        .options(
            selectinload(ScheduleEvent.subject),
            selectinload(ScheduleEvent.instructor),
            selectinload(ScheduleEvent.room),
        )
        .order_by(_DAY_ORDER, ScheduleEvent.start_time)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
