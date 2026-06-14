# bot/handlers/instagram.py
"""Instagram content flow: photo -> caption, and scenario helper -> Reel (Veo)."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from bot.db.channels import INSTAGRAM
from bot.db.session import async_session_factory
from bot.db.repository import ToneOfVoiceRepository
from bot.handlers._veo_flow import _cleanup_photos, _download_photos, start_veo_flow
from bot.keyboards.inline import ig_generate_reel_keyboard, instagram_subtype_keyboard
from bot.services.gemini_service import GeminiService
from bot.states.states import InstagramStates

router = Router()


async def _ig_tov(user_id: int) -> dict:
    async with async_session_factory() as session:
        tov = await ToneOfVoiceRepository(session).get_for_channel(user_id, INSTAGRAM)
    return (tov.profile_json or {}) if tov else {}


@router.callback_query(F.data == "platform:instagram")
async def start_instagram(callback: CallbackQuery, state: FSMContext):
    await state.set_state(InstagramStates.waiting_subtype)
    await callback.message.edit_text(
        "What kind of Instagram content?",
        reply_markup=instagram_subtype_keyboard(),
    )
    await callback.answer()


# --- Caption from photos ---

@router.callback_query(InstagramStates.waiting_subtype, F.data == "ig:caption")
async def start_caption(callback: CallbackQuery, state: FSMContext):
    await state.set_state(InstagramStates.collecting_caption_photos)
    await state.update_data(caption_photos=[])
    await callback.message.edit_text("Send one or more photos, then /done.")
    await callback.answer()


@router.message(InstagramStates.collecting_caption_photos, F.photo)
async def on_caption_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("caption_photos", [])
    photos.append({"type": "photo", "file_id": message.photo[-1].file_id})
    await state.update_data(caption_photos=photos)
    await message.answer(f"Got photo ({len(photos)} so far). Send more or /done.")


@router.message(InstagramStates.collecting_caption_photos, F.text == "/done")
async def on_caption_done(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("caption_photos", [])
    if not photos:
        await message.answer("Send at least one photo first, then /done.")
        return

    await message.answer("Writing your caption…")
    tone_profile = await _ig_tov(message.from_user.id)
    image_paths = await _download_photos(message, photos)

    gemini = GeminiService()
    try:
        caption = await gemini.caption_from_photos(image_paths, tone_profile)
    except Exception as e:
        _cleanup_photos(image_paths)
        await state.clear()
        await message.answer(f"Couldn't write the caption: {e}")
        return

    _cleanup_photos(image_paths)
    await message.answer(f"Caption:\n\n{caption}")
    await state.clear()


# --- Scenario helper (clarify-loop) -> Reel ---

@router.callback_query(InstagramStates.waiting_subtype, F.data == "ig:scenario")
async def start_scenario(callback: CallbackQuery, state: FSMContext):
    await state.set_state(InstagramStates.scenario_developing)
    await state.update_data(scenario_context="")
    await callback.message.edit_text("Describe your Reel idea. Send /cancel to stop.")
    await callback.answer()


@router.message(InstagramStates.scenario_developing)
async def on_scenario_message(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text == "/cancel":
        await state.clear()
        await message.answer("Cancelled.")
        return
    if not text or text.startswith("/"):
        await message.answer("Send a plain-language description, or /cancel to stop.")
        return

    data = await state.get_data()
    prev = data.get("scenario_context", "")
    scenario_context = f"{prev}\n{text}".strip() if prev else text
    await state.update_data(scenario_context=scenario_context)

    tone_profile = await _ig_tov(message.from_user.id)

    gemini = GeminiService()
    try:
        result = await gemini.develop_instagram_scenario(
            idea=text, history=scenario_context, tone_profile=tone_profile,
        )
    except Exception as e:
        await message.answer(f"Couldn't develop that: {e}\n\nTry describing it again, or /cancel.")
        return

    if result["kind"] == "clarify":
        question = result["question"]
        await state.update_data(scenario_context=f"{scenario_context}\nASSISTANT ASKED: {question}")
        await message.answer(question)
        return  # stay in scenario_developing to receive the answer

    script = result["script"]
    caption = result.get("caption", "")
    await state.update_data(scenario_script=script, scenario_caption=caption)
    await state.set_state(InstagramStates.scenario_ready)
    body = f"Here's your Reel script:\n\n{script}"
    if caption:
        body += f"\n\nCaption:\n\n{caption}"
    await message.answer(body, reply_markup=ig_generate_reel_keyboard())


@router.callback_query(InstagramStates.scenario_ready, F.data == "ig:reel")
async def on_scenario_reel(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    # Pass the script through the param; start_veo_flow owns description/description_preset.
    await start_veo_flow(callback, state, channel=INSTAGRAM, description=data.get("scenario_script", ""))


@router.callback_query(InstagramStates.scenario_ready, F.data == "ig:script_done")
async def on_scenario_done(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Saved your script.")
    await callback.answer()
