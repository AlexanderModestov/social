from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from bot.handlers.linkedin._shared import run_skill, report_card
from bot.states.states import ProfileOptimizerStates

router = Router()


@router.callback_query(F.data == "li:profile-optimizer")
async def start_profile(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileOptimizerStates.waiting_input)
    await callback.message.edit_text(
        "Paste your current LinkedIn profile text — headline, About section, and "
        "Experience. I'll rewrite them for 2026 conversion."
    )
    await callback.answer()


@router.message(ProfileOptimizerStates.waiting_input)
async def on_text(message: Message, state: FSMContext):
    text = message.text or ""
    if not text.strip():
        await message.answer("Paste your profile text (headline, About, Experience).")
        return
    result = await run_skill("profile-optimizer", {"profile": text}, message.from_user.id)
    await state.update_data(
        save_skill="profile-optimizer", save_inputs={"profile": text}, save_output=result,
    )
    card = report_card(result)
    await message.answer(card["text"], reply_markup=card["reply_markup"])
