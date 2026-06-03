import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent
from bot.config import settings
from bot.handlers import start, tone_of_voice, linkedin, tiktok

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    @dp.errors()
    async def handle_errors(event: ErrorEvent) -> bool:
        exc = event.exception
        if isinstance(exc, TelegramBadRequest) and "query is too old" in str(exc):
            logger.debug("Ignored expired callback query: %s", exc)
            return True
        logger.exception("Unhandled exception: %s", exc)
        return False

    dp.include_router(start.router)
    dp.include_router(tone_of_voice.router)
    dp.include_router(linkedin.router)
    dp.include_router(tiktok.router)

    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
