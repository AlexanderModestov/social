from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from bot.handlers.linkedin._shared import run_skill, report_card
from bot.states.states import PostAuditStates

router = Router()


@router.callback_query(F.data == "li:post-audit")
async def start_audit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PostAuditStates.waiting_input)
    await callback.message.edit_text(
        "Paste the post draft to audit (algorithm + AI-detection check, no rewrite)."
    )
    await callback.answer()


@router.message(PostAuditStates.waiting_input)
async def on_text(message: Message, state: FSMContext):
    draft = message.text or ""
    if not draft.strip():
        await message.answer("Send a draft to audit.")
        return
    report = await run_skill("post-audit", {"draft": draft, "mode": "audit"}, message.from_user.id)
    await state.update_data(
        save_skill="post-audit", save_inputs={"draft": draft}, save_output=report,
    )
    card = report_card(report)
    await message.answer(card["text"], reply_markup=card["reply_markup"])
