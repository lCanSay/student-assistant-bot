import os
import sys
from datetime import time
from types import SimpleNamespace

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.wsp_models import DayOfWeek, LessonType
from utils.formatters import format_free_rooms, format_schedule


def test_format_schedule_empty_html():
    result = format_schedule([], "Тест")
    assert result == "<b>Расписание: Тест</b>\n\nНичего не найдено."


def test_format_schedule_empty_plain():
    result = format_schedule([], "Тест", as_html=False)
    assert result == "Расписание: Тест\n\nНичего не найдено."


def test_format_schedule_groups_and_formats_by_day():
    event_mon = SimpleNamespace(
        day_of_week=DayOfWeek.MONDAY,
        start_time=time(9, 0),
        end_time=time(10, 30),
        lesson_type=LessonType.LECTURE,
        room=SimpleNamespace(number="101"),
        instructor=SimpleNamespace(full_name="Иванов И.И."),
        subject=SimpleNamespace(code="MATH101", name_en="Mathematics", name_ru=None),
    )
    event_tue = SimpleNamespace(
        day_of_week=DayOfWeek.TUESDAY,
        start_time=time(11, 0),
        end_time=time(12, 30),
        lesson_type=LessonType.PRACTICE,
        room=SimpleNamespace(number="202"),
        instructor=SimpleNamespace(full_name="Петров П.П."),
        subject=SimpleNamespace(code="PHYS101", name_en=None, name_ru="Физика"),
    )

    result = format_schedule([event_tue, event_mon], "Моя группа")

    assert "<b>Расписание: Моя группа</b>" in result
    assert "<b>Понедельник</b>" in result
    assert "<b>Вторник</b>" in result
    assert "▪️ 09:00 - 10:30 | Л | Каб. 101" in result
    assert "<i>Mathematics (MATH101) — Иванов И.И.</i>" in result
    assert "<i>Физика (PHYS101) — Петров П.П.</i>" in result


def test_format_schedule_missing_related_fields_uses_placeholders():
    event = SimpleNamespace(
        day_of_week=DayOfWeek.WEDNESDAY,
        start_time=time(14, 0),
        end_time=time(15, 30),
        lesson_type=LessonType.LAB,
        room=None,
        instructor=None,
        subject=None,
    )

    result = format_schedule([event], "Без данных")

    assert "Каб. —" in result
    assert "—" in result


def test_format_free_rooms_groups_properly():
    raw_rooms = [
        "332б",
        "726",
        "26",
        "SEZPIT 100",
        "Новая аудитория",
    ]

    result = format_free_rooms(raw_rooms)

    assert "<b>2-й этаж:</b> 726" in result
    assert "<b>3-й этаж:</b> 332б" in result
    assert "<b>0-й этаж:</b> 26" in result
    assert "<b>Другие:</b> Новая аудитория" in result
    assert "SEZPIT 100" not in result


def test_format_free_rooms_returns_empty_string_when_no_rooms():
    assert format_free_rooms([]) == ""
