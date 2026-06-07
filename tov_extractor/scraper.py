import asyncio
import re
import httpx

APIFY_BASE = "https://api.apify.com/v2"
ACTOR_ID = "apify~instagram-scraper"


def extract_username(raw: str) -> str:
    raw = raw.strip()
    if "instagram.com/" in raw:
        m = re.search(r"instagram\.com/([^/?&#]+)", raw)
        if m:
            return m.group(1)
    return raw.lstrip("@").strip("/")


async def scrape_posts(username: str, apify_token: str, limit: int = 50) -> list[dict]:
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(
            f"{APIFY_BASE}/acts/{ACTOR_ID}/runs",
            params={"token": apify_token, "waitForFinish": 120},
            json={
                "directUrls": [f"https://www.instagram.com/{username}/"],
                "resultsType": "posts",
                "resultsLimit": limit,
                "addParentData": False,
            },
        )
        resp.raise_for_status()
        run = resp.json()["data"]

        # Poll if not finished yet
        for _ in range(12):
            if run["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break
            await asyncio.sleep(10)
            poll = await client.get(
                f"{APIFY_BASE}/actor-runs/{run['id']}",
                params={"token": apify_token},
            )
            poll.raise_for_status()
            run = poll.json()["data"]

        if run["status"] != "SUCCEEDED":
            raise RuntimeError(f"Apify run ended with status: {run['status']}")

        items = await client.get(
            f"{APIFY_BASE}/datasets/{run['defaultDatasetId']}/items",
            params={"token": apify_token, "limit": limit},
        )
        items.raise_for_status()
        return items.json()
