"""Access-control middleware: only allow-listed Telegram users may use the bot.

Registered as an OUTER middleware on the dispatcher's update observer so it runs
once per update, before routing — blocking every update type (messages, callback
queries, etc.) from users not in the allowlist. Fail-closed: an empty allowlist
blocks everyone.
"""
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

logger = logging.getLogger(__name__)

DENY_MESSAGE = "Sorry, you don't have access to this bot."


class AccessControlMiddleware(BaseMiddleware):
    def __init__(self, allowed_ids: set[int]):
        self.allowed_ids = set(allowed_ids)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is not None and user.id in self.allowed_ids:
            return await handler(event, data)

        if user is not None:
            logger.info("Blocked update from non-allowlisted user id=%s", user.id)
        await self._deny(event)
        return None

    @staticmethod
    async def _deny(event: TelegramObject) -> None:
        """Tell the blocked user once, on whatever update type came in."""
        message = getattr(event, "message", None)
        callback = getattr(event, "callback_query", None)
        try:
            if message is not None:
                await message.answer(DENY_MESSAGE)
            elif callback is not None:
                await callback.answer(DENY_MESSAGE, show_alert=True)
        except Exception:  # never let a denial reply crash update handling
            logger.debug("Failed to deliver access-denied notice", exc_info=True)
