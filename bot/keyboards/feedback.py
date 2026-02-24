from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_feedback_keyboard(interaction_id: int) -> InlineKeyboardMarkup:
    """Return 👍/👎 inline buttons tied to an interaction ID."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👍", callback_data=f"like_{interaction_id}"),
                InlineKeyboardButton(text="👎", callback_data=f"dislike_{interaction_id}"),
            ]
        ]
    )
