import asyncio
import logging
import sys

print("=== bot.main loading ===", flush=True)

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

print("=== importing handlers ===", flush=True)
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent
from bot.config import settings
from bot.handlers import start, tone_of_voice, tiktok
from bot.handlers import linkedin as linkedin_pkg
from bot.middlewares.access import AccessControlMiddleware
print("=== all imports OK ===", flush=True)

async def main():
    logger.info("Creating bot...")
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    allowed = settings.allowed_users()
    logger.info("Access control: %d allow-listed user(s)", len(allowed))
    dp.update.outer_middleware(AccessControlMiddleware(allowed))

    logger.info("Bot created, registering routers...")

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
    for r in linkedin_pkg.routers:
        dp.include_router(r)
    dp.include_router(tiktok.router)

    logger.info("Starting polling...")
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    print("=== starting asyncio.run(main()) ===", flush=True)
    asyncio.run(main())
