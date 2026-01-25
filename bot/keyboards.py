from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_keyboard() -> ReplyKeyboardMarkup:
    # Creates and returns the main menu keyboard.
    kb_list = [
        [
            KeyboardButton(text="📅 Мое расписание"),
            KeyboardButton(text="🔍 Свободные аудитории")
        ],
        [
            KeyboardButton(text="📞 Контакты"),
            KeyboardButton(text="❓ Помощь")
        ]
    ]
    keyboard = ReplyKeyboardMarkup(
        keyboard=kb_list,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Выберите действие"
    )
    return keyboard
