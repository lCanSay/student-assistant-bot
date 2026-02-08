from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message
from cachetools import TTLCache

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, limit: int = 1, ttl: float = 5.0):
        self.cache = TTLCache(maxsize=10000, ttl=ttl)

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if event.from_user.id in self.cache:
            # User is throttled, stop propagation
            return None
        
        # else add user to cache
        self.cache[event.from_user.id] = True
        
        return await handler(event, data)
