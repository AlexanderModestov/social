from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.db.session import async_session_factory
from bot.db.repository import ToneOfVoiceRepository
from bot.keyboards.inline import settings_keyboard

router = Router()


async def _channels(user_id: int) -> set[str]:
    async with async_session_factory() as session:
        return await ToneOfVoiceRepository(session).get_channels_with_tov(user_id)


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    channels = await _channels(message.from_user.id)
    await message.answer(
        "Your tone of voice per channel:",
        reply_markup=settings_keyboard(channels),
    )


@router.callback_query(F.data.startswith("settings:delete:"))
async def on_settings_delete(callback: CallbackQuery, state: FSMContext):
    channel = callback.data.split(":")[2]
    async with async_session_factory() as session:
        repo = ToneOfVoiceRepository(session)
        await repo.delete(callback.from_user.id, channel)
        await session.commit()
        channels = await repo.get_channels_with_tov(callback.from_user.id)
    await callback.message.edit_text("Updated.", reply_markup=settings_keyboard(channels))
    await callback.answer("Deleted.")


@router.callback_query(F.data.startswith("settings:create:"))
async def on_settings_create(callback: CallbackQuery, state: FSMContext):
    from bot.states.states import ToneOfVoiceStates
    from bot.keyboards.inline import tov_method_keyboard

    channel = callback.data.split(":")[2]
    await state.update_data(channel=channel)
    await state.set_state(ToneOfVoiceStates.choosing_method)
    await callback.message.edit_text(
        "How would you like to define it?",
        reply_markup=tov_method_keyboard(channel),
    )
    await callback.answer()
