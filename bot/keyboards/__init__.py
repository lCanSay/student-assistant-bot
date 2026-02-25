from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Main reply keyboard for the bot."""
    kb_list = [
        [
            KeyboardButton(text="📅 Расписание"),
            KeyboardButton(text="🚪 Свободные аудитории"),
            KeyboardButton(text="❓ Помощь"),
        ],
        [
            KeyboardButton(text="🗺 Карта КБТУ"),
            KeyboardButton(text="📅 Академ. календарь"),
            KeyboardButton(text="📚 РУПы"),
        ],
    ]
    return ReplyKeyboardMarkup(
        keyboard=kb_list,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Выберите действие",
    )
