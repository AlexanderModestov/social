"""Generalized preprocessing of raw actor post dicts into language/length stats.

Generalizes the Instagram-only logic in ``bot/services/instagram_tov_service.py``
by reading post text via ``config.post_text`` so it works for all channels.
"""
from bot.services.tov.config import post_text


def detect_language(text: str) -> str:
    if not text:
        return "ru"
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return "ru"
    cyrillic = sum(1 for c in alpha if "Ѐ" <= c <= "ӿ")
    ratio = cyrillic / len(alpha)
    if ratio > 0.6:
        return "ru"
    if ratio < 0.2:
        return "en"
    return "mixed"


def preprocess_posts(channel: str, posts: list[dict]) -> dict:
    texts = []
    for p in posts:
        t = post_text(channel, p)
        if t:
            texts.append({"text": t, "lang": detect_language(t), "likes": p.get("likesCount", 0)})
    lengths = [len(t["text"]) for t in texts]
    counts = {"ru": 0, "en": 0, "mixed": 0}
    for t in texts:
        counts[t["lang"]] = counts.get(t["lang"], 0) + 1
    return {
        "total_posts": len(posts),
        "posts_with_text": len(texts),
        "avg_text_length": int(sum(lengths) / len(lengths)) if lengths else 0,
        "language_counts": counts,
        "texts": texts,
    }
