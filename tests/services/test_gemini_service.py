import pytest
from unittest.mock import MagicMock, patch
from bot.services.gemini_service import GeminiService


@pytest.mark.asyncio
async def test_generate_video_calls_api():
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock()]

    with patch("bot.services.gemini_service.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        service = GeminiService()
        result = await service.generate_video(
            description="A fast-paced product demo",
            image_paths=[],
            tone_profile={"voice_summary": "Direct"}
        )

    mock_client.models.generate_content.assert_called_once()
    assert result is mock_response
