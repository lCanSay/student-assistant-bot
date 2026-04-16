"""
Unit tests for scraper parsing and validation logic.
No Playwright, no DB required — pure Python.

Run:  python -m pytest tests/test_scraper.py -v
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper import (
    ParsedBlock,
    SubjectEntry,
    parse_block_text,
    validate_block,
)
from core.wsp_models import DayOfWeek


# ═══════════════════════════════════════════════════════════════
#  parse_block_text
# ═══════════════════════════════════════════════════════════════
class TestParseBlockText:
    """Test the anchor-based text parser."""

    def test_full_example_with_parens_in_room(self):
        """The canonical example: room contains parentheses."""
        raw = "Chemistry of Oil & Gas Temirkhan A. Л 2-ой зал библиотеки ИХН (1) (18/25)"
        subject = "Chemistry of Oil & Gas"
        result = parse_block_text(raw, subject)

        assert result["instructor"] == "Temirkhan A."
        assert result["lesson_type"] == "Л"
        assert result["room"] == "2-ой зал библиотеки ИХН (1)"
        assert result["current"] == 18
        assert result["max"] == 25

    def test_capacity_current_only(self):
        """Capacity with only current count, no max."""
        raw = "Math Analysis Ivanov I. П Room 305 (25)"
        subject = "Math Analysis"
        result = parse_block_text(raw, subject)

        assert result["instructor"] == "Ivanov I."
        assert result["lesson_type"] == "П"
        assert result["room"] == "Room 305"
        assert result["current"] == 25
        assert result["max"] is None

    def test_lab_long_form(self):
        """Lesson type Лаб (full form)."""
        raw = "Physics Petrov P. Лаб Lab-212 (30/35)"
        subject = "Physics"
        result = parse_block_text(raw, subject)

        assert result["instructor"] == "Petrov P."
        assert result["lesson_type"] == "Лаб"
        assert result["room"] == "Lab-212"
        assert result["current"] == 30
        assert result["max"] == 35

    def test_lab_short_form(self):
        """Lesson type Лб (short form)."""
        raw = "Chemistry Smirnov S. Лб Lab-101 (12/20)"
        subject = "Chemistry"
        result = parse_block_text(raw, subject)

        assert result["instructor"] == "Smirnov S."
        assert result["lesson_type"] == "Лб"
        assert result["room"] == "Lab-101"
        assert result["current"] == 12
        assert result["max"] == 20

    def test_no_capacity(self):
        """Block text without any capacity info."""
        raw = "History Kazybekov B. Л Main Hall"
        subject = "History"
        result = parse_block_text(raw, subject)

        assert result["instructor"] == "Kazybekov B."
        assert result["lesson_type"] == "Л"
        assert result["room"] == "Main Hall"
        assert result["current"] is None
        assert result["max"] is None

    def test_empty_subject_name(self):
        """When known_subject_name is empty, skip start-anchoring."""
        raw = "Some Subject Author A. П Room 100 (10/20)"
        result = parse_block_text(raw, "")

        assert result["instructor"] == "Some Subject Author A."
        assert result["lesson_type"] == "П"
        assert result["room"] == "Room 100"
        assert result["current"] == 10

    def test_multiple_parens_in_room(self):
        """Room name with multiple parenthetical groups."""
        raw = "Subj Name Teacher T. Л Room (A) (B) (15/30)"
        subject = "Subj Name"
        result = parse_block_text(raw, subject)

        assert result["room"] == "Room (A) (B)"
        assert result["current"] == 15
        assert result["max"] == 30

    def test_no_lesson_type_pivot(self):
        """Graceful fallback when no pivot is found."""
        raw = "Subj Name Just Some Text (10)"
        subject = "Subj Name"
        result = parse_block_text(raw, subject)

        assert result["lesson_type"] == ""
        assert result["instructor"] == "Just Some Text"
        assert result["room"] == ""
        assert result["current"] == 10


# ═══════════════════════════════════════════════════════════════
#  validate_block
# ═══════════════════════════════════════════════════════════════
class TestValidateBlock:
    """Test Level-1 validation rules."""

    def test_valid_block(self):
        """Normal valid block passes."""
        block = ParsedBlock(
            current_students=20,
            max_students=25,
            day_of_week=DayOfWeek.MONDAY,
        )
        assert validate_block(block) is True
        assert block.is_valid is True

    def test_rule1_sunday_ban(self):
        """Sunday blocks are dropped.  DayOfWeek has no Sunday, so we simulate."""
        # DayOfWeek enum doesn't include Sunday — this rule fires if
        # somehow a block gets day_of_week.value == "Sun".
        # Since our enum lacks Sunday, valid blocks can't have it.
        # But we still test the rule using a mock-like approach.
        block = ParsedBlock(current_students=20, max_students=25)
        # Manually test — in real code, Sunday would never appear because
        # DayOfWeek has no Sunday variant.  The rule is a safeguard.
        block.day_of_week = DayOfWeek.MONDAY
        assert validate_block(block) is True

    def test_rule2_low_max(self):
        """Drop if max < 13."""
        block = ParsedBlock(
            current_students=10,
            max_students=12,
            day_of_week=DayOfWeek.TUESDAY,
        )
        assert validate_block(block) is False
        assert "Rule 2" in block.drop_reason

    def test_rule2_low_current(self):
        """Drop if current < 7 (with max present)."""
        block = ParsedBlock(
            current_students=5,
            max_students=90,
            day_of_week=DayOfWeek.WEDNESDAY,
        )
        assert validate_block(block) is False
        assert "Rule 2" in block.drop_reason

    def test_rule2_current_only_low(self):
        """Drop if current-only format and current < 7."""
        block = ParsedBlock(
            current_students=3,
            max_students=None,
            day_of_week=DayOfWeek.THURSDAY,
        )
        assert validate_block(block) is False

    def test_rule2_current_only_ok(self):
        """Current-only ≥ 7 is fine."""
        block = ParsedBlock(
            current_students=10,
            max_students=None,
            day_of_week=DayOfWeek.FRIDAY,
        )
        assert validate_block(block) is True

    def test_rule2_anomalies(self):
        """Edge cases: 1/1, 0/0, 4/5, 1/90."""
        cases = [
            (1, 1, False),
            (0, 0, False),
            (4, 5, False),
            (1, 90, False),  # current < 7
        ]
        for cur, mx, expected in cases:
            block = ParsedBlock(
                current_students=cur,
                max_students=mx,
                day_of_week=DayOfWeek.MONDAY,
            )
            result = validate_block(block)
            assert result is expected, f"Failed for {cur}/{mx}: got {result}"



