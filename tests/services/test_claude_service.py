import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.services.claude_service import ClaudeService
from bot.services.linkedin.skill_service import LinkedInSkillService

@pytest.mark.asyncio
async def test_generate_tone_of_voice_calls_api():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"voice_summary": "Direct and clear"}')]

    with patch("bot.services.claude_service.anthropic.AsyncAnthropic") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        service = ClaudeService()
        result = await service.generate_tone_of_voice(
            role="Product Manager",
            audience="Developers",
            style_words=["Direct", "Analytical"],
            examples=["Here's what I learned today..."]
        )

    assert "voice_summary" in result

@pytest.mark.asyncio
async def test_generate_linkedin_post_calls_api():
    with patch.object(
        LinkedInSkillService, "run", new=AsyncMock(return_value="Hook\n\nBody")
    ) as m:
        service = ClaudeService()
        result = await service.generate_linkedin_post(
            notes="My notes here",
            scraped_content=["Article content"],
            tone_profile={"voice_summary": "Direct"},
            previous_post=None,
        )

    assert result == "Hook\n\nBody"
    # verify delegation: called with skill "post-writer" and the reference_articles assembled
    args, kwargs = m.call_args
    assert args[0] == "post-writer" or kwargs.get("skill") == "post-writer"
    user_inputs = kwargs.get("user_inputs") or args[1]
    assert user_inputs["notes"] == "My notes here"
    assert "Article content" in user_inputs["reference_articles"]
