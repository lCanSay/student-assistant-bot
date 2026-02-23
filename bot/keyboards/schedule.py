from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

schedule_main_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="👨‍🏫 По преподавателю", callback_data="search_instructor")],
        [InlineKeyboardButton(text="🚪 По аудитории", callback_data="search_room")],
        [InlineKeyboardButton(text="📚 По предмету", callback_data="search_subject")],
    ]
)
