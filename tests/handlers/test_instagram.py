import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.handlers import instagram
from bot.db.channels import INSTAGRAM
from bot.states.states import InstagramStates, VeoStates
from tests.handlers._fakes import FakeMessage, FakeCallback, FakeFSMContext, fake_session_factory


@pytest.mark.asyncio
async def test_start_instagram_sets_waiting_subtype():
    state = FakeFSMContext()
    callback = FakeCallback(data="platform:instagram")
    await instagram.start_instagram(callback, state)
    assert state.state == InstagramStates.waiting_subtype
    callback.message.edit_text.assert_awaited()


@pytest.mark.asyncio
async def test_caption_done_with_photo_calls_gemini_and_clears():
    state = FakeFSMContext({"caption_photos": [{"type": "photo", "file_id": "f1"}]})
    message = FakeMessage(text="/done")
    fake_repo = MagicMock()
    fake_repo.get_for_channel = AsyncMock(return_value=None)
    with patch.object(instagram, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(instagram, "async_session_factory", fake_session_factory()), \
         patch.object(instagram, "_download_photos", AsyncMock(return_value=["/tmp/a.jpg"])), \
         patch.object(instagram, "_cleanup_photos") as cleanup, \
         patch.object(instagram, "GeminiService") as G:
        G.return_value.caption_from_photos = AsyncMock(return_value="my caption")
        await instagram.on_caption_done(message, state)

    fake_repo.get_for_channel.assert_awaited_with(message.from_user.id, INSTAGRAM)
    G.return_value.caption_from_photos.assert_awaited_once()
    cleanup.assert_called_once_with(["/tmp/a.jpg"])
    # caption sent as a plain message
    assert any("my caption" in c.args[0] for c in message.answer.await_args_list)
    assert state.state is None  # cleared


@pytest.mark.asyncio
async def test_caption_done_without_photos_stays():
    state = FakeFSMContext({"caption_photos": []})
    state.state = InstagramStates.collecting_caption_photos
    message = FakeMessage(text="/done")
    await instagram.on_caption_done(message, state)
    assert state.state == InstagramStates.collecting_caption_photos
    message.answer.assert_awaited()
    assert "photo" in message.answer.await_args.args[0].lower()


@pytest.mark.asyncio
async def test_scenario_clarify_stays_and_asks():
    state = FakeFSMContext({"scenario_context": ""})
    state.state = InstagramStates.scenario_developing
    message = FakeMessage(text="a reel about coffee")
    fake_repo = MagicMock()
    fake_repo.get_for_channel = AsyncMock(return_value=None)
    with patch.object(instagram, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(instagram, "async_session_factory", fake_session_factory()), \
         patch.object(instagram, "GeminiService") as G:
        G.return_value.develop_instagram_scenario = AsyncMock(
            return_value={"kind": "clarify", "question": "What vibe?"})
        await instagram.on_scenario_message(message, state)

    assert state.state == InstagramStates.scenario_developing
    assert any("What vibe?" in c.args[0] for c in message.answer.await_args_list)
    assert "ASSISTANT ASKED: What vibe?" in (await state.get_data())["scenario_context"]


@pytest.mark.asyncio
async def test_scenario_script_sets_ready_with_reel_keyboard():
    state = FakeFSMContext({"scenario_context": ""})
    state.state = InstagramStates.scenario_developing
    message = FakeMessage(text="a reel about coffee")
    fake_repo = MagicMock()
    fake_repo.get_for_channel = AsyncMock(return_value=None)
    with patch.object(instagram, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(instagram, "async_session_factory", fake_session_factory()), \
         patch.object(instagram, "GeminiService") as G:
        G.return_value.develop_instagram_scenario = AsyncMock(
            return_value={"kind": "script", "script": "HOOK then beats", "caption": "cap"})
        await instagram.on_scenario_message(message, state)

    assert state.state == InstagramStates.scenario_ready
    data = await state.get_data()
    assert data["scenario_script"] == "HOOK then beats"
    kb = message.answer.await_args.kwargs["reply_markup"]
    callbacks = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "ig:reel" in callbacks


@pytest.mark.asyncio
async def test_reel_handoff_seeds_state_and_enters_veo():
    state = FakeFSMContext({"scenario_script": "HOOK then beats"})
    state.state = InstagramStates.scenario_ready
    callback = FakeCallback(data="ig:reel")
    await instagram.on_scenario_reel(callback, state)
    assert state.state == VeoStates.choosing_video_mode
    data = await state.get_data()
    assert data["channel"] == INSTAGRAM
    assert data["description"] == "HOOK then beats"
    assert data["description_preset"] is True


@pytest.mark.asyncio
async def test_scenario_cancel_clears():
    state = FakeFSMContext({"scenario_context": "stuff"})
    state.state = InstagramStates.scenario_developing
    message = FakeMessage(text="/cancel")
    await instagram.on_scenario_message(message, state)
    assert state.state is None
    message.answer.assert_awaited()


@pytest.mark.asyncio
async def test_caption_done_gemini_error_cleans_up_and_clears():
    state = FakeFSMContext({"caption_photos": [{"type": "photo", "file_id": "f1"}]})
    state.state = InstagramStates.collecting_caption_photos
    message = FakeMessage(text="/done")
    fake_repo = MagicMock()
    fake_repo.get_for_channel = AsyncMock(return_value=None)
    with patch.object(instagram, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(instagram, "async_session_factory", fake_session_factory()), \
         patch.object(instagram, "_download_photos", AsyncMock(return_value=["/tmp/a.jpg"])), \
         patch.object(instagram, "_cleanup_photos") as cleanup, \
         patch.object(instagram, "GeminiService") as G:
        G.return_value.caption_from_photos = AsyncMock(side_effect=Exception("boom"))
        await instagram.on_caption_done(message, state)

    # temp files cleaned up despite the error
    cleanup.assert_called_once_with(["/tmp/a.jpg"])
    # an error message was sent
    assert any("boom" in c.args[0] for c in message.answer.await_args_list)
    # state cleared
    assert state.state is None


@pytest.mark.asyncio
async def test_scenario_gemini_error_stays_and_messages():
    state = FakeFSMContext({"scenario_context": ""})
    state.state = InstagramStates.scenario_developing
    message = FakeMessage(text="a reel about coffee")
    fake_repo = MagicMock()
    fake_repo.get_for_channel = AsyncMock(return_value=None)
    with patch.object(instagram, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(instagram, "async_session_factory", fake_session_factory()), \
         patch.object(instagram, "GeminiService") as G:
        G.return_value.develop_instagram_scenario = AsyncMock(side_effect=Exception("boom"))
        await instagram.on_scenario_message(message, state)

    # user stays in the developing state — no exception escaped
    assert state.state == InstagramStates.scenario_developing
    # an error message was sent
    assert any("boom" in c.args[0] for c in message.answer.await_args_list)
