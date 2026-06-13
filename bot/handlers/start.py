from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from bot.db.session import async_session_factory
from bot.db.repository import UserRepository, ToneOfVoiceRepository
from bot.keyboards.inline import main_menu_keyboard, platform_keyboard

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    async with async_session_factory() as session:
        await UserRepository(session).get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
        )
        await session.commit()
        channels = await ToneOfVoiceRepository(session).get_channels_with_tov(
            message.from_user.id
        )

    await message.answer(
        "👋 Welcome! I help you create content for Instagram, LinkedIn, and TikTok.\n\n"
        "What would you like to do?",
        reply_markup=main_menu_keyboard(channels_with_tov=channels),
    )

@router.callback_query(lambda c: c.data == "action:create_content")
async def on_create_content(callback: CallbackQuery):
    await callback.message.edit_text(
        "Choose your platform:",
        reply_markup=platform_keyboard(),
    )
    await callback.answer()
