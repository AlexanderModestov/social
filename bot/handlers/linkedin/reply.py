from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from bot.handlers.linkedin._shared import resolve_source, run_skill, report_card
from bot.states.states import ReplyHandlerStates

router = Router()


@router.callback_query(F.data == "li:reply-handler")
async def start_reply(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ReplyHandlerStates.waiting_input)
    await callback.message.edit_text(
        "Send the comment URL you want to reply to (or paste the comment + thread context)."
    )
    await callback.answer()


@router.message(ReplyHandlerStates.waiting_input)
async def on_input(message: Message, state: FSMContext):
    content, source = await resolve_source(message.text or "")
    if source == "needs_paste":
        await message.answer(
            "I couldn't fetch that automatically. Paste the comment + thread context here and I'll draft a reply."
        )
        return
    if source == "empty" or not content.strip():
        await message.answer("Send a comment URL or paste the comment + thread context.")
        return
    draft = await run_skill("reply-handler", {"thread": content}, message.from_user.id)
    await state.update_data(
        save_skill="reply-handler", save_inputs={"thread": content}, save_output=draft,
    )
    card = report_card(draft)
    await message.answer(card["text"], reply_markup=card["reply_markup"])
