from aiogram.fsm.state import StatesGroup, State


class ScheduleSearch(StatesGroup):
    waiting_for_instructor = State()
    waiting_for_room = State()
    waiting_for_subject = State()
