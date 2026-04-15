from aiogram import Router, F
from aiogram.types import CallbackQuery

from core.database import async_session
import services.repo as repo
from services.metrics import FEEDBACK_TOTAL, REQUESTS_TOTAL

router = Router()


@router.callback_query(F.data.startswith("like_"))
async def handle_like(callback: CallbackQuery):
    REQUESTS_TOTAL.labels(handler="feedback_like").inc()
    FEEDBACK_TOTAL.labels(value="like").inc()
    interaction_id = int(callback.data.split("_", 1)[1])
    async with async_session() as session:
        await repo.update_feedback(session, interaction_id, 1)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Спасибо за отзыв!")


@router.callback_query(F.data.startswith("dislike_"))
async def handle_dislike(callback: CallbackQuery):
    REQUESTS_TOTAL.labels(handler="feedback_dislike").inc()
    FEEDBACK_TOTAL.labels(value="dislike").inc()
    interaction_id = int(callback.data.split("_", 1)[1])
    async with async_session() as session:
        await repo.update_feedback(session, interaction_id, -1)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Спасибо за отзыв!")
