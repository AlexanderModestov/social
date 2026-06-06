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
            duration_seconds=8,
            aspect_ratio="9:16",
            generate_audio=True,
        )
        if settings.gcs_output_bucket:
            kwargs["output_gcs_uri"] = settings.gcs_output_bucket
        return types.GenerateVideosConfig(**kwargs)

    async def generate_clip(self, prompt: str, seed_image_path: str | None = None) -> str:
        client = _get_client()
        image = types.Image.from_file(location=seed_image_path) if seed_image_path else None
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
