from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from bot.handlers.linkedin._shared import resolve_source, run_skill, report_card
from bot.states.states import HookExtractorStates

router = Router()


@router.callback_query(F.data == "li:hook-extractor")
async def start_hook_extractor(callback: CallbackQuery, state: FSMContext):
    await state.set_state(HookExtractorStates.waiting_input)
    await callback.message.edit_text(
        "Send a viral LinkedIn post URL to reverse-engineer (or paste the post text)."
    )
    await callback.answer()


@router.message(HookExtractorStates.waiting_input)
async def on_input(message: Message, state: FSMContext):
    content, source = await resolve_source(message.text or "")
    if source == "needs_paste":
        await message.answer(
            "I couldn't fetch that automatically. Paste the post text here and I'll reverse-engineer the hook."
        )
        return
    if source == "empty" or not content.strip():
        await message.answer("Send a post URL or paste the post text.")
        return
    result = await run_skill("hook-extractor", {"post": content}, message.from_user.id)
    await state.update_data(
        save_skill="hook-extractor", save_inputs={"post": content}, save_output=result,
    )
    card = report_card(result)
    await message.answer(card["text"], reply_markup=card["reply_markup"])
