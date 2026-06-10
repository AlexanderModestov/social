import asyncio
import os
import shutil
import subprocess
import tempfile
from functools import lru_cache

from google import genai
from google.genai import types

from bot.config import settings

POLL_INTERVAL = 15
POLL_TIMEOUT = 360


@lru_cache(maxsize=1)
def _get_client() -> genai.Client:
    return genai.Client(
        vertexai=True,
        project=settings.gcp_project_id,
        location=settings.gcp_location,
    )


class VeoService:
    MODEL = settings.veo_model

    def _config(self) -> types.GenerateVideosConfig:
        kwargs = dict(
            number_of_videos=1,
            duration_seconds=settings.veo_duration_seconds,
            aspect_ratio="9:16",
            generate_audio=True,
        )
        if settings.gcs_output_bucket:
            kwargs["output_gcs_uri"] = settings.gcs_output_bucket
        return types.GenerateVideosConfig(**kwargs)

    def _normalize_cmd(self, in_path: str, out_path: str) -> list[str]:
        # Cover-crop to a 1080x1920 vertical canvas so a landscape seed image
        # can't drag Veo's output off 9:16. No black bars (crop, not pad).
        return [
            "ffmpeg", "-y", "-i", in_path,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            out_path,
        ]

    def _normalize_seed(self, path: str) -> str:
        out_dir = tempfile.mkdtemp()
        out_path = os.path.join(out_dir, "seed_9x16.jpg")
        subprocess.run(self._normalize_cmd(path, out_path), check=True, capture_output=True)
        return out_path

    async def generate_clip(self, prompt: str, seed_image_path: str | None = None) -> str:
        client = _get_client()
        norm_dir = None
        image = None
        if seed_image_path:
            normalized = self._normalize_seed(seed_image_path)
            norm_dir = os.path.dirname(normalized)
            image = types.Image.from_file(location=normalized)
        try:
            op = await client.aio.models.generate_videos(
                model=self.MODEL, prompt=prompt, image=image, config=self._config(),
            )
            elapsed = 0
            while not op.done:
                if elapsed >= POLL_TIMEOUT:
                    raise TimeoutError(f"Veo generation timed out after {POLL_TIMEOUT}s")
                await asyncio.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL
                op = await client.aio.operations.get(op)
            video = op.response.generated_videos[0].video
            return self._write_clip(video)
        finally:
            if norm_dir:
                shutil.rmtree(norm_dir, ignore_errors=True)

    def _write_clip(self, video) -> str:
        # On Vertex, generate_videos returns inline bytes; files.download() is
        # Gemini-Developer-only and raises on a Vertex client, so write directly.
        if not video.video_bytes:
            raise RuntimeError(
                "Veo returned no inline video bytes (likely a GCS-only response). "
                "Configure GCS download or check VEO_MODEL/output settings."
            )
        out_path = os.path.join(tempfile.mkdtemp(), "clip.mp4")
        with open(out_path, "wb") as fh:
            fh.write(video.video_bytes)
        return out_path

    async def generate_and_stitch(
        self, prompts: list[str], seed_image_path: str | None = None,
    ) -> str:
        tmpdir = tempfile.mkdtemp()
        clip_paths: list[str] = []
        try:
            for i, prompt in enumerate(prompts):
                seed = seed_image_path if i == 0 else None
                clip = await self.generate_clip(prompt, seed_image_path=seed)
                dest = os.path.join(tmpdir, f"clip_{i:02d}.mp4")
                os.replace(clip, dest)
                shutil.rmtree(os.path.dirname(clip), ignore_errors=True)
                clip_paths.append(dest)
            return self._stitch(clip_paths, tmpdir)
        except Exception:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise

    def _build_concat_file(self, clip_paths: list[str], tmpdir: str) -> str:
        list_path = os.path.join(tmpdir, "clips.txt")
        with open(list_path, "w") as f:
            f.write("\n".join(f"file '{p}'" for p in clip_paths))
        return list_path

    def _stitch(self, clip_paths: list[str], tmpdir: str) -> str:
        list_path = self._build_concat_file(clip_paths, tmpdir)
        output = os.path.join(tmpdir, "final.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", output],
            check=True, capture_output=True,
        )
        return output
