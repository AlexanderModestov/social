import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.services.claude_service import ClaudeService

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
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Great hook line\n\nBody paragraph.\n\n#tag1")]

    with patch("bot.services.claude_service.anthropic.AsyncAnthropic") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        service = ClaudeService()
        result = await service.generate_linkedin_post(
            notes="My notes here",
            scraped_content=["Article content here"],
            tone_profile={"voice_summary": "Direct"},
            previous_post=None
        )

    assert isinstance(result, str)
    assert len(result) > 0
