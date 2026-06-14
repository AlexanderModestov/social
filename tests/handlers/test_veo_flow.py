import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.handlers import _veo_flow
from bot.db.channels import INSTAGRAM
from bot.states.states import VeoStates
from tests.handlers._fakes import FakeMessage, FakeCallback, FakeFSMContext, fake_session_factory


@pytest.mark.asyncio
async def test_on_video_mode_with_preset_flag_skips_to_materials():
    state = FakeFSMContext({"description": "a dog surfing", "description_preset": True})
    callback = FakeCallback(data="videomode:quick")
    await _veo_flow.on_video_mode(callback, state)
    assert state.state == VeoStates.collecting_materials
    callback.message.edit_text.assert_awaited()
    assert "photos" in callback.message.edit_text.await_args.args[0].lower()
    assert "describe your video idea" not in callback.message.edit_text.await_args.args[0].lower()
    # flag is consumed once the skip is taken
    assert (await state.get_data())["description_preset"] is False


@pytest.mark.asyncio
async def test_on_video_mode_with_residual_description_still_asks():
    # A residual description WITHOUT the explicit flag must NOT trigger the skip.
    state = FakeFSMContext({"description": "stale leftover idea"})
    callback = FakeCallback(data="videomode:quick")
    await _veo_flow.on_video_mode(callback, state)
    assert state.state == VeoStates.waiting_description
    callback.message.edit_text.assert_awaited_with("Describe your video idea.")


@pytest.mark.asyncio
async def test_veo_refine_uses_channel_from_state():
    state = FakeFSMContext({"channel": INSTAGRAM, "prompts": ["p"], "video_mode": "quick", "refine_context": ""})
    message = FakeMessage(text="make it brighter")
    fake_repo = MagicMock(); fake_repo.get_for_channel = AsyncMock(return_value=None)
    with patch.object(_veo_flow, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(_veo_flow, "async_session_factory", fake_session_factory()), \
         patch.object(_veo_flow, "GeminiService") as G:
        G.return_value.refine_veo_prompt = AsyncMock(return_value={"kind": "revision", "prompts": ["p2"]})
        await _veo_flow.on_prompt_refine_instruction(message, state)
    fake_repo.get_for_channel.assert_awaited_with(message.from_user.id, INSTAGRAM)
