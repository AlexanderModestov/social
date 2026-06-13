from aiogram import F, Router
from aiogram.types import CallbackQuery
from bot.keyboards.inline import linkedin_menu_keyboard

router = Router()


@router.callback_query(F.data == "platform:linkedin")
async def show_linkedin_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "Choose a LinkedIn skill:", reply_markup=linkedin_menu_keyboard()
    )
    await callback.answer()
