"""Unified Apify TOV import service: scrape -> preprocess -> Claude generation.

Ties the per-channel config (Task 5), preprocessing (Task 6), and channel-tuned
prompts together behind one ``analyze`` coroutine with a uniform error taxonomy:
Apify transport failures -> ServiceError, empty results -> NoPostsError.
"""
import json
import re

import anthropic

from bot.services.linkedin.apify_client import ApifyClient, ApifyError
from bot.services.tov.config import CHANNEL_ACTORS, actor_input
from bot.services.tov.handles import extract_handle
from bot.services.tov.preprocess import preprocess_posts
from bot.services.tov.prompts import build_tov_prompt
from bot.services.tov.errors import NoPostsError, ServiceError


def _generate_tov(channel, handle, data, anthropic_api_key) -> dict:
    prompt = build_tov_prompt(channel, handle, data)
    client = anthropic.Anthropic(api_key=anthropic_api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text)


class TovImportService:
    def __init__(self, apify_token: str, anthropic_api_key: str, limit: int = 50):
        self._client = ApifyClient(token=apify_token)
        self._anthropic_api_key = anthropic_api_key
        self._limit = limit

    async def analyze(self, channel: str, raw_handle: str) -> dict:
        import asyncio

        handle = extract_handle(channel, raw_handle)
        try:
            posts = await asyncio.to_thread(
                self._client.fetch_profile_posts,
                CHANNEL_ACTORS[channel],
                actor_input(channel, handle, self._limit),
            )
        except ApifyError as e:
            raise ServiceError(str(e)) from e
        if not posts:
            raise NoPostsError("no posts found")
        data = preprocess_posts(channel, posts)
        if data["posts_with_text"] == 0:
            raise NoPostsError("no posts with text")
        try:
            tov = await asyncio.to_thread(
                _generate_tov, channel, handle, data, self._anthropic_api_key
            )
        except Exception as e:
            raise ServiceError(str(e)) from e
        tov["channel"] = channel
        tov["handle"] = handle
        tov["posts_analyzed"] = data["total_posts"]
        return tov
