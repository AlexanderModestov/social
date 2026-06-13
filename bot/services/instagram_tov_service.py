"""Instagram TOV service — thin back-compat wrapper over the shared transport.

The hand-rolled Apify polling + Claude call has moved to
``bot.services.tov.service.TovImportService``. This module keeps the historic
public surface (``InstagramTovService`` + the three error classes) so existing
importers (``bot/handlers/tone_of_voice.py``) keep working unchanged.
"""
from bot.db.channels import INSTAGRAM
from bot.services.tov.errors import (  # re-exported for back-compat
    NoPostsError,
    PrivateProfileError,
    ServiceError,
)
from bot.services.tov.service import TovImportService

__all__ = [
    "InstagramTovService",
    "PrivateProfileError",
    "NoPostsError",
    "ServiceError",
]


class InstagramTovService:
    def __init__(self, apify_token: str, anthropic_api_key: str):
        self._svc = TovImportService(apify_token, anthropic_api_key)

    async def analyze(self, username: str) -> dict:
        result = await self._svc.analyze(INSTAGRAM, username)
        result["username"] = result.get("handle")  # back-compat key
        return result
