import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.handlers import tone_of_voice as tov
from bot.db.channels import INSTAGRAM, TIKTOK, CHANNEL_LABELS
from bot.states.states import ToneOfVoiceStates
from tests.handlers._fakes import (
    FakeMessage,
    FakeCallback,
    FakeFSMContext,
    fake_session_factory,
)


@pytest.mark.asyncio
async def test_on_create_tov_shows_picker_and_sets_choosing_channel():
    state = FakeFSMContext()
    callback = FakeCallback(data="action:tone_of_voice")

    fake_repo = MagicMock()
    fake_repo.get_channels_with_tov = AsyncMock(return_value=set())

    with patch.object(tov, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(tov, "async_session_factory", fake_session_factory()):
        await tov.on_create_tov(callback, state)

    assert state.state == ToneOfVoiceStates.choosing_channel
    callback.message.edit_text.assert_awaited()
    kb = callback.message.edit_text.await_args.kwargs["reply_markup"]
    cbs = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert all(c.startswith("tovchan:") for c in cbs)
    assert len(cbs) == 3  # no channels have tov yet


@pytest.mark.asyncio
async def test_channel_picked_stores_channel_and_sets_choosing_method():
    state = FakeFSMContext()
    callback = FakeCallback(data=f"tovchan:{INSTAGRAM}")

    await tov.on_channel_picked(callback, state)

    assert (await state.get_data())["channel"] == INSTAGRAM
    assert state.state == ToneOfVoiceStates.choosing_method
    kb = callback.message.edit_text.await_args.kwargs["reply_markup"]
    cbs = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert f"tovm:wizard:{INSTAGRAM}" in cbs
    assert f"tovm:import:{INSTAGRAM}" in cbs


@pytest.mark.asyncio
async def test_wizard_chosen_parses_channel_and_goes_to_waiting_role():
    state = FakeFSMContext()
    callback = FakeCallback(data=f"tovm:wizard:{TIKTOK}")

    await tov.on_wizard_chosen(callback, state)

    assert (await state.get_data())["channel"] == TIKTOK
    assert state.state == ToneOfVoiceStates.waiting_role


@pytest.mark.asyncio
async def test_save_profile_upserts_with_channel_from_state():
    state = FakeFSMContext({
        "channel": TIKTOK,
        "role": "creator",
        "generated_profile": {"voice_summary": "x"},
    })
    callback = FakeCallback(data="tov:save")

    fake_repo = MagicMock()
    fake_repo.upsert = AsyncMock()
    fake_repo.get_channels_with_tov = AsyncMock(return_value={TIKTOK})

    with patch.object(tov, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(tov, "async_session_factory", fake_session_factory()):
        await tov.on_save_profile(callback, state)

    fake_repo.upsert.assert_awaited_once()
    kwargs = fake_repo.upsert.await_args.kwargs
    assert kwargs["channel"] == TIKTOK
    assert kwargs["name"] == f"{CHANNEL_LABELS[TIKTOK]} voice"
    assert kwargs["profile_json"] == {"voice_summary": "x"}


@pytest.mark.asyncio
async def test_save_profile_reshows_picker_when_channels_missing():
    state = FakeFSMContext({
        "channel": TIKTOK,
        "generated_profile": {"voice_summary": "x"},
    })
    callback = FakeCallback(data="tov:save")

    fake_repo = MagicMock()
    fake_repo.upsert = AsyncMock()
    fake_repo.get_channels_with_tov = AsyncMock(return_value={TIKTOK})  # IG/LI missing

    with patch.object(tov, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(tov, "async_session_factory", fake_session_factory()):
        await tov.on_save_profile(callback, state)

    assert state.state == ToneOfVoiceStates.choosing_channel
    # The picker is re-shown via a fresh answer (edit_text is the "saved" notice).
    kb = callback.message.answer.await_args.kwargs["reply_markup"]
    cbs = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert all(c.startswith("tovchan:") for c in cbs)
    assert cbs  # IG + LI still missing


@pytest.mark.asyncio
async def test_import_chosen_sets_waiting_import_handle():
    state = FakeFSMContext()
    callback = FakeCallback(data=f"tovm:import:{INSTAGRAM}")

    with patch.object(tov.settings, "apify_token", "token-123"):
        await tov.on_import_chosen(callback, state)

    assert (await state.get_data())["channel"] == INSTAGRAM
    assert state.state == ToneOfVoiceStates.waiting_import_handle


@pytest.mark.asyncio
async def test_import_chosen_alerts_when_apify_not_configured():
    state = FakeFSMContext()
    callback = FakeCallback(data=f"tovm:import:{INSTAGRAM}")

    with patch.object(tov.settings, "apify_token", ""):
        await tov.on_import_chosen(callback, state)

    callback.answer.assert_awaited()
    assert callback.answer.await_args.kwargs.get("show_alert") is True
    assert state.state != ToneOfVoiceStates.waiting_import_handle


@pytest.mark.asyncio
async def test_import_handle_calls_analyze_with_channel_and_upserts():
    state = FakeFSMContext({"channel": TIKTOK})
    message = FakeMessage(text="@somebody")

    profile = {"handle": "somebody", "posts_analyzed": 12, "voice_summary": "v"}
    fake_svc = MagicMock()
    fake_svc.analyze = AsyncMock(return_value=profile)

    fake_repo = MagicMock()
    fake_repo.upsert = AsyncMock()
    fake_repo.get_channels_with_tov = AsyncMock(return_value={TIKTOK, INSTAGRAM})

    with patch.object(tov.settings, "apify_token", "token-123"), \
         patch.object(tov.settings, "anthropic_api_key", "key"), \
         patch.object(tov, "TovImportService", return_value=fake_svc), \
         patch.object(tov, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(tov, "async_session_factory", fake_session_factory()):
        await tov.on_import_handle(message, state)

    fake_svc.analyze.assert_awaited_once_with(TIKTOK, "@somebody")
    fake_repo.upsert.assert_awaited_once()
    kwargs = fake_repo.upsert.await_args.kwargs
    assert kwargs["channel"] == TIKTOK
    assert kwargs["profile_json"] == profile
    assert "somebody" in kwargs["name"]


@pytest.mark.asyncio
async def test_import_handle_blank_handle_value_error_stays_in_state():
    state = FakeFSMContext({"channel": TIKTOK})
    state.state = ToneOfVoiceStates.waiting_import_handle  # entered the import step
    message = FakeMessage(text="   ")

    fake_svc = MagicMock()
    fake_svc.analyze = AsyncMock(side_effect=ValueError("blank handle"))

    fake_repo = MagicMock()
    fake_repo.upsert = AsyncMock()

    with patch.object(tov.settings, "apify_token", "token-123"), \
         patch.object(tov.settings, "anthropic_api_key", "key"), \
         patch.object(tov, "TovImportService", return_value=fake_svc), \
         patch.object(tov, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(tov, "async_session_factory", fake_session_factory()):
        # must NOT raise
        await tov.on_import_handle(message, state)

    fake_repo.upsert.assert_not_awaited()
    # stays in the import state for a retry
    assert state.state == ToneOfVoiceStates.waiting_import_handle
    message.answer.assert_awaited()


@pytest.mark.asyncio
async def test_import_handle_instagram_uses_rich_formatter():
    state = FakeFSMContext({"channel": INSTAGRAM})
    message = FakeMessage(text="@ig")

    profile = {"handle": "ig", "username": "ig", "posts_analyzed": 5}
    fake_svc = MagicMock()
    fake_svc.analyze = AsyncMock(return_value=profile)

    fake_repo = MagicMock()
    fake_repo.upsert = AsyncMock()
    fake_repo.get_channels_with_tov = AsyncMock(return_value=set())

    with patch.object(tov.settings, "apify_token", "token-123"), \
         patch.object(tov.settings, "anthropic_api_key", "key"), \
         patch.object(tov, "TovImportService", return_value=fake_svc), \
         patch.object(tov, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(tov, "async_session_factory", fake_session_factory()), \
         patch.object(tov, "format_instagram_profile", return_value="RICH") as fmt:
        await tov.on_import_handle(message, state)

    fmt.assert_called_once_with(profile)
