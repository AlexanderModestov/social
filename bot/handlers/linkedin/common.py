from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from bot.handlers.linkedin._shared import save_history

router = Router()


@router.callback_query(F.data == "skill:save")
async def on_skill_save(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    skill = data.get("save_skill")
    if not skill or data.get("save_output") is None:
        await callback.answer("Nothing to save.", show_alert=True)
        return
    await save_history(
        user_id=callback.from_user.id,
        skill=skill,
        inputs=data.get("save_inputs", {}),
        output=data["save_output"],
    )
    await state.clear()
    await callback.message.edit_text("Saved to your history!")
    await callback.answer()
