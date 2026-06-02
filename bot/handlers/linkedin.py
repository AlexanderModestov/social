# bot/handlers/linkedin.py
import re
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from bot.db.session import async_session_factory
from bot.db.repository import ToneOfVoiceRepository, PostHistoryRepository
from bot.keyboards.inline import post_actions_keyboard
from bot.services.claude_service import ClaudeService
from bot.services.scraper_service import ScraperService
from bot.states.states import LinkedInStates

router = Router()
URL_REGEX = re.compile(r"https?://\S+")

@router.callback_query(lambda c: c.data == "platform:linkedin")
async def start_linkedin(callback: CallbackQuery, state: FSMContext):
    await state.set_state(LinkedInStates.collecting_inputs)
    await state.update_data(links=[], notes=[], generated_post=None)
    await callback.message.edit_text(
        "Send me links and/or your notes for the post.\n\n"
        "You can send multiple messages. Type /done when finished."
    )
    await callback.answer()

@router.message(LinkedInStates.collecting_inputs, F.text != "/done")
async def on_input(message: Message, state: FSMContext):
    data = await state.get_data()
    urls = URL_REGEX.findall(message.text or "")
    if urls:
        links = data.get("links", []) + urls
        await state.update_data(links=links)
        await message.answer(f"Got {len(urls)} link(s). Send more or /done.")
    else:
        notes = data.get("notes", [])
        notes.append(message.text)
        await state.update_data(notes=notes)
        await message.answer("Got your notes. Send more or /done.")

@router.message(LinkedInStates.collecting_inputs, F.text == "/done")
async def on_done(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("links") and not data.get("notes"):
        await message.answer("Please send at least one link or note first.")
        return

    await message.answer("Fetching content and generating your post...")

    async with async_session_factory() as session:
        tov = await ToneOfVoiceRepository(session).get_active(message.from_user.id)

    tone_profile = tov.profile_json if tov else {}

    scraper = ScraperService()
    scraped = await scraper.scrape_urls(data.get("links", []))
    notes_text = "\n\n".join(data.get("notes", []))

    claude = ClaudeService()
    post = await claude.generate_linkedin_post(
        notes=notes_text,
        scraped_content=scraped,
        tone_profile=tone_profile,
    )

    await state.update_data(generated_post=post)
    await state.set_state(LinkedInStates.editing)
    await message.answer(post, reply_markup=post_actions_keyboard())

@router.callback_query(LinkedInStates.editing, F.data == "post:regenerate")
async def on_regenerate(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    async with async_session_factory() as session:
        tov = await ToneOfVoiceRepository(session).get_active(callback.from_user.id)
    scraper = ScraperService()
    scraped = await scraper.scrape_urls(data.get("links", []))
    claude = ClaudeService()
    post = await claude.generate_linkedin_post(
        notes="\n\n".join(data.get("notes", [])),
        scraped_content=scraped,
        tone_profile=tov.profile_json if tov else {},
    )
    await state.update_data(generated_post=post)
    await callback.message.edit_text(post, reply_markup=post_actions_keyboard())
    await callback.answer()

@router.callback_query(LinkedInStates.editing, F.data == "post:edit")
async def on_edit(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Tell me what to change (e.g. 'make it shorter, remove hashtags'):")
    await callback.answer()

@router.message(LinkedInStates.editing)
async def on_edit_feedback(message: Message, state: FSMContext):
    data = await state.get_data()
    async with async_session_factory() as session:
        tov = await ToneOfVoiceRepository(session).get_active(message.from_user.id)
    scraper = ScraperService()
    scraped = await scraper.scrape_urls(data.get("links", []))
    claude = ClaudeService()
    post = await claude.generate_linkedin_post(
        notes="\n\n".join(data.get("notes", [])),
        scraped_content=scraped,
        tone_profile=tov.profile_json if tov else {},
        previous_post=data.get("generated_post"),
        feedback=message.text,
    )
    await state.update_data(generated_post=post)
    await message.answer(post, reply_markup=post_actions_keyboard())

@router.callback_query(LinkedInStates.editing, F.data == "post:save")
async def on_save(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    async with async_session_factory() as session:
        repo = PostHistoryRepository(session)
        await repo.create(
            user_id=callback.from_user.id,
            platform="linkedin",
            format="post",
            input_data={"links": data.get("links", []), "notes": data.get("notes", [])},
            output_data={"post": data.get("generated_post")},
        )
        await session.commit()
    await state.clear()
    await callback.message.edit_text("Post saved to your history!")
    await callback.answer()
