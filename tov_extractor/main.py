import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from scraper import extract_username, scrape_posts
from analyzer import generate_tov

load_dotenv()

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

app = FastAPI(title="Tone of Voice API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    username: str


@app.get("/health")
def health():
    return {
        "status": "ok",
        "apify": "configured" if APIFY_TOKEN else "missing",
        "anthropic": "configured" if ANTHROPIC_API_KEY else "missing",
    }


@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    if not APIFY_TOKEN:
        raise HTTPException(500, "APIFY_TOKEN not configured")
    if not ANTHROPIC_API_KEY:
        raise HTTPException(500, "ANTHROPIC_API_KEY not configured")

    username = extract_username(req.username)
    if not username:
        raise HTTPException(400, "Invalid username or URL")

    try:
        posts = await scrape_posts(username, APIFY_TOKEN)
    except Exception as e:
        raise HTTPException(502, f"Scraping failed: {e}")

    if not posts:
        raise HTTPException(404, "No posts found. Profile may be private or doesn't exist.")

    try:
        result = generate_tov(username, posts, ANTHROPIC_API_KEY)
    except Exception as e:
        raise HTTPException(500, f"Analysis failed: {e}")

    return result
