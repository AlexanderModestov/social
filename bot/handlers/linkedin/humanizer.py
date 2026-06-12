from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from bot.handlers.linkedin._shared import run_skill
from bot.keyboards.inline import humanizer_modes_keyboard
from bot.states.states import HumanizerStates

router = Router()


@router.callback_query(F.data == "li:humanizer")
async def start_humanizer(callback: CallbackQuery, state: FSMContext):
    await state.set_state(HumanizerStates.waiting_input)
    await state.update_data(draft=None)
    await callback.message.edit_text(
        "Paste the text you want humanized (strips AI tells, adds specifics)."
    )
    await callback.answer()


async def _run_and_show(state, draft, mode, user_id) -> str:
    output = await run_skill("humanizer", {"draft": draft, "mode": mode}, user_id)
    await state.update_data(
        draft=draft,
        save_skill="humanizer",
        save_inputs={"draft": draft, "mode": mode},
        save_output=output,
    )
    await state.set_state(HumanizerStates.reviewing)
    return f"Mode: {mode}\n\n{output}"


@router.message(HumanizerStates.waiting_input)
async def on_text(message: Message, state: FSMContext):
    draft = message.text or ""
    if not draft.strip():
        await message.answer("Send some text to humanize.")
        return
    text = await _run_and_show(state, draft, "strict", message.from_user.id)
    await message.answer(text, reply_markup=humanizer_modes_keyboard())


@router.callback_query(HumanizerStates.reviewing, F.data.startswith("hmz:"))
async def on_mode(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.split(":", 1)[1]
    data = await state.get_data()
    draft = data.get("draft") or ""
    text = await _run_and_show(state, draft, mode, callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=humanizer_modes_keyboard())
    await callback.answer()
