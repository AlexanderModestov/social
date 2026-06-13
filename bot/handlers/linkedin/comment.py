from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from bot.handlers.linkedin._shared import resolve_source, run_skill, report_card
from bot.states.states import CommentDrafterStates

router = Router()


@router.callback_query(F.data == "li:comment-drafter")
async def start_comment(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CommentDrafterStates.waiting_input)
    await callback.message.edit_text(
        "Send the LinkedIn post URL you want to comment on (or paste the post text)."
    )
    await callback.answer()


@router.message(CommentDrafterStates.waiting_input)
async def on_input(message: Message, state: FSMContext):
    content, source = await resolve_source(message.text or "")
    if source == "needs_paste":
        await message.answer(
            "I couldn't fetch that automatically. Paste the post text here and I'll draft a comment."
        )
        return
    if source == "empty" or not content.strip():
        await message.answer("Send a post URL or paste the post text.")
        return
    draft = await run_skill("comment-drafter", {"post": content}, message.from_user.id)
    await state.update_data(
        save_skill="comment-drafter", save_inputs={"post": content}, save_output=draft,
    )
    card = report_card(draft)
    await message.answer(card["text"], reply_markup=card["reply_markup"])
