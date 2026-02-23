from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Main reply keyboard for the bot."""
    kb_list = [
        [
            KeyboardButton(text="📅 Расписание"),
            KeyboardButton(text="❓ Помощь"),
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=kb_list,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Выберите действие",
    )
