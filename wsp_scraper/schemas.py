from dataclasses import dataclass, field
from datetime import time as dt_time
from typing import Optional
from core.wsp_models import DayOfWeek

@dataclass
class ParsedBlock:
    """Represents one schedule cell extracted from the modal."""

    subject_code: str = ""
    subject_name: str = ""
    instructor: str = ""
    lesson_type: str = ""
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
