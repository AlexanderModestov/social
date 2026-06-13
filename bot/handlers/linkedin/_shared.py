import asyncio
from bot.config import settings
from bot.db.session import async_session_factory
from bot.db.repository import ToneOfVoiceRepository, PostHistoryRepository
from bot.keyboards.inline import post_actions_keyboard
from bot.services.linkedin import parse_linkedin_url, fetch_post
from bot.services.linkedin.skill_service import LinkedInSkillService

_service = LinkedInSkillService()


async def resolve_source(text: str) -> tuple[str, str]:
    """Return (content, source) where source is 'apify' | 'paste' | 'needs_paste' | 'empty'."""
    parsed = parse_linkedin_url(text or "")
    is_url = parsed["url_type"] != "unknown"
    if is_url and settings.apify_token:
        post = await asyncio.to_thread(fetch_post, text)
        if post and post.get("text"):
            return post["text"], "apify"
    if is_url:
        # URL but no Apify (or fetch failed/empty) — caller asks user to paste the body
        return "", "needs_paste"
    if text and text.strip():
        return text, "paste"
    return "", "empty"


async def fetch_engagers(post_url: str, max_items: int = 50):
    """Return a list of engagers for a post via Apify, or None if no token / failure."""
    if not settings.apify_token:
        return None
    try:
        from bot.services.linkedin.apify_client import ApifyClient
        client = ApifyClient(token=settings.apify_token)
        return await asyncio.to_thread(client.fetch_post_engagers, post_url=post_url, max_items=max_items)
    except Exception:
        return None


async def get_active_tov(user_id: int) -> dict:
    async with async_session_factory() as session:
        tov = await ToneOfVoiceRepository(session).get_active(user_id)
    return tov.profile_json if tov else {}


async def run_skill(skill, user_inputs, user_id, previous=None, feedback=None) -> str:
    tov = await get_active_tov(user_id)
    return await _service.run(skill, user_inputs, tov, previous=previous, feedback=feedback)


def approval_card(draft: str) -> dict:
    chars = len(draft)
    body = f"{draft}\n\n— {chars} chars · best window: Tue/Wed/Thu 7:30-9:00 AM"
    return {"text": body, "reply_markup": post_actions_keyboard()}


def report_card(text: str, extra_rows: list | None = None) -> dict:
    """A generic result card for non-draft skills: the text plus a Save button
    (callback 'skill:save'), with optional extra button rows prepended."""
    from bot.keyboards.inline import linkedin_report_keyboard
    return {"text": text, "reply_markup": linkedin_report_keyboard(extra_rows)}


async def save_history(user_id, skill, inputs, output):
    async with async_session_factory() as session:
        await PostHistoryRepository(session).create(
            user_id=user_id, platform="linkedin", format=skill,
            input_data=inputs, output_data={"output": output},
        )
        await session.commit()
