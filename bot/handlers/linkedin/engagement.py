from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from bot.handlers.linkedin._shared import fetch_engagers, run_skill, report_card
from bot.services.linkedin import parse_linkedin_url
from bot.states.states import EngagementStates

router = Router()


@router.callback_query(F.data == "li:engagement-monitor")
async def start_engagement(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EngagementStates.waiting_input)
    await callback.message.edit_text(
        "Send a LinkedIn post URL. I'll pull its likers/commenters and group them by ICP fit."
    )
    await callback.answer()


@router.message(EngagementStates.waiting_input)
async def on_input(message: Message, state: FSMContext):
    url = (message.text or "").strip()
    if parse_linkedin_url(url)["url_type"] == "unknown":
        await message.answer("Send a valid LinkedIn post URL.")
        return
    engagers = await fetch_engagers(url)
    if engagers is None:
        await message.answer(
            "Engagement analysis needs an Apify token configured by the bot operator. "
            "It isn't available right now."
        )
        return
    if not engagers:
        await message.answer("No engagers found for that post (or it couldn't be read).")
        return
    report = await run_skill(
        "engagement-monitor", {"post_url": url, "engagers": engagers}, message.from_user.id
    )
    await state.update_data(
        save_skill="engagement-monitor",
        save_inputs={"post_url": url, "engager_count": len(engagers)},
        save_output=report,
    )
    card = report_card(report)
    await message.answer(card["text"], reply_markup=card["reply_markup"])
