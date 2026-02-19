from __future__ import annotations
import re
import logging
from datetime import time as dt_time
from typing import Optional
from core.wsp_models import DayOfWeek
from .schemas import ParsedBlock

log = logging.getLogger("scraper.parser")

_CAPACITY_RE = re.compile(r"\((?P<current>\d+)(?:/(?P<max>\d+))?\)\s*$")
_PIVOT_RE = re.compile(r"\s+(Лаб|Л|П)\s+")


def parse_block_text(raw_text: str, known_subject_name: str) -> dict:
    """
    Anchor-based parser for schedule block inner text.
    Returns a dict with keys: instructor, lesson_type, room, current, max.
    """
    result: dict = {
        "instructor": "",
        "lesson_type": "",
        "room": "",
        "current": None,
        "max": None,
    }

    remaining = raw_text.strip()

    cap_match = _CAPACITY_RE.search(remaining)
    if cap_match:
        result["current"] = int(cap_match.group("current"))
        max_val = cap_match.group("max")
        result["max"] = int(max_val) if max_val else None
        remaining = remaining[: cap_match.start()].strip()
    else:
        log.debug("No capacity found in: %s", raw_text)

    if known_subject_name and remaining.startswith(known_subject_name):
        remaining = remaining[len(known_subject_name) :].strip()

    pivot_match = _PIVOT_RE.search(remaining)
    if pivot_match:
        lesson_token = pivot_match.group(1)
        result["lesson_type"] = lesson_token

        result["instructor"] = remaining[: pivot_match.start()].strip()
        result["room"] = remaining[pivot_match.end() :].strip()
    else:
        result["instructor"] = remaining.strip()
        log.warning("No lesson-type pivot found in block: '%s'", raw_text)

    return result


def validate_block(block: ParsedBlock) -> bool:
    """
    Apply validation rules. Sets block.is_valid and block.drop_reason.
    """
    if block.day_of_week is not None and block.day_of_week.value == "Sun":
        block.is_valid = False
        block.drop_reason = "Rule 1: Sunday ban"
        log.info("Dropped block due to Rule 1 (Sunday): %s", block.raw_text[:80])
        return False

    cur = block.current_students
    mx = block.max_students

    if mx is not None:
        if mx < 9 or (cur is not None and cur < 7):
            block.is_valid = False
            block.drop_reason = f"Rule 2: capacity {cur}/{mx}"
            log.info("Dropped block due to Rule 2: %d/%d capacity — %s", cur if cur is not None else 0, mx, block.raw_text[:80])
            return False
    elif cur is not None:
        if cur < 7:
            block.is_valid = False
            block.drop_reason = f"Rule 2: capacity ({cur})"
            log.info("Dropped block due to Rule 2: (%d) capacity — %s", cur, block.raw_text[:80])
            return False

    return True


DAY_LABEL_MAP: dict[str, DayOfWeek] = {
    "mon": DayOfWeek.MONDAY,
    "tue": DayOfWeek.TUESDAY,
    "wed": DayOfWeek.WEDNESDAY,
    "thu": DayOfWeek.THURSDAY,
    "fri": DayOfWeek.FRIDAY,
    "sat": DayOfWeek.SATURDAY,
    "\u0434\u04af\u0439": DayOfWeek.MONDAY,
    "\u0441\u0435\u0439": DayOfWeek.TUESDAY,
    "\u0441\u04d9\u0440": DayOfWeek.WEDNESDAY,
    "\u0431\u0435\u0439": DayOfWeek.THURSDAY,
    "\u0436\u04b1\u043c": DayOfWeek.FRIDAY,
    "\u0441\u0435\u043d": DayOfWeek.SATURDAY,
    "\u043f\u043d": DayOfWeek.MONDAY,
    "\u0432\u0442": DayOfWeek.TUESDAY,
    "\u0441\u0440": DayOfWeek.WEDNESDAY,
    "\u0447\u0442": DayOfWeek.THURSDAY,
    "\u043f\u0442": DayOfWeek.FRIDAY,
    "\u0441\u0431": DayOfWeek.SATURDAY,
}

FIRST_SLOT_HOUR = 8   
FIRST_SLOT_MIN = 0
SCHEDULE_TIME_ORIGIN_TOP = 41
SCHEDULE_PX_PER_HOUR = 40

def derive_day_from_left(left_px: float, column_boundaries: list[tuple[float, float, DayOfWeek]]) -> Optional[DayOfWeek]:
    for lo, hi, day in column_boundaries:
        if lo <= left_px < hi:
            return day
    return None


def derive_times_from_css(
    top_px: float,
    height_px: float,
    origin_top: float,
    px_per_min: float,
) -> tuple[Optional[dt_time], Optional[dt_time]]:
    if px_per_min <= 0:
        return None, None

    start_minutes = ((top_px - origin_top) / px_per_min) + FIRST_SLOT_HOUR * 60 + FIRST_SLOT_MIN
    duration_minutes = height_px / px_per_min

    start_h = int(start_minutes // 60)
    start_m = int(start_minutes % 60)
    end_minutes = start_minutes + duration_minutes
    end_h = int(end_minutes // 60)
    end_m = int(end_minutes % 60)

    try:
        return dt_time(start_h, start_m), dt_time(end_h, end_m)
    except ValueError:
        return None, None
