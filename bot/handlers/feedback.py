from aiogram import Router, F
from aiogram.types import CallbackQuery

from core.database import async_session
import services.repo as repo

router = Router()


@router.callback_query(F.data.startswith("like_"))
async def handle_like(callback: CallbackQuery):
    interaction_id = int(callback.data.split("_", 1)[1])
    async with async_session() as session:
        await repo.update_feedback(session, interaction_id, 1)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Спасибо за отзыв!")


@router.callback_query(F.data.startswith("dislike_"))
async def handle_dislike(callback: CallbackQuery):
    interaction_id = int(callback.data.split("_", 1)[1])
    async with async_session() as session:
        await repo.update_feedback(session, interaction_id, -1)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Спасибо за отзыв!")
