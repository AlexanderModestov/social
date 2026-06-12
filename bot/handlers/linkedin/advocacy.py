from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from bot.handlers.linkedin._shared import run_skill, report_card
from bot.states.states import EmployeeAdvocacyStates

router = Router()


@router.callback_query(F.data == "li:employee-advocacy")
async def start_advocacy(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EmployeeAdvocacyStates.waiting_input)
    await callback.message.edit_text(
        "Describe your team and goals (size, industry, what you want from a LinkedIn "
        "program). I'll plan a 14-day launch with cadence and governance."
    )
    await callback.answer()


@router.message(EmployeeAdvocacyStates.waiting_input)
async def on_text(message: Message, state: FSMContext):
    context = (message.text or "").strip()
    if not context:
        await message.answer("Tell me about your team and goals.")
        return
    plan = await run_skill("employee-advocacy", {"context": context}, message.from_user.id)
    await state.update_data(
        save_skill="employee-advocacy",
        save_inputs={"context": context},
        save_output=plan,
    )
    card = report_card(plan)
    await message.answer(card["text"], reply_markup=card["reply_markup"])
