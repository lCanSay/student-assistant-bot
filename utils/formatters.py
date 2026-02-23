from __future__ import annotations

from collections import defaultdict

from core.wsp_models import ScheduleEvent, DayOfWeek

# Human-readable day names (Russian)
_DAY_NAMES: dict[DayOfWeek, str] = {
    DayOfWeek.MONDAY: "Понедельник",
    DayOfWeek.TUESDAY: "Вторник",
    DayOfWeek.WEDNESDAY: "Среда",
    DayOfWeek.THURSDAY: "Четверг",
    DayOfWeek.FRIDAY: "Пятница",
    DayOfWeek.SATURDAY: "Суббота",
}

# Ordering for chronological grouping
_DAY_ORDER: dict[DayOfWeek, int] = {
    DayOfWeek.MONDAY: 1,
    DayOfWeek.TUESDAY: 2,
    DayOfWeek.WEDNESDAY: 3,
    DayOfWeek.THURSDAY: 4,
    DayOfWeek.FRIDAY: 5,
    DayOfWeek.SATURDAY: 6,
}

TELEGRAM_MAX_LEN = 4096


def format_schedule(events: list[ScheduleEvent], title: str, *, as_html: bool = True) -> str:
    """Format a list of ScheduleEvents grouped by day.

    Args:
        as_html: If True, wrap with <b>/<i> tags. If False, return plain text.
    """
    if not events:
        if as_html:
            return f"<b>Расписание: {title}</b>\n\nНичего не найдено."
        return f"Расписание: {title}\n\nНичего не найдено."

    # Group by day
    by_day: dict[DayOfWeek, list[ScheduleEvent]] = defaultdict(list)
    for ev in events:
        by_day[ev.day_of_week].append(ev)

    if as_html:
        lines: list[str] = [f"<b>Расписание: {title}</b>"]
    else:
        lines = [f"Расписание: {title}"]

    sorted_days = sorted(by_day.keys(), key=lambda d: _DAY_ORDER.get(d, 99))

    for day in sorted_days:
        day_events = sorted(by_day[day], key=lambda e: e.start_time)
        lines.append("")

        day_name = _DAY_NAMES.get(day, day.value)
        lines.append(f"<b>{day_name}</b>" if as_html else day_name)

        for ev in day_events:
            t_start = ev.start_time.strftime("%H:%M")
            t_end = ev.end_time.strftime("%H:%M")
            lesson = ev.lesson_type.value
            room = ev.room.number if ev.room else "—"
            instructor = ev.instructor.full_name if ev.instructor else "—"
            subj_code = ev.subject.code if ev.subject else ""
            subj_name = (ev.subject.name_en or ev.subject.name_ru or "") if ev.subject else "—"

            lines.append(f"▪️ {t_start} - {t_end} | {lesson} | Каб. {room}")
            detail = f"{subj_name} ({subj_code}) — {instructor}"
            lines.append(f"<i>{detail}</i>" if as_html else detail)

    return "\n".join(lines)
