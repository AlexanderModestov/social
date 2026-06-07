import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.services.instagram_tov_service import (
    InstagramTovService,
    PrivateProfileError,
    NoPostsError,
    ServiceError,
)

FAKE_PROFILE = {
    "username": "alex",
    "posts_analyzed": 10,
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


@pytest.mark.asyncio
async def test_analyze_returns_profile_on_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = FAKE_PROFILE
    mock_response.raise_for_status = MagicMock()

    with patch("bot.services.instagram_tov_service.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        svc = InstagramTovService(base_url="http://localhost:8000")
        result = await svc.analyze("alex")

    assert result["username"] == "alex"
    assert result["posts_analyzed"] == 10


@pytest.mark.asyncio
async def test_analyze_raises_private_profile_on_404():
    mock_response = MagicMock()
    mock_response.status_code = 404

    import httpx
    with patch("bot.services.instagram_tov_service.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError("not found", request=MagicMock(), response=mock_response)
        )

        svc = InstagramTovService(base_url="http://localhost:8000")
        with pytest.raises(PrivateProfileError):
            await svc.analyze("private_user")


@pytest.mark.asyncio
async def test_analyze_raises_no_posts_on_404_with_no_posts_message():
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {"detail": "No posts found"}

    import httpx
    with patch("bot.services.instagram_tov_service.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError("not found", request=MagicMock(), response=mock_response)
        )

        svc = InstagramTovService(base_url="http://localhost:8000")
        with pytest.raises(NoPostsError):
            await svc.analyze("empty_user")


@pytest.mark.asyncio
async def test_analyze_raises_service_error_on_502():
    mock_response = MagicMock()
    mock_response.status_code = 502

    import httpx
    with patch("bot.services.instagram_tov_service.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError("bad gateway", request=MagicMock(), response=mock_response)
        )

        svc = InstagramTovService(base_url="http://localhost:8000")
        with pytest.raises(ServiceError):
            await svc.analyze("alex")


@pytest.mark.asyncio
async def test_analyze_raises_service_error_on_connect_error():
    import httpx
    with patch("bot.services.instagram_tov_service.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

        svc = InstagramTovService(base_url="http://localhost:8000")
        with pytest.raises(ServiceError):
            await svc.analyze("alex")
