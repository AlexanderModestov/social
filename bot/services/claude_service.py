import json
import anthropic
from pathlib import Path
from bot.config import settings

SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"


def _load_skill(path: str) -> str:
    return (SKILLS_DIR / path).read_text(encoding="utf-8")


class ClaudeService:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def generate_tone_of_voice(
        self,
        role: str,
        audience: str,
        style_words: list[str],
        examples: list[str],
    ) -> dict:
        system_prompt = _load_skill("brand_voice/system_prompt.txt")
        user_message = (
            f"Role: {role}\n"
            f"Audience: {audience}\n"
            f"Style words: {', '.join(style_words)}\n"
            f"Examples:\n" + "\n".join(f"- {e}" for e in examples)
        )
        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        text = response.content[0].text.strip()
        # strip markdown code fences if Claude wraps the JSON
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.rstrip("`").strip()
        return json.loads(text)

    async def generate_linkedin_post(
        self,
        notes: str,
        scraped_content: list[str],
        tone_profile: dict,
        previous_post: str | None = None,
        feedback: str | None = None,
    ) -> str:
        system_prompt = _load_skill("linkedin/system_prompt.txt")
        context_parts = [f"USER TONE OF VOICE:\n{json.dumps(tone_profile, indent=2)}"]
        if scraped_content:
            context_parts.append("REFERENCE ARTICLES:\n" + "\n\n---\n\n".join(scraped_content))
        if notes:
            context_parts.append(f"USER NOTES:\n{notes}")
        if previous_post and feedback:
            context_parts.append(f"PREVIOUS POST:\n{previous_post}\n\nFEEDBACK:\n{feedback}")

        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": "\n\n".join(context_parts)}],
        )
        return response.content[0].text

    async def generate_tiktok_caption(self, url: str, page_content: str, tone_profile: dict) -> str:
        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system="Write a punchy TikTok caption (under 150 chars) + 5 hashtags. Match the user's tone of voice. Respond with just the caption and hashtags.",
            messages=[{"role": "user", "content": f"Product URL: {url}\nPage content: {page_content[:2000]}\nTone: {json.dumps(tone_profile)}"}],
        )
        return response.content[0].text
