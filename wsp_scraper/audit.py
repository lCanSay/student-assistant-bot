import json
import os
import logging

"""Logs from all subjects that were dropped during parsing with reasoning(saved to dropped_items.jsonl)"""

log = logging.getLogger("scraper.audit")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE_PATH = os.path.join(PROJECT_ROOT, "dropped_items.jsonl")

def log_dropped_item(item_type: str, code: str, reason: str, raw_text: str = "") -> None:
    """Append a dropped block or ghost subject to the JSONL audit file."""
    record = {
        "type": item_type,
        "code": code,
        "reason": reason,
        "raw_text": raw_text
    }
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        log.error("Failed to write audit log: %s", e)
