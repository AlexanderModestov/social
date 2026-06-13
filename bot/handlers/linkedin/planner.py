from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from bot.handlers.linkedin._shared import run_skill, report_card
from bot.states.states import ContentPlannerStates

router = Router()


@router.callback_query(F.data == "li:content-planner")
async def start_planner(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ContentPlannerStates.waiting_role)
    await callback.message.edit_text("What's your role? (e.g. 'B2B SaaS founder')")
    await callback.answer()


@router.message(ContentPlannerStates.waiting_role)
async def on_role(message: Message, state: FSMContext):
    role = (message.text or "").strip()
    if not role:
        await message.answer("Tell me your role first.")
        return
    await state.update_data(planner_role=role)
    await state.set_state(ContentPlannerStates.waiting_audience)
    await message.answer("Who's your target audience? (e.g. 'VPs of Marketing')")


@router.message(ContentPlannerStates.waiting_audience)
async def on_audience(message: Message, state: FSMContext):
    audience = (message.text or "").strip()
    if not audience:
        await message.answer("Tell me your target audience.")
        return
    data = await state.get_data()
    role = data.get("planner_role", "")
    plan = await run_skill(
        "content-planner", {"role": role, "audience": audience}, message.from_user.id
    )
    await state.update_data(
        save_skill="content-planner",
        save_inputs={"role": role, "audience": audience},
        save_output=plan,
    )
    card = report_card(plan)
    await message.answer(card["text"], reply_markup=card["reply_markup"])
