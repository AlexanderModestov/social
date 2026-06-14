# bot/handlers/_veo_flow.py
"""Shared Veo video flow (video-mode -> description -> materials -> prompt review
-> refine/edit/accept -> generate). Parametrized by channel via FSM state, so it
can be driven by TikTok, Instagram, or any future channel."""
import os
import shutil
import tempfile
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message
from bot.config import settings
from bot.db.channels import TIKTOK
from bot.db.session import async_session_factory
from bot.db.repository import ToneOfVoiceRepository
from bot.keyboards.inline import video_mode_keyboard, prompt_review_keyboard
from bot.services.gemini_service import GeminiService
from bot.services.veo_service import VeoService
from bot.states.states import VeoStates

router = Router()


async def start_veo_flow(
    callback: CallbackQuery, state: FSMContext, *, channel: str, description: str | None = None
):
    await state.update_data(
        channel=channel,
        description=description or "",
        description_preset=bool(description),
        video_mode=None,
        materials=[],
        prompts=[],
        image_paths=[],
        refine_context="",
    )
    await state.set_state(VeoStates.choosing_video_mode)
    await callback.message.edit_text(
        "What kind of video?", reply_markup=video_mode_keyboard(),
    )
    await callback.answer()


@router.callback_query(VeoStates.choosing_video_mode, F.data.startswith("videomode:"))
async def on_video_mode(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.split(":")[1]  # "quick" | "full"
    await state.update_data(video_mode=mode, materials=[])
    data = await state.get_data()
    if data.get("description_preset"):
        # description explicitly supplied (e.g. Instagram scenario handoff) — skip the ask
        await state.update_data(description_preset=False)
        await state.set_state(VeoStates.collecting_materials)
        await callback.message.edit_text(
            "Now send photos to include (optional).\nType /done when ready."
        )
    else:
        await state.set_state(VeoStates.waiting_description)
        await callback.message.edit_text("Describe your video idea.")
    await callback.answer()


@router.message(VeoStates.waiting_description)
async def on_video_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(VeoStates.collecting_materials)
    await message.answer(
        "Now send photos to include (optional).\nType /done when ready."
    )


@router.message(VeoStates.collecting_materials, F.photo)
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


@router.message(VeoStates.collecting_materials, F.text == "/done")
async def on_materials_done(message: Message, state: FSMContext):
    data = await state.get_data()
    channel = data.get("channel", TIKTOK)
    await message.answer("Writing your video prompt…")

    async with async_session_factory() as session:
        tov = await ToneOfVoiceRepository(session).get_for_channel(message.from_user.id, channel)
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
        else:
            prompt = await gemini.write_veo_prompt(
                data.get("description", ""), image_paths, tone_profile,
            )
            await state.update_data(prompts=[prompt])
    except Exception as e:
        for p in image_paths:
            if os.path.exists(p):
                os.unlink(p)
        await state.clear()
        await message.answer(f"Couldn't write the prompt: {e}")
        return

    await _show_prompt_review(message, state)


@router.callback_query(VeoStates.reviewing_prompt, F.data == "veo:edit")
async def on_prompt_edit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(VeoStates.editing_prompt)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "Send the corrected prompt. For a full video, separate scenes with blank lines."
    )
    await callback.answer()


@router.message(VeoStates.editing_prompt)
async def on_prompt_edited(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        await message.answer("Please send the corrected prompt text (not a command).")
        return
    data = await state.get_data()
    if data.get("video_mode") == "full":
        prompts = [p.strip() for p in text.split("\n\n") if p.strip()][: settings.veo_max_scenes]
    else:
        prompts = [text]
    await state.update_data(prompts=prompts)
    await _run_veo(message, state)


@router.callback_query(VeoStates.reviewing_prompt, F.data == "veo:refine")
async def on_prompt_refine(callback: CallbackQuery, state: FSMContext):
    await state.set_state(VeoStates.refining_prompt)
    await state.update_data(refine_context="")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "What should I change? e.g. \"more energetic, sunset lighting, slower camera\".\n"
        "Send /cancel to go back."
    )
    await callback.answer()


@router.message(VeoStates.refining_prompt)
async def on_prompt_refine_instruction(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text == "/cancel":
        await state.update_data(refine_context="")
        await _show_prompt_review(message, state)
        return
    if not text or text.startswith("/"):
        await message.answer("Send a plain-language instruction, or /cancel to go back.")
        return
    data = await state.get_data()
    channel = data.get("channel", TIKTOK)
    prev = data.get("refine_context", "")
    refine_context = f"{prev}\n{text}".strip() if prev else text

    async with async_session_factory() as session:
        tov = await ToneOfVoiceRepository(session).get_for_channel(message.from_user.id, channel)
    tone_profile = tov.profile_json if tov else {}

    gemini = GeminiService()
    try:
        result = await gemini.refine_veo_prompt(
            current_prompts=data.get("prompts", []),
            instruction=refine_context,
            tone_profile=tone_profile,
            mode=data.get("video_mode", "quick"),
        )
    except Exception as e:
        await state.update_data(refine_context="")
        await _show_prompt_review(message, state)
        await message.answer(f"Couldn't refine that: {e}")
        return

    if result["kind"] == "clarify":
        question = result["question"]
        await state.update_data(refine_context=f"{refine_context}\nASSISTANT ASKED: {question}")
        await message.answer(question)
        return  # stay in refining_prompt to receive the answer

    await state.update_data(prompts=result["prompts"], refine_context="")
    await _show_prompt_review(message, state)


@router.callback_query(VeoStates.reviewing_prompt, F.data == "veo:accept")
async def on_prompt_accept(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await _run_veo(callback.message, state)


def _cleanup_photos(image_paths: list[str]):
    for p in image_paths:
        if os.path.exists(p):
            os.unlink(p)


async def _show_prompt_review(message: Message, state: FSMContext):
    data = await state.get_data()
    prompts = data.get("prompts", [])
    if data.get("video_mode") == "full":
        preview = "\n".join(f"Scene {i+1}: {p}" for i, p in enumerate(prompts))
    else:
        preview = prompts[0] if prompts else ""
    await state.set_state(VeoStates.reviewing_prompt)
    await message.answer(
        f"Here's the video prompt:\n\n{preview}\n\nAccept it, refine, or rewrite?",
        reply_markup=prompt_review_keyboard(),
    )


async def _run_veo(message: Message, state: FSMContext):
    data = await state.get_data()
    prompts = data.get("prompts", [])
    image_paths = data.get("image_paths", [])
    seed = image_paths[0] if image_paths else None

    if not prompts:
        await state.set_state(VeoStates.reviewing_prompt)
        await message.answer(
            "The prompt was empty — edit it and try again.",
            reply_markup=prompt_review_keyboard(),
        )
        return

    await state.set_state(VeoStates.generating_veo)
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
        await state.set_state(VeoStates.reviewing_prompt)
        await message.answer(
            f"Video generation failed: {e}\n\nEdit the prompt and try again.",
            reply_markup=prompt_review_keyboard(),
        )
        return

    await message.answer_video(FSInputFile(video_path), caption="Here's your video!")
    shutil.rmtree(os.path.dirname(video_path), ignore_errors=True)
    _cleanup_photos(image_paths)
    await state.clear()
