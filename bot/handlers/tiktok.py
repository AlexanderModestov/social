# bot/handlers/tiktok.py
import os
import tempfile
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message, InlineKeyboardButton, InlineKeyboardMarkup
from bot.db.session import async_session_factory
from bot.db.repository import ToneOfVoiceRepository, PostHistoryRepository
from bot.keyboards.inline import tiktok_subtype_keyboard
from bot.services.claude_service import ClaudeService
from bot.services.gemini_service import GeminiService
from bot.services.playwright_service import PlaywrightService
from bot.services.scraper_service import ScraperService
from bot.states.states import TikTokStates

router = Router()

def _caption_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Yes, generate caption", callback_data="demo:caption")],
        [InlineKeyboardButton(text="No thanks", callback_data="demo:skip")],
    ])

@router.callback_query(lambda c: c.data == "platform:tiktok")
async def start_tiktok(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TikTokStates.waiting_subtype)
    await callback.message.edit_text(
        "What kind of TikTok video?",
        reply_markup=tiktok_subtype_keyboard(),
    )
    await callback.answer()

# --- Product Demo ---

@router.callback_query(TikTokStates.waiting_subtype, F.data == "tiktok:product_demo")
async def start_product_demo(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TikTokStates.waiting_product_url)
    await callback.message.edit_text("Send me the product URL to record.")
    await callback.answer()

@router.message(TikTokStates.waiting_product_url)
async def on_product_url(message: Message, state: FSMContext):
    url = message.text.strip()
    await state.set_state(TikTokStates.recording)
    await message.answer("Recording the demo... this may take 30–60 seconds.")

    service = PlaywrightService()
    try:
        video_path = await service.record_product_demo(url)
    except ValueError:
        await state.set_state(TikTokStates.waiting_product_url)
        await message.answer("Invalid URL. Please send a valid https:// link.")
        return
    except Exception as e:
        await state.clear()
        await message.answer(f"Recording failed: {e}. Please try again.")
        return

    video_file = FSInputFile(video_path)
    await message.answer_video(video_file, caption="Here's your product demo!")
    os.unlink(video_path)

    await state.update_data(recorded_url=url)
    await message.answer(
        "Want a TikTok caption for this video?",
        reply_markup=_caption_keyboard(),
    )

@router.callback_query(F.data == "demo:caption")
async def on_generate_caption(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    async with async_session_factory() as session:
        tov = await ToneOfVoiceRepository(session).get_active(callback.from_user.id)
    scraper = ScraperService()
    page_content = await scraper.scrape_url(data.get("recorded_url", ""))
    claude = ClaudeService()
    caption = await claude.generate_tiktok_caption(
        url=data.get("recorded_url", ""),
        page_content=page_content,
        tone_profile=tov.profile_json if tov else {},
    )
    await callback.message.answer(f"Caption:\n\n{caption}")
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "demo:skip")
async def on_skip_caption(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Done!")

# --- Video from Plot ---

@router.callback_query(TikTokStates.waiting_subtype, F.data == "tiktok:video_plot")
async def start_video_plot(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TikTokStates.waiting_description)
    await state.update_data(materials=[])
    await callback.message.edit_text("Describe your video idea.")
    await callback.answer()

@router.message(TikTokStates.waiting_description)
async def on_video_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(TikTokStates.collecting_materials)
    await message.answer(
        "Now send photos or materials to include (optional).\nType /done when ready."
    )

@router.message(TikTokStates.collecting_materials, F.photo)
async def on_material_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    materials = data.get("materials", [])
    file_id = message.photo[-1].file_id
    materials.append({"type": "photo", "file_id": file_id})
    await state.update_data(materials=materials)
    await message.answer(f"Got photo ({len(materials)} so far). Send more or /done.")

@router.message(TikTokStates.collecting_materials, F.text == "/done")
async def on_materials_done(message: Message, state: FSMContext):
    data = await state.get_data()
    await message.answer("Generating your video... this may take 1–2 minutes.")

    async with async_session_factory() as session:
        tov = await ToneOfVoiceRepository(session).get_active(message.from_user.id)

    image_paths = []
    bot = message.bot
    for material in data.get("materials", []):
        if material["type"] == "photo":
            file = await bot.get_file(material["file_id"])
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            await bot.download_file(file.file_path, destination=tmp.name)
            image_paths.append(tmp.name)

    gemini = GeminiService()
    try:
        response = await gemini.generate_video(
            description=data.get("description", ""),
            image_paths=image_paths,
            tone_profile=tov.profile_json if tov else {},
        )
        await message.answer("Video generated! (Gemini video output format may vary — check response for video data)")
    except Exception as e:
        await message.answer(f"Video generation failed: {e}")
    finally:
        for path in image_paths:
            os.unlink(path)
        await state.clear()
