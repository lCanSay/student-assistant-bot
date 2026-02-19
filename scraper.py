"""
WSP Schedule Scraper
====================
Async Playwright scraper for wsp.kbtu.kz/SubjectSchedule (Vaadin-based).
Extracts schedule data and inserts into PostgreSQL via SQLAlchemy 2.0.

Usage:
    python scraper.py
"""
from __future__ import annotations

import asyncio
import logging
import re
import sys
import os
from dataclasses import dataclass, field
from datetime import time as dt_time
from typing import Optional

from playwright.async_api import async_playwright, Page, Locator

# ── Project imports ──────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

from config import DATABASE_URL
from core.database import engine, Base, async_session
from core.wsp_models import (
    DayOfWeek,
    Instructor,
    LessonType,
    Room,
    ScheduleEvent,
    Subject,
)
from sqlalchemy import select, text, func, delete

# ── Constants ────────────────────────────────────────────────────
WSP_LOGIN = os.getenv("WSP_LOGIN")
WSP_PASSWORD = os.getenv("WSP_PASSWORD")
TARGET_URL = "https://wsp.kbtu.kz/SubjectSchedule"

# Vaadin schedule grid: time slots start at a known pixel offset.
# These are calibrated from the recon phase.  Adjust if the site changes.
TIME_SLOT_ORIGIN_TOP = 0       # px, will be auto-detected per modal
TIME_SLOT_PX_PER_MIN = 1.0    # recalibrated at runtime from known anchors

# Column positions in the modal map to days.
# Vaadin uses absolute left offsets; we map ranges to DayOfWeek.
DAY_COLUMN_MAP: dict[int, DayOfWeek] = {}  # populated dynamically

# Lesson type pivot tokens (surrounded by spaces)
LESSON_TYPE_PIVOTS = [" Лаб ", " Лб ", " Л ", " П "]

# Map raw pivot tokens → canonical LessonType enum
LESSON_TYPE_MAP: dict[str, LessonType] = {
    "Л":   LessonType.LECTURE,
    "П":   LessonType.PRACTICE,
    "Лаб": LessonType.LAB,
    "Лб":  LessonType.LAB,  # normalize short form → LAB
}

# ── Logging ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("scraper")


# ═══════════════════════════════════════════════════════════════
#  DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════
@dataclass
class ParsedBlock:
    """Represents one schedule cell extracted from the modal."""

    subject_code: str = ""
    subject_name: str = ""
    instructor: str = ""
    lesson_type: str = ""           # raw token, e.g. "Л"
    room: str = ""
    current_students: Optional[int] = None
    max_students: Optional[int] = None
    day_of_week: Optional[DayOfWeek] = None
    start_time: Optional[dt_time] = None
    end_time: Optional[dt_time] = None
    is_valid: bool = True
    drop_reason: str = ""
    raw_text: str = ""


@dataclass
class SubjectEntry:
    """Subject metadata collected from the grid table."""

    code: str
    name_en: str = ""
    name_ru: str = ""
    name_kz: str = ""
    department: str = ""
    credits: Optional[float] = None
    formula: str = ""
    year: Optional[str] = None
    period: Optional[str] = None
    blocks: list[ParsedBlock] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  PARSING
# ═══════════════════════════════════════════════════════════════
# Regex: capacity anchored to end of string ── (18/25) or (25)
_CAPACITY_RE = re.compile(r"\((?P<current>\d+)(?:/(?P<max>\d+))?\)\s*$")

# Regex: lesson type pivot (space-delimited)
_PIVOT_RE = re.compile(r"\s+(Лаб|Лб|Л|П)\s+")


def parse_block_text(raw_text: str, known_subject_name: str) -> dict:
    """
    Anchor-based parser for schedule block inner text.

    Steps:
    1. End-anchor: extract capacity "(current/max)" or "(current)" from the END.
    2. Start-anchor: strip known_subject_name from the LEFT.
    3. Center-pivot: find the lesson-type token (Л / П / Лаб / Лб) surrounded by spaces.
    4. Split: left of pivot = instructor, right of pivot = room.

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

    # ── Step 1: End anchor — capacity ────────────────────────
    cap_match = _CAPACITY_RE.search(remaining)
    if cap_match:
        result["current"] = int(cap_match.group("current"))
        max_val = cap_match.group("max")
        result["max"] = int(max_val) if max_val else None
        remaining = remaining[: cap_match.start()].strip()
    else:
        log.debug("No capacity found in: %s", raw_text)

    # ── Step 2: Start anchor — subject name ──────────────────
    if known_subject_name and remaining.startswith(known_subject_name):
        remaining = remaining[len(known_subject_name) :].strip()

    # ── Step 3: Center pivot — lesson type ───────────────────
    pivot_match = _PIVOT_RE.search(remaining)
    if pivot_match:
        lesson_token = pivot_match.group(1)
        result["lesson_type"] = lesson_token

        # ── Step 4: Split around pivot ───────────────────────
        result["instructor"] = remaining[: pivot_match.start()].strip()
        result["room"] = remaining[pivot_match.end() :].strip()
    else:
        # Fallback: treat everything as instructor if no pivot found
        result["instructor"] = remaining.strip()
        log.warning("No lesson-type pivot found in block: '%s'", raw_text)

    return result


# ═══════════════════════════════════════════════════════════════
#  VALIDATION
# ═══════════════════════════════════════════════════════════════
def validate_block(block: ParsedBlock) -> bool:
    """
    Apply validation rules.  Sets block.is_valid and block.drop_reason.

    Level 1 — Block-level:
        Rule 1 (Sunday Ban): drop if day_of_week is Sunday.
        Rule 2 (Thresholds):
            current/max → drop if max < 11 OR current < 7.
            current only → drop if current < 7.

    Returns True if valid, False otherwise.
    """
    # Rule 1: Sunday ban
    if block.day_of_week is not None and block.day_of_week.value == "Sun":
        block.is_valid = False
        block.drop_reason = "Rule 1: Sunday ban"
        log.info(
            "Dropped block due to Rule 1 (Sunday): %s", block.raw_text[:80]
        )
        return False

    # Rule 2: Capacity thresholds
    cur = block.current_students
    mx = block.max_students

    if mx is not None:
        # Format: (current/max)
        if mx < 9 or (cur is not None and cur < 7):
            block.is_valid = False
            block.drop_reason = f"Rule 2: capacity {cur}/{mx}"
            log.info(
                "Dropped block due to Rule 2: %d/%d capacity — %s",
                cur if cur is not None else 0,
                mx,
                block.raw_text[:80],
            )
            return False
    elif cur is not None:
        # Format: (current) only
        if cur < 7:
            block.is_valid = False
            block.drop_reason = f"Rule 2: capacity ({cur})"
            log.info(
                "Dropped block due to Rule 2: (%d) capacity — %s",
                cur,
                block.raw_text[:80],
            )
            return False

    return True





# ═══════════════════════════════════════════════════════════════
#  TIME / DAY DERIVATION FROM CSS
# ═══════════════════════════════════════════════════════════════
# The schedule modal uses absolute CSS positioning:
#   - `left` → day column
#   - `top`  → start time
#   - `height` → duration

# Known time anchors (from Vaadin schedule widget):
# These map pixel top-offsets to actual times.
# Calibrated empirically from the ScheduleView page.
# Time labels: top:41px = 08:00, top:81px = 09:00 → 40px per hour.
FIRST_SLOT_HOUR = 8   # 08:00 is the first slot
FIRST_SLOT_MIN = 0
SCHEDULE_TIME_ORIGIN_TOP = 41   # px where 08:00 starts
SCHEDULE_PX_PER_HOUR = 40       # 40px = 1 hour


def derive_day_from_left(left_px: float, column_boundaries: list[tuple[float, float, DayOfWeek]]) -> Optional[DayOfWeek]:
    """Map a CSS left offset to a DayOfWeek using detected column boundaries."""
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
    """Convert CSS top/height to start_time/end_time."""
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


# ═══════════════════════════════════════════════════════════════
#  PLAYWRIGHT NAVIGATION
# ═══════════════════════════════════════════════════════════════
async def login(page: Page) -> None:
    """Log in to wsp.kbtu.kz via the Vaadin login view (in English)."""
    log.info("Navigating to login page...")
    await page.goto("https://wsp.kbtu.kz", wait_until="networkidle", timeout=30_000)
    await page.wait_for_timeout(3000)

    # Step 1: Switch UI to English
    gb_flag = page.locator("img[src*='gb.png']")
    if await gb_flag.count() > 0:
        await gb_flag.first.click()
        log.info("Switched UI to English")
        await page.wait_for_timeout(5000)
        await page.wait_for_load_state("networkidle", timeout=15_000)

    # Step 2: Click the login icon to open the LoginView form
    login_icon = page.locator("img[src*='login_24']")
    await login_icon.wait_for(state="visible", timeout=10_000)
    await login_icon.click()
    log.info("Clicked login icon \u2014 waiting for login form...")
    await page.wait_for_timeout(3000)

    # Step 3: Fill username (Vaadin ComboBox / filterselect input)
    username_field = page.locator("input.v-filterselect-input")
    await username_field.wait_for(state="visible", timeout=10_000)
    await username_field.click()
    await username_field.fill(WSP_LOGIN)

    # Step 4: Fill password
    password_field = page.locator("input[type='password']")
    await password_field.wait_for(state="visible", timeout=10_000)
    await password_field.fill(WSP_PASSWORD)

    # Step 5: Click the login button ("Log in" in English, fallback to others)
    submit = page.locator(
        ".v-button:has-text('Log in'), .v-button:has-text('\u041a\u0456\u0440\u0443'), "
        ".v-button:has-text('\u0412\u043e\u0439\u0442\u0438'), .v-button:has-text('Login')"
    )
    submit_count = await submit.count()
    if submit_count > 0:
        await submit.first.click()
    else:
        log.warning("No login button found \u2014 pressing Enter")
        await password_field.press("Enter")

    await page.wait_for_timeout(3000)
    await page.wait_for_load_state("networkidle", timeout=15_000)
    log.info("Login complete \u2014 current URL: %s", page.url)


async def navigate_to_schedule(page: Page) -> None:
    """Navigate to the Subject Schedule page."""
    log.info("Navigating to %s ...", TARGET_URL)
    await page.goto(TARGET_URL, wait_until="networkidle", timeout=30_000)
    await page.wait_for_timeout(3000)
    log.info("Schedule page loaded — URL: %s", page.url)


# ─────────────────────────────────────────────────────────────
#  PHASE 1 — Collect all subject codes from the virtual grid
# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
#  PHASE 1 — Single-Pass Helpers
# ─────────────────────────────────────────────────────────────

async def extract_row_metadata(cells: list[Locator], col_names: list[str]) -> dict:
    """Extract metadata from a row's cells."""
    row_data: dict = {}
    if len(cells) > 0:
        first_text = await cells[0].inner_text()
        log.debug("Row cells: %d, first: %r", len(cells), first_text)
    
    for i, col in enumerate(col_names):
        if i < len(cells):
            text = (await cells[i].inner_text()).strip()
            row_data[col] = text
            if col in ("year", "period"):
                 log.debug("  %s: %r", col, text)
        else:
            row_data[col] = ""
    return row_data


async def find_next_unprocessed_row(
    page: Page, processed_codes: set[str], col_names: list[str]
) -> tuple[Optional[Locator], Optional[dict]]:
    """
    Scan visible rows for the first one whose code hasn't been processed.
    Returns (row_locator, subject_data_dict) or (None, None).
    """
    rows = await page.locator(".v-table-body tr").all()
    
    for row in rows:
        cells = await row.locator("td").all()
        if len(cells) < 2:
            continue

        # Code is in the first cell - strip spaces for consistent keys
        raw_code = (await cells[0].inner_text()).strip()
        code_key = raw_code.replace(" ", "")
        
        if not code_key:
            continue
            
        if code_key in processed_codes:
            continue
            
        # Found a new one!
        subject_data = await extract_row_metadata(cells, col_names)
        # Ensure the dict has the space-stripped code too, if helpful, 
        # but we usually keep the original format for display/logic unless standardized.
        # Let's verify: SubjectEntry expects 'code'.
        # We can standardize "code" here or later. The key in processed_codes is stripped.
        subject_data["code"] = raw_code 
        
        return row, subject_data
        
    return None, None



# ─────────────────────────────────────────────────────────────
#  PHASE 2 — Targeted scraping per subject
# ─────────────────────────────────────────────────────────────
# ── Day label → DayOfWeek mapping (English UI) ──────────────
DAY_LABEL_MAP: dict[str, DayOfWeek] = {
    "mon": DayOfWeek.MONDAY,
    "tue": DayOfWeek.TUESDAY,
    "wed": DayOfWeek.WEDNESDAY,
    "thu": DayOfWeek.THURSDAY,
    "fri": DayOfWeek.FRIDAY,
    "sat": DayOfWeek.SATURDAY,
    # Sunday is intentionally omitted — Rule 1 bans it and DayOfWeek has no SUNDAY.
    # Kazakh/Russian fallbacks
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


async def detect_schedule_layout(
    page: Page,
) -> list[tuple[DayOfWeek, Locator]]:
    """
    Detect day columns in the ScheduleView page.
    Each day is a `v-verticallayout` with class `v-border-left-1-bfbfbf`.
    Inside each column there is a bold `.v-label` with the day abbreviation
    and sibling containers holding `.v-absolutelayout-wrapper-schedule-item`
    elements.

    Returns a list of (DayOfWeek, column_locator) for each day that has items.
    """
    day_columns: list[tuple[DayOfWeek, Locator]] = []

    # Each day column is a v-verticallayout with the border class.
    # (The parent v-slot also has it, so we must only target v-verticallayout.)
    columns = page.locator("div.v-verticallayout[class*='v-border-left-1-bfbfbf']")
    col_count = await columns.count()
    log.info("  Found %d day column containers", col_count)

    for i in range(col_count):
        col = columns.nth(i)

        # Find the day label (bold text) inside this column
        label = col.locator(".v-label.bold")
        lbl_count = await label.count()
        if lbl_count == 0:
            continue

        label_text = (await label.first.inner_text()).strip().lower()
        day = DAY_LABEL_MAP.get(label_text)
        if day is None:
            if label_text:   # skip silently if empty
                log.warning("  Unknown day label: %r — skipping", label_text)
            continue

        # Only include columns that actually contain schedule items
        items = col.locator(".v-absolutelayout-wrapper-schedule-item")
        item_count = await items.count()
        if item_count == 0:
            log.debug("  Day %s: no schedule items — skipping", day.value)
            continue

        day_columns.append((day, col))
        log.info("    Day %s: %d schedule items", day.value, item_count)

    return day_columns


async def scrape_row_schedule(
    page: Page, row_element: Locator, subject_data: dict
) -> SubjectEntry:
    """
    Open the schedule for a given subject row, scrape blocks, then return.
    """
    code = subject_data["code"]
    name = subject_data.get("name_en") or subject_data.get("name_ru", "")

    entry = SubjectEntry(
        code=code,
        name_en=subject_data.get("name_en", ""),
        name_ru=subject_data.get("name_ru", ""),
        name_kz=subject_data.get("name_kz", ""),
        department=subject_data.get("department", ""),
        formula=subject_data.get("formula", ""),
    )

    # Parse numeric fields
    if subject_data.get("year"):
        entry.year = subject_data["year"]
    if subject_data.get("period"):
        entry.period = subject_data["period"]

    # Parse credits
    credits_str = subject_data.get("credits", "")
    if credits_str:
        try:
            entry.credits = float(credits_str)
        except ValueError:
            pass

    log.info("Scraping subject: %s (%s)", code, name)

    # ── Double-click the subject row ─────────────────────────
    # The row locator is passed in directly, so no searching needed.
    await row_element.dblclick()
    await page.wait_for_timeout(5000)
    log.info("  Opened ScheduleView — URL: %s", page.url)

    # ── Verify we're on the ScheduleView ─────────────────────
    if "ScheduleView" not in page.url:
        log.warning("Did not navigate to ScheduleView for %s — skipping", code)
        return entry

    # ── Detect day columns ───────────────────────────────────
    day_columns = await detect_schedule_layout(page)

    if not day_columns:
        log.warning("No day columns detected for %s — trying flat approach", code)
        # Fallback: try to find all schedule items on the page regardless of column
        all_items = page.locator(".v-absolutelayout-wrapper-schedule-item")
        item_count = await all_items.count()
        log.info("  Found %d schedule items (flat, no day info)", item_count)

        for j in range(item_count):
            item_el = all_items.nth(j)
            label_el = item_el.locator(".v-label")
            if await label_el.count() == 0:
                continue
            raw_text = (await label_el.first.inner_text()).strip()
            if not raw_text:
                continue

            parsed = parse_block_text(raw_text, name)
            pb = ParsedBlock(
                subject_code=code,
                subject_name=name,
                instructor=parsed["instructor"],
                lesson_type=parsed["lesson_type"],
                room=parsed["room"],
                current_students=parsed["current"],
                max_students=parsed["max"],
                raw_text=raw_text,
            )
            # Try time from CSS top of the schedule-item
            style = await item_el.get_attribute("style") or ""
            top_m = re.search(r"top:\s*([\d.]+)px", style)
            if top_m:
                slot_index = int(float(top_m.group(1))) // 40
                hour = FIRST_SLOT_HOUR + slot_index
                pb.start_time = dt_time(hour, FIRST_SLOT_MIN)
                pb.end_time = dt_time(hour, 50)

            validate_block(pb)
            entry.blocks.append(pb)
    else:
        # ── Parse schedule items per-day-column ──────────────
        for day, column_loc in day_columns:
            items = column_loc.locator(".v-absolutelayout-wrapper-schedule-item")
            item_count = await items.count()
            log.info("    Day %s: %d schedule items", day.value, item_count)

            for j in range(item_count):
                item_el = items.nth(j)
                label_el = item_el.locator(".v-label")
                if await label_el.count() == 0:
                    continue

                raw_text = (await label_el.first.inner_text()).strip()
                if not raw_text:
                    continue

                parsed = parse_block_text(raw_text, name)
                pb = ParsedBlock(
                    subject_code=code,
                    subject_name=name,
                    instructor=parsed["instructor"],
                    lesson_type=parsed["lesson_type"],
                    room=parsed["room"],
                    current_students=parsed["current"],
                    max_students=parsed["max"],
                    raw_text=raw_text,
                    day_of_week=day,
                )

                # Derive time from the CSS top: Npx of the schedule-item
                # Each slot is 40px tall. top:0 = first slot (08:00)
                style = await item_el.get_attribute("style") or ""
                top_m = re.search(r"top:\s*([\d.]+)px", style)
                if top_m:
                    slot_index = int(float(top_m.group(1))) // 40
                    hour = FIRST_SLOT_HOUR + slot_index
                    pb.start_time = dt_time(hour, FIRST_SLOT_MIN)
                    pb.end_time = dt_time(hour, 50)

                validate_block(pb)
                entry.blocks.append(pb)

    valid_count = sum(1 for b in entry.blocks if b.is_valid)
    log.info(
        "  Subject %s: %d total blocks, %d valid",
        code,
        len(entry.blocks),
        valid_count,
    )

    # ── Navigate back to the subject list ─────────────────────
    back_btn = page.locator("img[src*='arrow_left']")
    if await back_btn.count() > 0:
        await back_btn.first.click()
        await page.wait_for_timeout(3000)
    else:
        await page.go_back()
        await page.wait_for_timeout(3000)

    return entry


# ═══════════════════════════════════════════════════════════════
#  DATABASE INSERTION
# ═══════════════════════════════════════════════════════════════
async def get_or_create_instructor(session, name: str) -> Instructor:
    """Get existing Instructor or create a new one."""
    result = await session.execute(
        select(Instructor).where(Instructor.full_name == name)
    )
    inst = result.scalar_one_or_none()
    if inst is None:
        inst = Instructor(full_name=name)
        session.add(inst)
        await session.flush()
    return inst


async def get_or_create_room(session, number: str) -> Room:
    """Get existing Room or create a new one."""
    result = await session.execute(
        select(Room).where(Room.number == number)
    )
    room = result.scalar_one_or_none()
    if room is None:
        room = Room(number=number)
        session.add(room)
        await session.flush()
    return room


async def save_subject_to_db(session, entry: SubjectEntry) -> None:
    """Upsert a Subject and insert its valid ScheduleEvents with conflict resolution."""
    # Normalize code: remove non-alphanumeric characters (keeps Cyrillic, etc.)
    base_code = "".join(ch for ch in entry.code if ch.isalnum())
    entry.code = base_code  # Update entry for consistency

    # Check validity of new data
    new_valid_count = sum(1 for b in entry.blocks if b.is_valid)

    # Check for existing Subject
    result = await session.execute(
        select(Subject).where(Subject.code == base_code)
    )
    subj = result.scalar_one_or_none()

    if subj is not None:
        # Conflict Resolution: Compare schedule density
        existing_count = (await session.execute(
            select(func.count()).where(ScheduleEvent.subject_id == subj.id)
        )).scalar() or 0

        if new_valid_count > existing_count:
            log.info(
                "Replacing schedule for %s (New: %d events > Old: %d events)",
                base_code, new_valid_count, existing_count
            )
            # Delete old events
            await session.execute(
                delete(ScheduleEvent).where(ScheduleEvent.subject_id == subj.id)
            )
            
            # Update metadata
            if entry.name_en: subj.name_en = entry.name_en
            if entry.name_ru: subj.name_ru = entry.name_ru
            if entry.name_kz: subj.name_kz = entry.name_kz
            if entry.department: subj.department = entry.department
            if entry.credits is not None: subj.credits = entry.credits
            if entry.formula: subj.formula = entry.formula
            if entry.year is not None: subj.year = entry.year
            if entry.period is not None: subj.period = entry.period
        else:
            log.info(
                "Keeping existing schedule for %s (New: %d <= Old: %d)",
                base_code, new_valid_count, existing_count
            )
            return

    else:
        # Create new Subject
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
        await session.flush()  # get ID

    # Insert valid events (deduplicate blocks in-memory first)
    seen_keys: set[tuple] = set()   # (day, start_time, lesson_type_str, room_name)
    inserted_count = 0
    
    for block in entry.blocks:
        if not block.is_valid:
            continue

        # Skip blocks with missing critical data
        if not block.instructor or not block.room:
            continue

        if block.day_of_week is None or block.start_time is None:
            continue

        # Resolve lesson type
        lt = LESSON_TYPE_MAP.get(block.lesson_type)
        if lt is None:
            continue

        # In-memory dedup
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


# ═══════════════════════════════════════════════════════════════
#  MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════
async def main() -> None:
    """Run the full scraping pipeline (Single Pass)."""

    if not WSP_LOGIN or not WSP_PASSWORD:
        log.error("WSP_LOGIN / WSP_PASSWORD not set in .env — aborting.")
        sys.exit(1)

    log.info("=" * 60)
    log.info("WSP Schedule Scraper — Single Pass")
    log.info("=" * 60)

    # ── Ensure database tables exist at the very start ───────
    log.info("Ensuring database tables exist...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_playwright() as pw:
        # Production: headless=True if stable
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1600, "height": 900},
        )
        page = await context.new_page()

        try:
            # ── Step 1: Login ────────────────────────────────
            await login(page)

            # ── Step 2: Navigate to schedule page ────────────
            await navigate_to_schedule(page)

            # ── Setup for Single Pass Loop ───────────────────
            # Column mapping (English mode column order):
            # Code, Name (Ru), Name (Kz), Name (En), Department, Credit, Formula, Year, Period
            col_names = [
                "code", "name_ru", "name_kz", "name_en",
                "department", "credits", "formula", "year", "period",
            ]

            processed_codes: set[str] = set()
            saved_count = 0
            no_new_count = 0
            
            # Temporary safety limit (remove later)
            TEST_LIMIT = 50
            
            # Helper logic:
            # We need to scroll RIGHT to ensure columns 8/9 (Year/Period) are rendered/visible.
            # Vaadin virtual tables sometimes lazy-render columns too.
            scroll_container = page.locator(".v-table-body-wrapper")
            if await scroll_container.count() > 0:
                # Force scroll right
                await scroll_container.first.evaluate("el => el.scrollLeft = 9999")
                await page.wait_for_timeout(1000)
                # Reset scroll left? No, keep it scrolled to read all cells if possible.
                # Actually, if we scroll right, we might lose the first column (Code).
                # Vaadin tables usually float the first column or it might scroll away.
                # Let's check. Use evaluate to scroll just enough or check if it's needed.
                # Instead of hard scroll right, let's just assume we can read all cells 
                # OR capture them carefully. 
                # If cells are missing from DOM, we might need a better strategy. 
                # For now, let's try reading and assume Vaadin keeps enough in DOM or we scroll to read.
                # A safer bet: read columns, and if Year is empty/missing, maybe scroll?
                # Actually, Vaadin tables usually render the full row width in the DOM `tr` 
                # even if clipped by overflow hidden.
                pass 

            async with async_session() as session:
                log.info("Starting single-pass scroll & scrape loop...")
                
                while no_new_count < 10:  # Allow some empty scrolls
                    # 1. Find next unprocessed row
                    row, subj_data = await find_next_unprocessed_row(page, processed_codes, col_names)
                    
                    if row is None:
                        # No new subjects visible → scroll down
                        no_new_count += 1
                        log.debug(f"No new rows found (streak={no_new_count}). Scrolling...")
                        
                        if await scroll_container.count() > 0:
                            await scroll_container.first.evaluate("el => el.scrollTop += 400")
                        else:
                            await page.evaluate("window.scrollBy(0, 400)")
                            
                        await page.wait_for_timeout(800)
                        continue

                    # 2. Process the row
                    no_new_count = 0 # Reset streak
                    raw_code = subj_data["code"]
                    clean_key = raw_code.strip().replace(" ", "")
                    
                    log.info("Found new subject: %s", raw_code)

                    try:
                        # Scrape schedule
                        entry = await scrape_row_schedule(page, row, subj_data)
                        
                        # 3. Save if valid
                        valid_count = sum(1 for b in entry.blocks if b.is_valid)
                        if valid_count > 0:
                            await save_subject_to_db(session, entry)
                            # Commit immediately (transaction per subject)
                            await session.commit()
                            saved_count += 1
                        else:
                            log.info("Ghost subject skipped: %s", raw_code)

                    except Exception as e:
                        log.exception("Error processing subject %s: %s", raw_code, e)
                        await session.rollback()
                        # Navigate back to schedule if we got stuck in ScheduleView
                        if "ScheduleView" in page.url:
                             await page.go_back()
                             await page.wait_for_timeout(3000)

                    # 4. Mark as processed
                    processed_codes.add(clean_key)
                    
                    # Check limits
                    if saved_count >= TEST_LIMIT:
                        log.info("Hit TEST_LIMIT (%d). Stopping.", TEST_LIMIT)
                        break
            
            log.info("=" * 60)
            log.info("Scraping complete! %d subjects saved.", saved_count)
            log.info("=" * 60)

        finally:
            await page.wait_for_timeout(3000)
            await browser.close()
            await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Parsing keyboard interrupted (Ctrl+C). Browser closed.")
    except Exception as e:
        log.critical("Critical error in parser: %s", e)
