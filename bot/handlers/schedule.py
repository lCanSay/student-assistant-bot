from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

from bot.states.schedule import ScheduleSearch
from bot.keyboards.schedule import schedule_main_kb
from core.database import async_session
from services.wsp_repo import (
    search_schedule_by_instructor,
    search_schedule_by_room,
    search_schedule_by_subject,
)
from utils.formatters import format_schedule

router = Router()

NO_RESULTS_TEXT = "❌ Ничего не найдено. Попробуйте другой запрос."


# ---------- /schedule command + reply keyboard button ----------

@router.message(Command("schedule"))
@router.message(F.text == "📅 Расписание")
async def cmd_schedule(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📅 Поиск расписания\nВыберите тип поиска:",
        reply_markup=schedule_main_kb,
    )


# ---------- Callback handlers (set FSM state) ----------

@router.callback_query(F.data == "search_instructor")
async def cb_search_instructor(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ScheduleSearch.waiting_for_instructor)
    await callback.message.answer("👨‍🏫 Введите фамилию преподавателя:")
    await callback.answer()


@router.callback_query(F.data == "search_room")
async def cb_search_room(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ScheduleSearch.waiting_for_room)
    await callback.message.answer("🚪 Введите номер аудитории:")
    await callback.answer()


@router.callback_query(F.data == "search_subject")
async def cb_search_subject(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ScheduleSearch.waiting_for_subject)
    await callback.message.answer("📚 Введите название или код предмета:")
    await callback.answer()


# ---------- Helper ----------

MAX_MSG_LEN = 4000


async def _send_schedule(message: Message, events: list, title: str, query: str):
    """Send schedule as inline HTML or as a .txt file if too long."""
    if not events:
        await message.answer(NO_RESULTS_TEXT)
        return

    text_html = format_schedule(events, title, as_html=True)

    if len(text_html) <= MAX_MSG_LEN:
        await message.answer(text_html, parse_mode=ParseMode.HTML)
    else:
        text_plain = format_schedule(events, title, as_html=False)
        safe_name = query.replace(" ", "_").replace("/", "-")
        document = BufferedInputFile(
            text_plain.encode("utf-8"),
            filename=f"Schedule_{safe_name}.txt",
        )
        await message.answer_document(
            document=document,
            caption="Расписание слишком большое. Отправил полным текстовым файлом 👆",
        )


# ---------- Message handlers (process user input) ----------

@router.message(ScheduleSearch.waiting_for_instructor)
async def process_instructor_search(message: Message, state: FSMContext):
    query = message.text.strip()
    async with async_session() as session:
        events = await search_schedule_by_instructor(session, query)
    await _send_schedule(message, events, f"преп. {query}", query)
    await state.clear()


@router.message(ScheduleSearch.waiting_for_room)
async def process_room_search(message: Message, state: FSMContext):
    query = message.text.strip()
    async with async_session() as session:
        events = await search_schedule_by_room(session, query)
    await _send_schedule(message, events, f"каб. {query}", query)
    await state.clear()


@router.message(ScheduleSearch.waiting_for_subject)
async def process_subject_search(message: Message, state: FSMContext):
    query = message.text.strip()
    async with async_session() as session:
        events = await search_schedule_by_subject(session, query)
    await _send_schedule(message, events, query, query)
    await state.clear()
