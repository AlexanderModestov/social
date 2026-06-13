"""Behavior tests for the Instagram TOV back-compat wrapper.

``InstagramTovService`` now delegates to the shared ``TovImportService``; these
tests pin the wrapper's contract (delegation to the INSTAGRAM channel, the
``username`` back-compat key, error propagation) rather than the old
hand-rolled internals.
"""
import pytest
from unittest.mock import AsyncMock, patch

from bot.db.channels import INSTAGRAM
from bot.services.instagram_tov_service import (
    InstagramTovService,
    PrivateProfileError,
    NoPostsError,
    ServiceError,
)

FAKE_RESULT = {
    "channel": INSTAGRAM,
    "handle": "alex",
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


# ── error re-exports ──────────────────────────────────────────────────────────

def test_errors_are_reexported_from_shared_module():
    from bot.services.tov import errors as shared
    assert PrivateProfileError is shared.PrivateProfileError
    assert NoPostsError is shared.NoPostsError
    assert ServiceError is shared.ServiceError


# ── InstagramTovService.analyze ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_delegates_to_instagram_channel():
    with patch(
        "bot.services.instagram_tov_service.TovImportService.analyze",
        new=AsyncMock(return_value=dict(FAKE_RESULT)),
    ) as mock_analyze:
        svc = InstagramTovService(apify_token="tok", anthropic_api_key="key")
        result = await svc.analyze("alex")

    mock_analyze.assert_awaited_once_with(INSTAGRAM, "alex")
    assert result["posts_analyzed"] == 1


@pytest.mark.asyncio
async def test_analyze_adds_username_backcompat_key():
    with patch(
        "bot.services.instagram_tov_service.TovImportService.analyze",
        new=AsyncMock(return_value=dict(FAKE_RESULT)),
    ):
        svc = InstagramTovService(apify_token="tok", anthropic_api_key="key")
        result = await svc.analyze("@alex")

    # back-compat: formatter/handler still read ``username``.
    assert result["username"] == "alex"


@pytest.mark.asyncio
async def test_analyze_propagates_no_posts_error():
    with patch(
        "bot.services.instagram_tov_service.TovImportService.analyze",
        new=AsyncMock(side_effect=NoPostsError("no posts")),
    ):
        svc = InstagramTovService(apify_token="tok", anthropic_api_key="key")
        with pytest.raises(NoPostsError):
            await svc.analyze("private_user")


@pytest.mark.asyncio
async def test_analyze_propagates_service_error():
    with patch(
        "bot.services.instagram_tov_service.TovImportService.analyze",
        new=AsyncMock(side_effect=ServiceError("Apify failed")),
    ):
        svc = InstagramTovService(apify_token="tok", anthropic_api_key="key")
        with pytest.raises(ServiceError):
            await svc.analyze("alex")
