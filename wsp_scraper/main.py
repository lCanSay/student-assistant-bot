import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from playwright.async_api import async_playwright
from core.database import engine, Base, async_session
from wsp_scraper.browser import login, navigate_to_schedule, find_next_unprocessed_row, scrape_row_schedule
from wsp_scraper.db_service import save_subject_to_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("scraper.main")

async def main() -> None:
    """Run the full scraping pipeline (Single Pass)."""
    
    WSP_LOGIN = os.getenv("WSP_LOGIN")
    WSP_PASSWORD = os.getenv("WSP_PASSWORD")

    if not WSP_LOGIN or not WSP_PASSWORD:
        log.error("WSP_LOGIN / WSP_PASSWORD not set in .env — aborting.")
        sys.exit(1)

    log.info("WSP Schedule Scraper — Single Pass (Modular)")

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
            await login(page)
            await navigate_to_schedule(page)

            col_names = [
                "code", "name_ru", "name_kz", "name_en",
                "department", "credits", "formula", "year", "period",
            ]

            processed_codes: set[str] = set()
            saved_count = 0
            no_new_count = 0
            
            TEST_LIMIT = 50
            
            scroll_container = page.locator(".v-table-body-wrapper")
            if await scroll_container.count() > 0:
                await scroll_container.first.evaluate("el => el.scrollLeft = 9999")
                await page.wait_for_timeout(1000)

            async with async_session() as session:
                log.info("Starting single-pass scroll & scrape loop...")
                
                while no_new_count < 10:
                    row, subj_data = await find_next_unprocessed_row(page, processed_codes, col_names)
                    
                    if row is None:
                        no_new_count += 1
                        log.debug(f"No new rows found (streak={no_new_count}). Scrolling...")
                        
                        if await scroll_container.count() > 0:
                            await scroll_container.first.evaluate("el => el.scrollTop += 400")
                        else:
                            await page.evaluate("window.scrollBy(0, 400)")
                            
                        await page.wait_for_timeout(800)
                        continue

                    no_new_count = 0
                    raw_code = subj_data["code"]
                    clean_key = raw_code.strip().replace(" ", "")
                    
                    log.info("Found new subject: %s", raw_code)

                    try:
                        entry = await scrape_row_schedule(page, row, subj_data)
                        
                        valid_count = sum(1 for b in entry.blocks if b.is_valid)
                        if valid_count > 0:
                            await save_subject_to_db(session, entry)
                            await session.commit()
                            saved_count += 1
                        else:
                            log.info("Ghost subject skipped: %s", raw_code)

                    except Exception as e:
                        log.exception("Error processing subject %s: %s", raw_code, e)
                        await session.rollback()
                        if "ScheduleView" in page.url:
                             await page.go_back()
                             await page.wait_for_timeout(3000)

                    processed_codes.add(clean_key)
                    
                    if saved_count >= TEST_LIMIT:
                        log.info("Hit TEST_LIMIT (%d). Stopping.", TEST_LIMIT)
                        break
            
            log.info("Scraping complete! %d subjects saved.", saved_count)

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
