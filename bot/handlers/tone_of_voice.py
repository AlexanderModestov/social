# bot/handlers/tone_of_voice.py
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from bot.db.session import async_session_factory
from bot.db.repository import ToneOfVoiceRepository
from bot.keyboards.inline import style_words_keyboard, tone_of_voice_confirm_keyboard
from bot.services.claude_service import ClaudeService
from bot.states.states import ToneOfVoiceStates

router = Router()

@router.callback_query(lambda c: c.data == "action:tone_of_voice")
async def start_wizard(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ToneOfVoiceStates.waiting_role)
    await callback.message.edit_text(
        "Let's define your tone of voice.\n\n"
        "What's your professional role or what do you create content about?"
    )
    await callback.answer()

@router.message(ToneOfVoiceStates.waiting_role)
async def on_role(message: Message, state: FSMContext):
    await state.update_data(role=message.text)
    await state.set_state(ToneOfVoiceStates.waiting_audience)
    await message.answer("Who is your audience? Who reads or watches your content?")

@router.message(ToneOfVoiceStates.waiting_audience)
async def on_audience(message: Message, state: FSMContext):
    await state.update_data(audience=message.text, style_words=[])
    await state.set_state(ToneOfVoiceStates.waiting_style)
    await message.answer(
        "Pick words that describe your voice (select at least 2, then press Continue):",
        reply_markup=style_words_keyboard([]),
    )

@router.callback_query(ToneOfVoiceStates.waiting_style, F.data.startswith("style:"))
async def on_style_word(callback: CallbackQuery, state: FSMContext):
    word = callback.data.split(":")[1]
    if word == "done":
        data = await state.get_data()
        if len(data.get("style_words", [])) < 2:
            await callback.answer("Please select at least 2 words.", show_alert=True)
            return
        await state.set_state(ToneOfVoiceStates.waiting_examples)
        await callback.message.edit_text(
            "Share 1–3 examples of content you like (your own posts, articles, or just text).\n\n"
            "Send them one by one, then type /done."
        )
    else:
        data = await state.get_data()
        words = data.get("style_words", [])
        if word in words:
            words = [w for w in words if w != word]
        else:
            words = words + [word]
        await state.update_data(style_words=words)
        await callback.message.edit_reply_markup(reply_markup=style_words_keyboard(words))
    await callback.answer()

@router.message(ToneOfVoiceStates.waiting_examples, F.text != "/done")
async def on_example(message: Message, state: FSMContext):
    data = await state.get_data()
    examples = data.get("examples", [])
    examples.append(message.text)
    await state.update_data(examples=examples)
    count = len(examples)
    await message.answer(f"Got it ({count} example{'s' if count > 1 else ''} so far). Send more or type /done.")

@router.message(ToneOfVoiceStates.waiting_examples, F.text == "/done")
async def on_examples_done(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("examples"):
        await message.answer("Please share at least one example.")
        return

    await message.answer("Analyzing your style...")
    service = ClaudeService()
    try:
        profile = await service.generate_tone_of_voice(
            role=data["role"],
            audience=data["audience"],
            style_words=data["style_words"],
            examples=data["examples"],
        )
    except Exception as e:
        await message.answer(f"Error generating profile: {e}. Please try again.")
        return

    await state.update_data(generated_profile=profile)
    await state.set_state(ToneOfVoiceStates.confirming_profile)

    profile_text = (
        f"*Your tone of voice profile:*\n\n"
        f"*Voice:* {profile.get('voice_summary', '')}\n"
        f"*Style:* {', '.join(profile.get('tone_words', []))}\n"
        f"*Always:* {'; '.join(profile.get('always', []))}\n"
        f"*Avoid:* {'; '.join(profile.get('avoid', []))}\n"
        f"*Audience:* {profile.get('audience', '')}"
    )
    await message.answer(profile_text, parse_mode="Markdown", reply_markup=tone_of_voice_confirm_keyboard())

@router.callback_query(ToneOfVoiceStates.confirming_profile, F.data == "tov:save")
async def on_save_profile(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    async with async_session_factory() as session:
        repo = ToneOfVoiceRepository(session)
        await repo.create(
            user_id=callback.from_user.id,
            name=f"Profile {data['role'][:30]}",
            profile_json=data["generated_profile"],
        )
        await session.commit()
    await state.clear()
    await callback.message.edit_text("Profile saved! You're ready to create content.")
    await callback.answer()

@router.callback_query(ToneOfVoiceStates.confirming_profile, F.data == "tov:regenerate")
async def on_regenerate_profile(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text("Regenerating...")
    service = ClaudeService()
    profile = await service.generate_tone_of_voice(
        role=data["role"],
        audience=data["audience"],
        style_words=data["style_words"],
        examples=data["examples"],
    )
    await state.update_data(generated_profile=profile)
    profile_text = (
        f"*Your tone of voice profile:*\n\n"
        f"*Voice:* {profile.get('voice_summary', '')}\n"
        f"*Style:* {', '.join(profile.get('tone_words', []))}\n"
        f"*Always:* {'; '.join(profile.get('always', []))}\n"
        f"*Avoid:* {'; '.join(profile.get('avoid', []))}"
    )
    await callback.message.edit_text(profile_text, parse_mode="Markdown", reply_markup=tone_of_voice_confirm_keyboard())
    await callback.answer()
