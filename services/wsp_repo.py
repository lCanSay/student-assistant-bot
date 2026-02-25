from sqlalchemy import select, case, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

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


async def get_currently_free_rooms(session: AsyncSession) -> list[str]:
    """
    Find rooms that are currently free.
    If during a break (>= 50 mins), looks ahead 15 mins to find rooms free for the NEXT class block.
    """
    tz = ZoneInfo("Asia/Almaty")
    now = datetime.now(tz)
    
    # Heuristic to fix the X:50 - Y:00 break gap:
    if now.minute >= 50:
        target_time = now + timedelta(minutes=15)
    else:
        target_time = now
        
    current_day = target_time.strftime("%A").upper() # Outputs 'MONDAY', 'TUESDAY', etc.
    check_time = target_time.time()

    # Query rooms that DO NOT have an event overlapping with check_time
    stmt = (
        select(Room.number)
        .where(
            ~Room.events.any(
                and_(
                    ScheduleEvent.day_of_week == current_day,
                    ScheduleEvent.start_time <= check_time,
                    ScheduleEvent.end_time >= check_time
                )
            )
        )
        .order_by(Room.number)
    )
    result = await session.execute(stmt)
    return result.scalars().all()
