import logging
import re
import os
from typing import Optional
from datetime import time as dt_time
from playwright.async_api import Page, Locator

from .schemas import SubjectEntry, ParsedBlock, DayOfWeek
from .parser import (
    parse_block_text,
    validate_block,
    DAY_LABEL_MAP,
    FIRST_SLOT_HOUR,
    FIRST_SLOT_MIN
)

log = logging.getLogger("scraper.browser")

WSP_LOGIN = os.getenv("WSP_LOGIN")
WSP_PASSWORD = os.getenv("WSP_PASSWORD")
TARGET_URL = "https://wsp.kbtu.kz/SubjectSchedule"

async def login(page: Page) -> None:
    log.info("Navigating to login page...")
    await page.goto("https://wsp.kbtu.kz", wait_until="networkidle", timeout=30_000)
    await page.wait_for_timeout(3000)

    gb_flag = page.locator("img[src*='gb.png']")
    if await gb_flag.count() > 0:
        await gb_flag.first.click()
        log.info("Switched UI to English")
        await page.wait_for_timeout(5000)
        await page.wait_for_load_state("networkidle", timeout=15_000)

    login_icon = page.locator("img[src*='login_24']")
    await login_icon.wait_for(state="visible", timeout=10_000)
    await login_icon.click()
    log.info("Clicked login icon")
    await page.wait_for_timeout(3000)

    username_field = page.locator("input.v-filterselect-input")
    await username_field.wait_for(state="visible", timeout=10_000)
    await username_field.click()
    if WSP_LOGIN:
        await username_field.fill(WSP_LOGIN)
    else:
        log.error("WSP_LOGIN not set")

    password_field = page.locator("input[type='password']")
    await password_field.wait_for(state="visible", timeout=10_000)
    if WSP_PASSWORD:
        await password_field.fill(WSP_PASSWORD)
    else:
        log.error("WSP_PASSWORD not set")

    submit = page.locator(
        ".v-button:has-text('Log in'), .v-button:has-text('\u041a\u0456\u0440\u0443'), "
        ".v-button:has-text('\u0412\u043e\u0439\u0442\u0438'), .v-button:has-text('Login')"
    )
    if await submit.count() > 0:
        await submit.first.click()
    else:
        log.warning("No login button found - pressing Enter")
        await password_field.press("Enter")

    await page.wait_for_timeout(3000)
    await page.wait_for_load_state("networkidle", timeout=15_000)
    log.info("Login complete: %s", page.url)


async def navigate_to_schedule(page: Page) -> None:
    log.info("Navigating to %s", TARGET_URL)
    await page.goto(TARGET_URL, wait_until="networkidle", timeout=30_000)
    await page.wait_for_timeout(3000)
    log.info("Schedule page loaded: %s", page.url)


async def extract_row_metadata(cells: list[Locator], col_names: list[str]) -> dict:
    row_data: dict = {}
    for i, col in enumerate(col_names):
        if i < len(cells):
            text = (await cells[i].inner_text()).strip()
            row_data[col] = text
        else:
            row_data[col] = ""
    return row_data


async def find_next_unprocessed_row(
    page: Page, processed_codes: set[str], col_names: list[str]
) -> tuple[Optional[Locator], Optional[dict]]:
    rows = await page.locator(".v-table-body tr").all()
    
    for row in rows:
        cells = await row.locator("td").all()
        if len(cells) < 2:
            continue

        raw_code = (await cells[0].inner_text()).strip()
        code_key = raw_code.replace(" ", "")
        
        if not code_key or code_key in processed_codes:
            continue
            
        subject_data = await extract_row_metadata(cells, col_names)
        subject_data["code"] = raw_code 
        
        return row, subject_data
        
    return None, None


async def detect_schedule_layout(page: Page) -> list[tuple[DayOfWeek, Locator]]:
    day_columns: list[tuple[DayOfWeek, Locator]] = []
    columns = page.locator("div.v-verticallayout[class*='v-border-left-1-bfbfbf']")
    col_count = await columns.count()

    for i in range(col_count):
        col = columns.nth(i)
        label = col.locator(".v-label.bold")
        if await label.count() == 0:
            continue

        label_text = (await label.first.inner_text()).strip().lower()
        day = DAY_LABEL_MAP.get(label_text)
        if day is None:
            continue

        items = col.locator(".v-absolutelayout-wrapper-schedule-item")
        if await items.count() == 0:
            continue

        day_columns.append((day, col))

    return day_columns


async def scrape_row_schedule(
    page: Page, row_element: Locator, subject_data: dict
) -> SubjectEntry:
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

    if subject_data.get("year"):
        entry.year = subject_data["year"]
    if subject_data.get("period"):
        entry.period = subject_data["period"]

    credits_str = subject_data.get("credits", "")
    if credits_str:
        try:
            entry.credits = float(credits_str)
        except ValueError:
            pass

    log.info("Scraping subject: %s (%s)", code, name)

    await row_element.dblclick()
    await page.wait_for_timeout(5000)

    if "ScheduleView" not in page.url:
        log.warning("Did not navigate to ScheduleView for %s", code)
        return entry

    day_columns = await detect_schedule_layout(page)

    if not day_columns:
        log.warning("No day columns detected for %s — trying flat approach", code)
        all_items = page.locator(".v-absolutelayout-wrapper-schedule-item")
        item_count = await all_items.count()

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
        for day, column_loc in day_columns:
            items = column_loc.locator(".v-absolutelayout-wrapper-schedule-item")
            item_count = await items.count()

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
    log.info("Subject %s: %d total blocks, %d valid", code, len(entry.blocks), valid_count)

    back_btn = page.locator("img[src*='arrow_left']")
    if await back_btn.count() > 0:
        await back_btn.first.click()
        await page.wait_for_timeout(3000)
    else:
        await page.go_back()
        await page.wait_for_timeout(3000)

    return entry
