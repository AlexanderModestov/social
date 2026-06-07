import pytest
from unittest.mock import MagicMock, patch
from bot.services.instagram_tov_service import (
    InstagramTovService,
    PrivateProfileError,
    NoPostsError,
    ServiceError,
    _extract_username,
)

FAKE_POSTS = [{"caption": "Hello world", "likesCount": 10, "timestamp": "2024-01-01"}]

FAKE_PROFILE = {
    "username": "alex",
    "posts_analyzed": 1,
    "persona_summary": "Creative",
    "archetype": "Urban nomad",
    "voice_dimensions": [],
    "language": {"primary": "English ~100%", "secondary": None, "mixing_note": None},
    "caption_patterns": [],
    "motifs": {"themes": [], "places": [], "sensory": []},
    "dos": ["Be concise"],
    "donts": ["Avoid jargon"],
    "signature_elements": {"punctuation": "...", "hashtags": "rarely", "phrases": []},
}


# ── _extract_username ─────────────────────────────────────────────────────────

def test_extract_username_strips_at():
    assert _extract_username("@alex") == "alex"


def test_extract_username_parses_url():
    assert _extract_username("https://instagram.com/alex/") == "alex"


def test_extract_username_plain():
    assert _extract_username("alex") == "alex"


# ── InstagramTovService.analyze ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_returns_profile_on_success():
    with (
        patch("bot.services.instagram_tov_service._scrape_posts", return_value=FAKE_POSTS) as mock_scrape,
        patch("bot.services.instagram_tov_service._generate_tov", return_value=FAKE_PROFILE) as mock_gen,
    ):
        svc = InstagramTovService(apify_token="tok", anthropic_api_key="key")
        result = await svc.analyze("alex")

    mock_scrape.assert_called_once_with("alex", "tok")
    mock_gen.assert_called_once_with("alex", FAKE_POSTS, "key")
    assert result["username"] == "alex"


@pytest.mark.asyncio
async def test_analyze_strips_at_prefix():
    with (
        patch("bot.services.instagram_tov_service._scrape_posts", return_value=FAKE_POSTS),
        patch("bot.services.instagram_tov_service._generate_tov", return_value=FAKE_PROFILE),
    ):
        svc = InstagramTovService(apify_token="tok", anthropic_api_key="key")
        await svc.analyze("@alex")


@pytest.mark.asyncio
async def test_analyze_raises_no_posts_on_empty_result():
    with patch("bot.services.instagram_tov_service._scrape_posts", return_value=[]):
        svc = InstagramTovService(apify_token="tok", anthropic_api_key="key")
        with pytest.raises(NoPostsError):
            await svc.analyze("private_user")


@pytest.mark.asyncio
async def test_analyze_raises_service_error_on_scrape_failure():
    with patch(
        "bot.services.instagram_tov_service._scrape_posts",
        side_effect=RuntimeError("Apify failed"),
    ):
        svc = InstagramTovService(apify_token="tok", anthropic_api_key="key")
        with pytest.raises(ServiceError):
            await svc.analyze("alex")


@pytest.mark.asyncio
async def test_analyze_raises_service_error_on_generate_failure():
    with (
        patch("bot.services.instagram_tov_service._scrape_posts", return_value=FAKE_POSTS),
        patch(
            "bot.services.instagram_tov_service._generate_tov",
            side_effect=ValueError("bad JSON"),
        ),
    ):
        svc = InstagramTovService(apify_token="tok", anthropic_api_key="key")
        with pytest.raises(ServiceError):
            await svc.analyze("alex")
