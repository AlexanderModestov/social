import pytest
from unittest.mock import AsyncMock, MagicMock
from bot.services.linkedin.skill_service import LinkedInSkillService


@pytest.mark.asyncio
async def test_run_builds_prompt_and_returns_text():
    svc = LinkedInSkillService()

    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text="DRAFTED POST")]
    svc.client.messages.create = AsyncMock(return_value=fake_msg)

    out = await svc.run(
        skill="post-writer",
        user_inputs={"topic": "AI agencies", "notes": "be bold"},
        tov={"role": "founder"},
    )
    assert out == "DRAFTED POST"

    kwargs = svc.client.messages.create.call_args.kwargs
    assert "LinkedIn Post Writer" in kwargs["system"]      # skill prompt used
    assert "AI agencies" in kwargs["messages"][0]["content"]  # inputs passed
    assert kwargs["model"] == "claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_run_includes_previous_and_feedback():
    svc = LinkedInSkillService()
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text="REVISED")]
    svc.client.messages.create = AsyncMock(return_value=fake_msg)

    await svc.run(
        skill="post-writer",
        user_inputs={"topic": "x"},
        tov={},
        previous="OLD DRAFT",
        feedback="make it shorter",
    )
    user_content = svc.client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "OLD DRAFT" in user_content
    assert "make it shorter" in user_content


@pytest.mark.asyncio
async def test_run_uses_larger_token_budget_for_planner():
    svc = LinkedInSkillService()
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text="PLAN")]
    svc.client.messages.create = AsyncMock(return_value=fake_msg)
    await svc.run(skill="content-planner", user_inputs={"role": "founder"}, tov={})
    assert svc.client.messages.create.call_args.kwargs["max_tokens"] == 4096
