from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from bot.db.session import async_session_factory
from bot.db.repository import UserRepository
from bot.keyboards.inline import main_menu_keyboard, platform_keyboard

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    async with async_session_factory() as session:
        repo = UserRepository(session)
        await repo.get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
        )
        await session.commit()

    await message.answer(
        "👋 Welcome! I help you create content for LinkedIn and TikTok.\n\n"
        "What would you like to do?",
        reply_markup=main_menu_keyboard(),
    )

@router.callback_query(lambda c: c.data == "action:create_content")
async def on_create_content(callback: CallbackQuery):
    await callback.message.edit_text(
        "Choose your platform:",
        reply_markup=platform_keyboard(),
    )
    await callback.answer()
