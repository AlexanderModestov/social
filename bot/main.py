import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from bot.config import settings
from bot.handlers import start, tone_of_voice, linkedin, tiktok

logging.basicConfig(level=logging.INFO)

async def main():
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(tone_of_voice.router)
    dp.include_router(linkedin.router)
    dp.include_router(tiktok.router)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
