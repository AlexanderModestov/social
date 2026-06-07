import json
import re
import anthropic


def _detect_language(text: str) -> str:
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


def preprocess_posts(posts: list[dict]) -> dict:
    captions = [
        {
            "text": (p.get("caption") or "").strip(),
            "location": p.get("locationName"),
            "likes": p.get("likesCount", 0),
            "date": (p.get("timestamp") or "")[:10],
            "lang": _detect_language((p.get("caption") or "")),
        }
        for p in posts
        if (p.get("caption") or "").strip()
    ]

    lang_counts = {"ru": 0, "en": 0, "mixed": 0}
    for c in captions:
        lang_counts[c["lang"]] = lang_counts.get(c["lang"], 0) + 1

    lengths = [len(c["text"]) for c in captions]
    avg_len = int(sum(lengths) / len(lengths)) if lengths else 0

    locations = [p["location"] for p in captions if p["location"]]

    return {
        "total_posts": len(posts),
        "posts_with_captions": len(captions),
        "avg_caption_length": avg_len,
        "language_counts": lang_counts,
        "unique_locations": list(dict.fromkeys(locations))[:20],
        "captions": captions,
    }


TOV_SCHEMA = """{
  "persona_summary": "2-3 sentences describing who this person is based on their content style",
  "archetype": "one concise phrase (e.g. 'reflective urban nomad', 'ironic homebody')",
  "voice_dimensions": [
    {"name": "short name", "description": "1-2 sentences"}
  ],
  "language": {
    "primary": "language name and ~percentage",
    "secondary": "other language if present, else null",
    "mixing_note": "how they mix languages, or null"
  },
  "caption_patterns": [
    {
      "name": "pattern name",
      "frequency": "e.g. ~60% of posts",
      "description": "what this pattern looks like",
      "examples": ["example 1", "example 2"]
    }
  ],
  "motifs": {
    "themes": ["theme1", "theme2"],
    "places": ["place1", "place2"],
    "sensory": ["detail1", "detail2"]
  },
  "dos": ["rule 1", "rule 2", "rule 3", "rule 4", "rule 5"],
  "donts": ["rule 1", "rule 2", "rule 3", "rule 4", "rule 5"],
  "signature_elements": {
    "punctuation": "description of punctuation style",
    "hashtags": "how they use or don't use hashtags",
    "phrases": ["phrase1", "phrase2", "phrase3"]
  }
}"""


def build_prompt(username: str, data: dict) -> str:
    # Send only texts, not full objects, to keep prompt tight
    caption_texts = [
        f"[{c['date']} | {c['lang']} | {c['likes']} likes | loc: {c['location'] or '-'}]\n{c['text']}"
        for c in data["captions"]
    ]
    captions_block = "\n\n".join(caption_texts[:80])

    return f"""Analyze Instagram profile @{username} and produce a tone of voice document.

Stats:
- {data['total_posts']} total posts, {data['posts_with_captions']} with captions
- Average caption length: {data['avg_caption_length']} chars
- Language split: {json.dumps(data['language_counts'])}
- Locations: {', '.join(data['unique_locations'])}

Captions ({len(data['captions'])} total, showing up to 80):
{captions_block}

Return ONLY a valid JSON object with this exact structure (no markdown fences, no extra text):
{TOV_SCHEMA}"""


def generate_tov(username: str, posts: list[dict], api_key: str) -> dict:
    data = preprocess_posts(posts)
    prompt = build_prompt(username, data)

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text.strip()
    # Strip markdown code fences if Claude added them
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)

    result = json.loads(text)
    result["username"] = username
    result["posts_analyzed"] = data["total_posts"]
    return result
