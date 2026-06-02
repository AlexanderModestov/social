import asyncio
import json
import google.generativeai as genai
from bot.config import settings

genai.configure(api_key=settings.google_api_key)


class GeminiService:
    MODEL = "gemini-2.0-flash-exp"

    def __init__(self):
        self.client = genai.Client()

    async def generate_video(
        self,
        description: str,
        image_paths: list[str],
        tone_profile: dict,
    ):
        system_prompt = (
            "You are a TikTok video creator. Based on the description, images, and tone of voice, "
            "generate a short engaging video (15-60 seconds). "
            f"Tone of voice: {json.dumps(tone_profile)}"
        )
        contents = [system_prompt, description]
        for path in image_paths:
            with open(path, "rb") as f:
                image_data = f.read()
            contents.append({"mime_type": "image/jpeg", "data": image_data})

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(
                model=self.MODEL,
                contents=contents,
            )
        )
        return response
