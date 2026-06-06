import json
import re
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

    def _split_scenes(self, text: str, max_scenes: int = 3) -> list[str]:
        # Split on the "Scene N:" marker so multi-line descriptions are preserved.
        parts = re.split(r"(?im)^\s*Scene\s+\d+:\s*", text)
        scenes = [p.strip() for p in parts[1:] if p.strip()]
        if scenes:
            return scenes[:max_scenes]
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        return paragraphs[:max_scenes]

    async def write_veo_prompt(
        self, description: str, image_paths: list[str], tone_profile: dict,
    ) -> str:
        system_prompt = (
            "You are a video director writing a prompt for a text-to-video model. "
            "Turn the user's idea into ONE vivid, cinematic shot description for a "
            "vertical 9:16 TikTok clip (~8 seconds): describe subject, setting, "
            "camera movement, lighting, and mood in 2-4 sentences. Output ONLY the "
            "prompt text, no preamble. "
            f"Match this tone of voice: {json.dumps(tone_profile)}"
        )
        parts = [types.Part.from_text(text=description)]
        for path in image_paths:
            with open(path, "rb") as f:
                parts.append(types.Part.from_bytes(data=f.read(), mime_type="image/jpeg"))
        resp = await _get_client().aio.models.generate_content(
            model=self.MODEL,
            contents=parts,
            config=types.GenerateContentConfig(system_instruction=system_prompt),
        )
        return (resp.text or "").strip()

    async def write_veo_scenes(
        self, description: str, image_paths: list[str], tone_profile: dict, max_scenes: int = 3,
    ) -> list[str]:
        system_prompt = (
            "You are a video director storyboarding a short vertical 9:16 TikTok "
            f"video as AT MOST {max_scenes} scenes. For each scene write one vivid, "
            "cinematic shot description (subject, camera, lighting, mood) suitable "
            "as a text-to-video prompt. Format EXACTLY as:\n"
            "Scene 1: <description>\nScene 2: <description>\n...\n"
            "Output only the scenes, no preamble. "
            f"Match this tone of voice: {json.dumps(tone_profile)}"
        )
        parts = [types.Part.from_text(text=description)]
        for path in image_paths:
            with open(path, "rb") as f:
                parts.append(types.Part.from_bytes(data=f.read(), mime_type="image/jpeg"))
        resp = await _get_client().aio.models.generate_content(
            model=self.MODEL,
            contents=parts,
            config=types.GenerateContentConfig(system_instruction=system_prompt),
        )
        return self._split_scenes(resp.text or "", max_scenes)
