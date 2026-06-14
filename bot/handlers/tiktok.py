# bot/handlers/tiktok.py
import os
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message, InlineKeyboardButton, InlineKeyboardMarkup
from bot.db.channels import TIKTOK
from bot.db.session import async_session_factory
from bot.db.repository import ToneOfVoiceRepository
from bot.handlers._veo_flow import start_veo_flow
from bot.keyboards.inline import tiktok_subtype_keyboard
from bot.services.claude_service import ClaudeService
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
        tov = await ToneOfVoiceRepository(session).get_for_channel(callback.from_user.id, TIKTOK)
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

# --- Video from Plot (Veo) ---

@router.callback_query(TikTokStates.waiting_subtype, F.data == "tiktok:video_plot")
async def start_video_plot(callback: CallbackQuery, state: FSMContext):
    await start_veo_flow(callback, state, channel=TIKTOK)
