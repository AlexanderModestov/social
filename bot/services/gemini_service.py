import json
from functools import lru_cache

from google import genai
from google.genai import types

from bot.config import settings


@lru_cache(maxsize=1)
def _get_client() -> genai.Client:
    return genai.Client(
        vertexai=True,
        project=settings.gcp_project_id,
        location=settings.gcp_location,
    )


class GeminiService:
    MODEL = "gemini-2.5-flash"

    async def generate_video(
        self,
        description: str,
        image_paths: list[str],
        tone_profile: dict,
    ):
        system_prompt = (
            "You are a TikTok video creator. Based on the description, images, "
            "and tone of voice, generate a short engaging video (15-60 seconds). "
            f"Tone of voice: {json.dumps(tone_profile)}"
        )
        parts = [types.Part.from_text(text=description)]
        for path in image_paths:
            with open(path, "rb") as f:
                parts.append(
                    types.Part.from_bytes(data=f.read(), mime_type="image/jpeg")
                )

        return await _get_client().aio.models.generate_content(
            model=self.MODEL,
            contents=parts,
            config=types.GenerateContentConfig(system_instruction=system_prompt),
        )
