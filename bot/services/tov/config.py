# NOTE: TikTok/LinkedIn actor input keys and result field names below are best-guess
# pending verification against a real Apify run; this module is the single place to adjust them.
from bot.db.channels import INSTAGRAM, TIKTOK, LINKEDIN

# Public, no-cookies Apify actors that return a profile's recent posts.
CHANNEL_ACTORS = {
    INSTAGRAM: "apify~instagram-scraper",
    TIKTOK: "clockworks~tiktok-scraper",
    LINKEDIN: "apimaestro~linkedin-profile-posts",
}

# Per-channel actor input builder: (handle, limit) -> dict payload.
def actor_input(channel: str, handle: str, limit: int) -> dict:
    if channel == INSTAGRAM:
        return {
            "directUrls": [f"https://www.instagram.com/{handle}/"],
            "resultsType": "posts", "resultsLimit": limit, "addParentData": False,
        }
    if channel == TIKTOK:
        return {"profiles": [handle], "resultsPerPage": limit, "shouldDownloadVideos": False}
    if channel == LINKEDIN:
        return {"username": handle, "limit": limit}
    raise ValueError(f"unknown channel: {channel}")

# Per-channel: extract the caption/body text from one actor result item.
def post_text(channel: str, item: dict) -> str:
    if channel == INSTAGRAM:
        return (item.get("caption") or "").strip()
    if channel == TIKTOK:
        return (item.get("text") or item.get("description") or "").strip()
    if channel == LINKEDIN:
        return (item.get("text") or item.get("content") or "").strip()
    raise ValueError(f"unknown channel: {channel}")
