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

    _CORE_SPEC = (
        "Anchor on the user's CORE IDEA: identify the central action/event/message the "
        "user described and keep it the focus — every detail you add must serve that "
        "idea, never replace it. "
        "Write the prompt as timestamped beats that span the FULL duration, e.g. "
        "[00:00-00:03] ... [00:03-00:06] ..., choosing 2-4 beats from the idea's pacing; "
        "each beat must be performable within its seconds. "
        "For every beat cover, IN THIS PRIORITY ORDER: subject (who + appearance), "
        "concrete ACTION (what they physically do), then cinematography (shot + camera "
        "move), context, and only then atmosphere/lighting — put action and subject "
        "before atmosphere so mood never crowds out what actually happens. "
        "If the idea involves people speaking, include short spoken lines in quotation "
        "marks in the user's own language with a delivery note (e.g. a woman says, "
        "excited, \"...\"); keep each line short enough to be spoken within its beat. "
        "Add SFX: or Ambient noise: directives only where they serve the idea. "
    )

    def _veo_prompt_system(self, tone_profile: dict) -> str:
        dur = settings.veo_duration_seconds
        return (
            "You are a video director writing a prompt for a text-to-video model, for "
            f"ONE vertical 9:16 TikTok clip that is exactly {dur} seconds long. "
            f"{self._CORE_SPEC}"
            f"{self._NO_TEXT} "
            "Output ONLY the prompt text (the beats), no preamble. "
            f"Match this tone of voice: {json.dumps(tone_profile)}"
        )

    def _veo_scenes_system(self, tone_profile: dict, max_scenes: int) -> str:
        dur = settings.veo_duration_seconds
        return (
            "You are a video director storyboarding a vertical 9:16 TikTok video as AT "
            f"MOST {max_scenes} scenes. Each scene is ONE shot lasting exactly {dur} "
            "seconds. Carry the CORE IDEA and visual continuity across the scenes so "
            "they read as one coherent video. "
            f"{self._CORE_SPEC}"
            f"{self._NO_TEXT} "
            "Format EXACTLY as:\n"
            "Scene 1: <beats>\nScene 2: <beats>\n...\n"
            "Output only the scenes, no preamble. "
            f"Match this tone of voice: {json.dumps(tone_profile)}"
        )

    def _split_scenes(self, text: str, max_scenes: int | None = None) -> list[str]:
        max_scenes = max_scenes or settings.veo_max_scenes
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

    def _parse_refine_result(self, raw: dict, max_scenes: int) -> dict:
        kind = raw.get("kind")
        if kind == "clarify":
            question = (raw.get("question") or "").strip()
            if not question:
                raise ValueError("clarify result missing question")
            return {"kind": "clarify", "question": question}
        if kind == "revision":
            prompts = [p.strip() for p in (raw.get("prompts") or []) if p and p.strip()]
            if not prompts:
                raise ValueError("revision result missing prompts")
            return {"kind": "revision", "prompts": prompts[:max_scenes]}
        raise ValueError(f"unknown refine result kind: {kind!r}")

    async def _generate_json(self, text: str, system_prompt: str) -> dict:
        resp = await _get_client().aio.models.generate_content(
            model=self.MODEL,
            contents=[types.Part.from_text(text=text)],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
            ),
        )
        return json.loads(resp.text or "{}")

    def _refine_system(
        self, current_prompts: list[str], instruction: str, tone_profile: dict, mode: str,
    ) -> str:
        dur = settings.veo_duration_seconds
        joined = "\n\n".join(current_prompts)
        shape = (
            "Respond with ONLY a JSON object. If the instruction is clear, apply it and "
            'return {"kind": "revision", "prompts": ["<full revised prompt>"]} — for a '
            "full video put one revised scene per array element. If the instruction is "
            'genuinely ambiguous, instead return {"kind": "clarify", "question": "<one '
            'short question>"}. Apply the requested change even if it alters earlier '
            "style or detail; keep everything the user did not ask to change. Only ask a "
            "question when you truly cannot tell what to change — never as a stall."
        )
        return (
            "You are revising an existing text-to-video prompt for a vertical 9:16 "
            f"TikTok clip; each shot is exactly {dur} seconds. "
            f"{self._CORE_SPEC}"
            f"{self._NO_TEXT} "
            f"{shape}\n\n"
            f"CURRENT PROMPT:\n{joined}\n\n"
            f"INSTRUCTION:\n{instruction}\n\n"
            f"Match this tone of voice: {json.dumps(tone_profile)}"
        )

    async def refine_veo_prompt(
        self, current_prompts: list[str], instruction: str, tone_profile: dict, mode: str,
        max_scenes: int | None = None,
    ) -> dict:
        max_scenes = max_scenes or settings.veo_max_scenes
        system_prompt = self._refine_system(current_prompts, instruction, tone_profile, mode)
        raw = await self._generate_json(instruction, system_prompt)
        return self._parse_refine_result(raw, max_scenes)
