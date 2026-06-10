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

    _NO_TEXT = (
        "Do NOT depict any on-screen text, captions, words, letters, numbers, "
        "logos, signage, or UI writing. The scene must contain no readable text "
        "of any kind."
    )

    def _veo_prompt_system(self, tone_profile: dict) -> str:
        dur = settings.veo_duration_seconds
        return (
            "You are a video director writing a prompt for a text-to-video model. "
            "Turn the user's idea into ONE vivid, cinematic shot description for a "
            "vertical 9:16 TikTok clip. "
            f"This clip is exactly {dur} seconds long: describe only ONE continuous "
            f"action that realistically fits in {dur} seconds of screen time — do "
            "not pack a longer story into one shot. Cover subject, setting, camera "
            "movement, lighting, and mood in 2-4 sentences. "
            f"{self._NO_TEXT} "
            "Output ONLY the prompt text, no preamble. "
            f"Match this tone of voice: {json.dumps(tone_profile)}"
        )

    def _veo_scenes_system(self, tone_profile: dict, max_scenes: int) -> str:
        dur = settings.veo_duration_seconds
        return (
            "You are a video director storyboarding a short vertical 9:16 TikTok "
            f"video as AT MOST {max_scenes} scenes. Each scene is ONE shot lasting "
            f"exactly {dur} seconds, so describe only the action that fits in that "
            "time. For each "
            "scene write one vivid, cinematic shot description (subject, camera, "
            "lighting, mood) suitable as a text-to-video prompt. "
            f"{self._NO_TEXT} "
            "Format EXACTLY as:\n"
            "Scene 1: <description>\nScene 2: <description>\n...\n"
            "Output only the scenes, no preamble. "
            f"Match this tone of voice: {json.dumps(tone_profile)}"
        )

    def _split_scenes(self, text: str, max_scenes: int = 3) -> list[str]:
        # Split on the "Scene N:" marker so multi-line descriptions are preserved.
        parts = re.split(r"(?im)^\s*Scene\s+\d+:\s*", text)
        scenes = [p.strip() for p in parts[1:] if p.strip()]
        if scenes:
            return scenes[:max_scenes]
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        return paragraphs[:max_scenes]

    async def _generate(self, description: str, image_paths: list[str], system_prompt: str) -> str:
        parts = [types.Part.from_text(text=description)]
        for path in image_paths:
            with open(path, "rb") as f:
                parts.append(types.Part.from_bytes(data=f.read(), mime_type="image/jpeg"))
        resp = await _get_client().aio.models.generate_content(
            model=self.MODEL,
            contents=parts,
            config=types.GenerateContentConfig(system_instruction=system_prompt),
        )
        return resp.text or ""

    async def write_veo_prompt(
        self, description: str, image_paths: list[str], tone_profile: dict,
    ) -> str:
        system_prompt = self._veo_prompt_system(tone_profile)
        return (await self._generate(description, image_paths, system_prompt)).strip()

    async def write_veo_scenes(
        self, description: str, image_paths: list[str], tone_profile: dict, max_scenes: int | None = None,
    ) -> list[str]:
        max_scenes = max_scenes or settings.veo_max_scenes
        system_prompt = self._veo_scenes_system(tone_profile, max_scenes)
        text = await self._generate(description, image_paths, system_prompt)
        return self._split_scenes(text, max_scenes)
