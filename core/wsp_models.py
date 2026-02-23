from __future__ import annotations

import enum
from typing import List, Optional

from core.database import Base
from sqlalchemy import (
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


class DayOfWeek(enum.Enum):
    MONDAY    = "Mon"
    TUESDAY   = "Tue"
    WEDNESDAY = "Wed"
    THURSDAY  = "Thu"
    FRIDAY    = "Fri"
    SATURDAY  = "Sat"


class LessonType(enum.Enum):
    LECTURE  = "Л"
    PRACTICE = "П"
    LAB      = "Лаб"


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name_ru: Mapped[Optional[str]] = mapped_column(String(255))
    name_kz: Mapped[Optional[str]] = mapped_column(String(255))
    name_en: Mapped[Optional[str]] = mapped_column(String(255))
    department: Mapped[Optional[str]] = mapped_column(String(255))
    credits: Mapped[Optional[float]] = mapped_column(Float)
    formula: Mapped[Optional[str]] = mapped_column(String(20))    # e.g. "1/0/2" (Lec/Prac/Lab)
    year: Mapped[Optional[str]] = mapped_column(String(20))
    period: Mapped[Optional[str]] = mapped_column(String(50))

    events: Mapped[List[ScheduleEvent]] = relationship(
        "ScheduleEvent", back_populates="subject", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Subject code={self.code!r}>"


class Instructor(Base):
    __tablename__ = "instructors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    events: Mapped[List[ScheduleEvent]] = relationship("ScheduleEvent", back_populates="instructor")

    def __repr__(self) -> str:
        return f"<Instructor full_name={self.full_name!r}>"


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    street: Mapped[Optional[str]] = mapped_column(String(255))    # nullable: may not always be known

    events: Mapped[List[ScheduleEvent]] = relationship("ScheduleEvent", back_populates="room")

    def __repr__(self) -> str:
        return f"<Room number={self.number!r}>"


class ScheduleEvent(Base):
    __tablename__ = "schedule_events"

    __table_args__ = (
        UniqueConstraint("subject_id", "day_of_week", "start_time", "lesson_type", "room_id", name="uq_event_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    instructor_id: Mapped[int] = mapped_column(ForeignKey("instructors.id", ondelete="RESTRICT"), nullable=False, index=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=False, index=True)

    day_of_week: Mapped[DayOfWeek] = mapped_column(SAEnum(DayOfWeek, name="day_of_week_enum"), nullable=False, index=True)
    start_time: Mapped[Time] = mapped_column(Time, nullable=False)  # derived from CSS `top` offset
    end_time: Mapped[Time] = mapped_column(Time, nullable=False)    # derived from CSS `height` offset
    lesson_type: Mapped[LessonType] = mapped_column(SAEnum(LessonType, name="lesson_type_enum"), nullable=False)

    group_info: Mapped[Optional[str]] = mapped_column(String(50))          # raw "(current/max)", e.g. "76/75"
    student_count_current: Mapped[Optional[int]] = mapped_column(Integer)
    student_count_max: Mapped[Optional[int]] = mapped_column(Integer)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    subject: Mapped[Subject] = relationship("Subject", back_populates="events")
    instructor: Mapped[Instructor] = relationship("Instructor", back_populates="events")
    room: Mapped[Room] = relationship("Room", back_populates="events")

    def __repr__(self) -> str:
        return f"<ScheduleEvent subject_id={self.subject_id} day={self.day_of_week} time={self.start_time}–{self.end_time}>"
