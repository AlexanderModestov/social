"""Channel-tuned Claude prompts for tone-of-voice generation.

All three channel schemas live here (DRY). ``build_tov_prompt`` mirrors the
body of ``instagram_tov_service._build_prompt``: it includes the handle, the
preprocessed stats, up to ~80 post text bodies, and ends with a strict
"return ONLY JSON" instruction followed by the channel's schema.
"""
import json

from bot.db.channels import INSTAGRAM, TIKTOK, LINKEDIN

# Instagram keeps the existing rich schema (parity with instagram_tov_service).
INSTAGRAM_SCHEMA = """{
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

# TikTok: short-form video captions — hook / pacing / CTA emphasis.
TIKTOK_SCHEMA = """{
  "persona_summary": "2-3 sentences describing this creator's on-camera/caption persona",
  "archetype": "one concise phrase (e.g. 'chaotic-good explainer', 'deadpan reviewer')",
  "language": {
    "primary": "language name and ~percentage",
    "secondary": "other language if present, else null",
    "mixing_note": "how they mix languages, or null"
  },
  "hook_patterns": [
    {
      "name": "hook style name",
      "frequency": "e.g. ~50% of posts",
      "description": "how the first line/caption grabs attention",
      "examples": ["example 1", "example 2"]
    }
  ],
  "pacing": {
    "caption_length": "typical caption length and rhythm",
    "energy": "overall energy/tempo of the writing"
  },
  "cta_patterns": ["how they prompt comments/follows/duets", "second CTA style"],
  "dos": ["rule 1", "rule 2", "rule 3", "rule 4", "rule 5"],
  "donts": ["rule 1", "rule 2", "rule 3", "rule 4", "rule 5"],
  "signature_elements": {
    "hashtags": "how they use hashtags and trends",
    "emoji": "emoji usage style",
    "phrases": ["catchphrase1", "catchphrase2", "catchphrase3"]
  }
}"""

# LinkedIn: professional long-form — hooks / professional register.
LINKEDIN_SCHEMA = """{
  "persona_summary": "2-3 sentences describing this person's professional voice",
  "archetype": "one concise phrase (e.g. 'pragmatic operator', 'visionary contrarian')",
  "language": {
    "primary": "language name and ~percentage",
    "secondary": "other language if present, else null",
    "register": "formal / conversational-professional / thought-leader, etc."
  },
  "hook_patterns": [
    {
      "name": "opening-line style name",
      "frequency": "e.g. ~40% of posts",
      "description": "how the first line earns the 'see more' click",
      "examples": ["example 1", "example 2"]
    }
  ],
  "structure": {
    "formatting": "line breaks, lists, whitespace habits",
    "post_shape": "typical narrative arc (story -> lesson -> CTA, etc.)"
  },
  "themes": ["theme1", "theme2", "theme3"],
  "cta_patterns": ["how they invite engagement professionally", "second CTA style"],
  "dos": ["rule 1", "rule 2", "rule 3", "rule 4", "rule 5"],
  "donts": ["rule 1", "rule 2", "rule 3", "rule 4", "rule 5"],
  "signature_elements": {
    "emoji": "emoji usage in a professional context",
    "hashtags": "hashtag habits",
    "phrases": ["phrase1", "phrase2", "phrase3"]
  }
}"""

_SCHEMAS = {
    INSTAGRAM: INSTAGRAM_SCHEMA,
    TIKTOK: TIKTOK_SCHEMA,
    LINKEDIN: LINKEDIN_SCHEMA,
}

_CHANNEL_NAMES = {
    INSTAGRAM: "Instagram",
    TIKTOK: "TikTok",
    LINKEDIN: "LinkedIn",
}


def build_tov_prompt(channel: str, handle: str, data: dict) -> str:
    """Build the Claude user prompt for one channel's tone-of-voice analysis."""
    schema = _SCHEMAS.get(channel, INSTAGRAM_SCHEMA)
    channel_name = _CHANNEL_NAMES.get(channel, channel)

    texts = data.get("texts", [])
    text_blocks = [
        f"[{t.get('lang', '?')} | {t.get('likes', 0)} likes]\n{t.get('text', '')}"
        for t in texts
    ]
    texts_block = "\n\n".join(text_blocks[:80])

    return f"""Analyze {channel_name} profile @{handle} and produce a tone of voice document.

Stats:
- {data.get('total_posts', 0)} total posts, {data.get('posts_with_text', 0)} with text
- Average text length: {data.get('avg_text_length', 0)} chars
- Language split: {json.dumps(data.get('language_counts', {}))}

Posts ({len(texts)} with text, showing up to 80):
{texts_block}

Return ONLY a valid JSON object with this exact structure (no markdown fences, no extra text):
{schema}"""
