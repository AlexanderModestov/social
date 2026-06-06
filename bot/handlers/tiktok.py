# bot/handlers/tiktok.py
import os
import shutil
import tempfile
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message, InlineKeyboardButton, InlineKeyboardMarkup
from bot.db.session import async_session_factory
from bot.db.repository import ToneOfVoiceRepository
from bot.keyboards.inline import tiktok_subtype_keyboard, video_mode_keyboard, prompt_review_keyboard
from bot.services.claude_service import ClaudeService
from bot.services.gemini_service import GeminiService
from bot.services.playwright_service import PlaywrightService
from bot.services.scraper_service import ScraperService
from bot.services.veo_service import VeoService
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

# --- Video from Plot (Veo) ---

@router.callback_query(TikTokStates.waiting_subtype, F.data == "tiktok:video_plot")
async def start_video_plot(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TikTokStates.choosing_video_mode)
    await callback.message.edit_text(
        "What kind of video?", reply_markup=video_mode_keyboard(),
    )
    await callback.answer()


@router.callback_query(TikTokStates.choosing_video_mode, F.data.startswith("videomode:"))
async def on_video_mode(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.split(":")[1]  # "quick" | "full"
    await state.update_data(video_mode=mode, materials=[])
    await state.set_state(TikTokStates.waiting_description)
    await callback.message.edit_text("Describe your video idea.")
    await callback.answer()


@router.message(TikTokStates.waiting_description)
async def on_video_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(TikTokStates.collecting_materials)
    await message.answer(
        "Now send photos to include (optional).\nType /done when ready."
    )


@router.message(TikTokStates.collecting_materials, F.photo)
async def on_material_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    materials = data.get("materials", [])
    materials.append({"type": "photo", "file_id": message.photo[-1].file_id})
    await state.update_data(materials=materials)
    await message.answer(f"Got photo ({len(materials)} so far). Send more or /done.")


async def _download_photos(message: Message, materials: list[dict]) -> list[str]:
    paths = []
    for material in materials:
        if material["type"] == "photo":
            file = await message.bot.get_file(material["file_id"])
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            await message.bot.download_file(file.file_path, destination=tmp.name)
            paths.append(tmp.name)
    return paths


@router.message(TikTokStates.collecting_materials, F.text == "/done")
async def on_materials_done(message: Message, state: FSMContext):
    data = await state.get_data()
    await message.answer("Writing your video prompt…")

    async with async_session_factory() as session:
        tov = await ToneOfVoiceRepository(session).get_active(message.from_user.id)
    tone_profile = tov.profile_json if tov else {}

    image_paths = await _download_photos(message, data.get("materials", []))
    await state.update_data(image_paths=image_paths)

    gemini = GeminiService()
    try:
        if data.get("video_mode") == "full":
            scenes = await gemini.write_veo_scenes(
                data.get("description", ""), image_paths, tone_profile,
            )
            await state.update_data(prompts=scenes)
            preview = "\n".join(f"Scene {i+1}: {s}" for i, s in enumerate(scenes))
        else:
            prompt = await gemini.write_veo_prompt(
                data.get("description", ""), image_paths, tone_profile,
            )
            await state.update_data(prompts=[prompt])
            preview = prompt
    except Exception as e:
        for p in image_paths:
            if os.path.exists(p):
                os.unlink(p)
        await state.clear()
        await message.answer(f"Couldn't write the prompt: {e}")
        return

    await state.set_state(TikTokStates.reviewing_prompt)
    await message.answer(
        f"Here's the video prompt:\n\n{preview}\n\nAccept it or edit?",
        reply_markup=prompt_review_keyboard(),
    )


@router.callback_query(TikTokStates.reviewing_prompt, F.data == "veo:edit")
async def on_prompt_edit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TikTokStates.editing_prompt)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "Send the corrected prompt. For a full video, separate scenes with blank lines."
    )
    await callback.answer()


@router.message(TikTokStates.editing_prompt)
async def on_prompt_edited(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        await message.answer("Please send the corrected prompt text (not a command).")
        return
    data = await state.get_data()
    if data.get("video_mode") == "full":
        prompts = [p.strip() for p in text.split("\n\n") if p.strip()][:3]
    else:
        prompts = [text]
    await state.update_data(prompts=prompts)
    await _run_veo(message, state)


@router.callback_query(TikTokStates.reviewing_prompt, F.data == "veo:accept")
async def on_prompt_accept(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await _run_veo(callback.message, state)


def _cleanup_photos(image_paths: list[str]):
    for p in image_paths:
        if os.path.exists(p):
            os.unlink(p)


async def _run_veo(message: Message, state: FSMContext):
    data = await state.get_data()
    prompts = data.get("prompts", [])
    image_paths = data.get("image_paths", [])
    seed = image_paths[0] if image_paths else None

    if not prompts:
        await state.set_state(TikTokStates.reviewing_prompt)
        await message.answer(
            "The prompt was empty — edit it and try again.",
            reply_markup=prompt_review_keyboard(),
        )
        return

    await state.set_state(TikTokStates.generating_veo)
    await message.answer("🎬 Generating your video… this takes a few minutes.")

    veo = VeoService()
    try:
        if data.get("video_mode") == "full":
            video_path = await veo.generate_and_stitch(prompts, seed_image_path=seed)
        else:
            video_path = await veo.generate_clip(prompts[0], seed_image_path=seed)
    except FileNotFoundError:
        # ffmpeg missing is a server-config problem, not fixable by editing — abort cleanly.
        _cleanup_photos(image_paths)
        await state.clear()
        await message.answer("Video stitching needs ffmpeg installed on the server.")
        return
    except Exception as e:
        # Retryable: keep prompts + seed photos, return to the review gate.
        await state.set_state(TikTokStates.reviewing_prompt)
        await message.answer(
            f"Video generation failed: {e}\n\nEdit the prompt and try again.",
            reply_markup=prompt_review_keyboard(),
        )
        return

    await message.answer_video(FSInputFile(video_path), caption="Here's your video!")
    shutil.rmtree(os.path.dirname(video_path), ignore_errors=True)
    _cleanup_photos(image_paths)
    await state.clear()
