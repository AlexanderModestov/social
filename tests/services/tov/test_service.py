import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.services.tov.service import TovImportService
from bot.services.tov.errors import NoPostsError
from bot.services.tov.prompts import build_tov_prompt
from bot.db.channels import INSTAGRAM, TIKTOK, LINKEDIN


@pytest.mark.asyncio
async def test_analyze_returns_tov_dict():
    svc = TovImportService(apify_token="t", anthropic_api_key="k")
    fake_client = MagicMock()
    fake_client.fetch_profile_posts = MagicMock(return_value=[{"text": "hi there"}])

    with patch.object(svc, "_client", fake_client), \
         patch("bot.services.tov.service._generate_tov", return_value={"dos": ["x"]}):
        result = await svc.analyze(TIKTOK, "@alex")

    assert result["channel"] == TIKTOK
    assert result["handle"] == "alex"
    assert result["dos"] == ["x"]


@pytest.mark.asyncio
async def test_analyze_no_posts_raises():
    svc = TovImportService(apify_token="t", anthropic_api_key="k")
    fake_client = MagicMock()
    fake_client.fetch_profile_posts = MagicMock(return_value=[])
    with patch.object(svc, "_client", fake_client):
        with pytest.raises(NoPostsError):
            await svc.analyze(TIKTOK, "@alex")


@pytest.mark.parametrize("channel", [INSTAGRAM, TIKTOK, LINKEDIN])
def test_build_tov_prompt_all_channels(channel):
    data = {
        "total_posts": 2,
        "posts_with_text": 1,
        "avg_text_length": 8,
        "language_counts": {"ru": 0, "en": 1, "mixed": 0},
        "texts": [{"text": "hi there", "lang": "en", "likes": 3}],
    }
    prompt = build_tov_prompt(channel, "alex", data)
    assert isinstance(prompt, str) and prompt
    assert "@alex" in prompt
    assert "JSON" in prompt
