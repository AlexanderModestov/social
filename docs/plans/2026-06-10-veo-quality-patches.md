# Veo Quality Patches Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix five quality issues in the TikTok "Video from plot" (Veo 3.1) flow — prompt/duration mismatch, garbled on-screen text, landscape flips, fixed duration ceiling, and inflexible prompt editing.

**Architecture:** Keep Veo as the generation engine. Make the per-clip duration and scene count configurable; teach Gemini that each clip is exactly N seconds and must contain no on-screen text; normalize the seed image to 1080×1920 with ffmpeg so output stays 9:16; and replace the binary review gate with an Accept / Refine-with-instructions / Rewrite loop. Real-screenshot reproduction (#6/#7) is explicitly out of scope.

**Tech Stack:** Python 3.10, aiogram 3, google-genai (Vertex AI), ffmpeg (already a dependency), pytest.

**Design doc:** `docs/plans/2026-06-10-veo-quality-patches-design.md`

**Conventions observed in this repo:**
- Tests are small and network-free: they exercise pure helpers, constructors, keyboards, and config — never live API calls. Match that. Make new logic testable by extracting prompt-strings into builder methods and ffmpeg args into a command-builder (mirrors the existing `_build_concat_file` test).
- There are **no handler unit tests** (aiogram). Handler wiring is verified by running the bot, not unit tests — keep handlers thin and verify manually in the final task.
- Run tests with the existing interpreter: `"C:\Users\aleks\Documents\Projects\social\.venv\Scripts\python.exe" -m pytest`. All commands below assume cwd = the worktree root `C:\Users\aleks\Documents\Projects\social\.worktrees\veo-quality-patches`.
- `PY` below = `"C:\Users\aleks\Documents\Projects\social\.venv\Scripts\python.exe"`.

---

## Task 1: Add `veo_duration_seconds` and `veo_max_scenes` settings

**Files:**
- Modify: `bot/config.py:17` (Settings fields)
- Test: `tests/test_config.py`

**Step 1: Write the failing tests**

Add to `tests/test_config.py`:

```python
def test_veo_settings_default(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("GCP_PROJECT_ID", "p")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:y@localhost/z")
    monkeypatch.delenv("VEO_DURATION_SECONDS", raising=False)
    monkeypatch.delenv("VEO_MAX_SCENES", raising=False)

    settings = Settings(_env_file=None)
    assert settings.veo_duration_seconds == 8
    assert settings.veo_max_scenes == 3


def test_veo_settings_read_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("GCP_PROJECT_ID", "p")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:y@localhost/z")
    monkeypatch.setenv("VEO_DURATION_SECONDS", "6")
    monkeypatch.setenv("VEO_MAX_SCENES", "5")

    settings = Settings(_env_file=None)
    assert settings.veo_duration_seconds == 6
    assert settings.veo_max_scenes == 5
```

**Step 2: Run to verify failure**

Run: `PY -m pytest tests/test_config.py -q`
Expected: FAIL (`AttributeError: ... 'veo_duration_seconds'`).

**Step 3: Implement**

In `bot/config.py`, add two fields after line 17 (`gcs_output_bucket`):

```python
    veo_duration_seconds: int = 8
    veo_max_scenes: int = 3
```

**Step 4: Run to verify pass**

Run: `PY -m pytest tests/test_config.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add bot/config.py tests/test_config.py
git commit -m "feat: configurable veo_duration_seconds and veo_max_scenes"
```

---

## Task 2: Veo uses configured duration + normalizes seed image to 9:16

**Files:**
- Modify: `bot/services/veo_service.py` (`_config`, `generate_clip`; add `_normalize_cmd`, `_normalize_seed`)
- Test: `tests/services/test_veo_service.py`

**Step 1: Write the failing tests**

Add to `tests/services/test_veo_service.py`:

```python
def test_config_uses_duration_setting():
    svc = VeoService()
    cfg = svc._config()
    assert cfg.duration_seconds == 8
    assert cfg.aspect_ratio == "9:16"


def test_normalize_cmd_forces_1080x1920(tmp_path):
    svc = VeoService()
    cmd = svc._normalize_cmd("in.jpg", "out.jpg")
    assert cmd[0] == "ffmpeg"
    assert "in.jpg" in cmd and "out.jpg" in cmd
    vf = cmd[cmd.index("-vf") + 1]
    assert "1080:1920" in vf
    assert "crop=1080:1920" in vf
```

**Step 2: Run to verify failure**

Run: `PY -m pytest tests/services/test_veo_service.py -q`
Expected: FAIL (`AttributeError: ... '_normalize_cmd'`).

**Step 3: Implement**

In `bot/services/veo_service.py`:

Change `_config` (line 29-38) so duration comes from settings:

```python
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
```

Add two methods (place above `generate_clip`):

```python
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
```

Update `generate_clip` (line 40-55) to normalize the seed and clean it up:

```python
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
```

(`os`, `shutil`, `subprocess`, `tempfile` are already imported.)

**Step 4: Run to verify pass**

Run: `PY -m pytest tests/services/test_veo_service.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add bot/services/veo_service.py tests/services/test_veo_service.py
git commit -m "feat: veo uses configured duration and normalizes seed to 9:16"
```

---

## Task 3: Gemini system prompts — 8s constraint + no on-screen text

**Files:**
- Modify: `bot/services/gemini_service.py` (extract `_veo_prompt_system`, `_veo_scenes_system`; use them)
- Test: `tests/services/test_gemini_service.py`

**Step 1: Write the failing tests**

Add to `tests/services/test_gemini_service.py`:

```python
def test_veo_prompt_system_has_duration_and_no_text():
    svc = GeminiService()
    sys = svc._veo_prompt_system({"voice": "punchy"})
    assert "8 second" in sys
    assert "no" in sys.lower() and "text" in sys.lower()
    assert "punchy" in sys  # tone profile is injected


def test_veo_scenes_system_has_duration_and_no_text():
    svc = GeminiService()
    sys = svc._veo_scenes_system({}, max_scenes=3)
    assert "8 second" in sys
    assert "text" in sys.lower()
    assert "3" in sys
```

**Step 2: Run to verify failure**

Run: `PY -m pytest tests/services/test_gemini_service.py -q`
Expected: FAIL (`AttributeError: ... '_veo_prompt_system'`).

**Step 3: Implement**

In `bot/services/gemini_service.py`, add `from bot.config import settings` is already imported. Add the no-text clause as a shared constant and two builder methods, then have the public methods call them.

Add near the top of the `GeminiService` class body:

```python
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
            f"video as AT MOST {max_scenes} scenes. Each scene is ONE {dur}-second "
            "shot, so describe only the action that fits in that time. For each "
            "scene write one vivid, cinematic shot description (subject, camera, "
            "lighting, mood) suitable as a text-to-video prompt. "
            f"{self._NO_TEXT} "
            "Format EXACTLY as:\n"
            "Scene 1: <description>\nScene 2: <description>\n...\n"
            "Output only the scenes, no preamble. "
            f"Match this tone of voice: {json.dumps(tone_profile)}"
        )
```

Replace the body of `write_veo_prompt` so it uses the builder:

```python
    async def write_veo_prompt(
        self, description: str, image_paths: list[str], tone_profile: dict,
    ) -> str:
        system_prompt = self._veo_prompt_system(tone_profile)
        return (await self._generate(description, image_paths, system_prompt)).strip()
```

Replace `write_veo_scenes` so it uses the builder and the configured cap:

```python
    async def write_veo_scenes(
        self, description: str, image_paths: list[str], tone_profile: dict, max_scenes: int | None = None,
    ) -> list[str]:
        max_scenes = max_scenes or settings.veo_max_scenes
        system_prompt = self._veo_scenes_system(tone_profile, max_scenes)
        text = await self._generate(description, image_paths, system_prompt)
        return self._split_scenes(text, max_scenes)
```

**Step 4: Run to verify pass**

Run: `PY -m pytest tests/services/test_gemini_service.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add bot/services/gemini_service.py tests/services/test_gemini_service.py
git commit -m "feat: veo prompts enforce per-clip duration and suppress on-screen text"
```

---

## Task 4: Wire `veo_max_scenes` through scene-splitting and the edit handler

**Files:**
- Modify: `bot/services/gemini_service.py` (`_split_scenes` default)
- Modify: `bot/handlers/tiktok.py:201` (replace hardcoded `[:3]`)
- Test: `tests/services/test_gemini_service.py`

**Step 1: Write the failing test**

Add to `tests/services/test_gemini_service.py`:

```python
def test_split_scenes_respects_config_cap(monkeypatch):
    import bot.services.gemini_service as gs
    monkeypatch.setattr(gs.settings, "veo_max_scenes", 2, raising=False)
    svc = GeminiService()
    text = "\n".join(f"Scene {i}: action {i}" for i in range(1, 6))
    assert len(svc._split_scenes(text)) == 2
```

**Step 2: Run to verify failure**

Run: `PY -m pytest tests/services/test_gemini_service.py::test_split_scenes_respects_config_cap -q`
Expected: FAIL (returns 3, not 2).

**Step 3: Implement**

In `gemini_service.py`, change `_split_scenes` signature/first line:

```python
    def _split_scenes(self, text: str, max_scenes: int | None = None) -> list[str]:
        max_scenes = max_scenes or settings.veo_max_scenes
```

(The rest of the method is unchanged.)

In `bot/handlers/tiktok.py`, add `from bot.config import settings` to the imports, then replace line 201:

```python
        prompts = [p.strip() for p in text.split("\n\n") if p.strip()][: settings.veo_max_scenes]
```

**Step 4: Run to verify pass**

Run: `PY -m pytest tests/services/test_gemini_service.py -q`
Expected: PASS (existing `test_split_scenes_caps_at_three` still passes — default is 3).

**Step 5: Commit**

```bash
git add bot/services/gemini_service.py bot/handlers/tiktok.py tests/services/test_gemini_service.py
git commit -m "feat: scene cap driven by veo_max_scenes setting"
```

---

## Task 5: Three-button review keyboard + refining state

**Files:**
- Modify: `bot/keyboards/inline.py:63-67` (`prompt_review_keyboard`)
- Modify: `bot/states/states.py:25` (add `refining_prompt`)
- Test: `tests/test_keyboards.py`

**Step 1: Write the failing test**

Add to `tests/test_keyboards.py` (and extend the import line):

```python
from bot.keyboards.inline import prompt_review_keyboard

def test_prompt_review_keyboard_has_accept_refine_edit():
    kb = prompt_review_keyboard()
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "veo:accept" in callbacks
    assert "veo:refine" in callbacks
    assert "veo:edit" in callbacks
```

**Step 2: Run to verify failure**

Run: `PY -m pytest tests/test_keyboards.py -q`
Expected: FAIL (`veo:refine` not in callbacks).

**Step 3: Implement**

Replace `prompt_review_keyboard` in `bot/keyboards/inline.py`:

```python
def prompt_review_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Accept", callback_data="veo:accept")],
        [InlineKeyboardButton(text="💬 Refine with instructions", callback_data="veo:refine")],
        [InlineKeyboardButton(text="✏️ Rewrite manually", callback_data="veo:edit")],
    ])
```

Add to `TikTokStates` in `bot/states/states.py` (after `editing_prompt`):

```python
    refining_prompt = State()
```

**Step 4: Run to verify pass**

Run: `PY -m pytest tests/test_keyboards.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add bot/keyboards/inline.py bot/states/states.py tests/test_keyboards.py
git commit -m "feat: add Refine-with-instructions option to veo review gate"
```

---

## Task 6: `GeminiService.refine_veo_prompt`

**Files:**
- Modify: `bot/services/gemini_service.py` (add `_refine_system`, `refine_veo_prompt`)
- Test: `tests/services/test_gemini_service.py`

**Step 1: Write the failing test**

Add to `tests/services/test_gemini_service.py`:

```python
def test_refine_system_includes_instruction_and_constraints():
    svc = GeminiService()
    sys = svc._refine_system(
        current_prompts=["A cat naps on a sunny windowsill."],
        instruction="make it more energetic",
        tone_profile={"voice": "bold"},
        mode="quick",
    )
    assert "make it more energetic" in sys
    assert "A cat naps on a sunny windowsill." in sys
    assert "8 second" in sys
    assert "text" in sys.lower()       # no-on-screen-text constraint preserved
    assert "bold" in sys
```

**Step 2: Run to verify failure**

Run: `PY -m pytest tests/services/test_gemini_service.py::test_refine_system_includes_instruction_and_constraints -q`
Expected: FAIL (`AttributeError: ... '_refine_system'`).

**Step 3: Implement**

Add to `GeminiService`:

```python
    def _refine_system(
        self, current_prompts: list[str], instruction: str, tone_profile: dict, mode: str,
    ) -> str:
        dur = settings.veo_duration_seconds
        joined = "\n\n".join(current_prompts)
        if mode == "full":
            fmt = (
                "Output the full set of scenes in the EXACT format "
                "'Scene 1: <description>' (one per line)."
            )
        else:
            fmt = "Output ONLY the single revised prompt text, no preamble."
        return (
            "You are revising an existing text-to-video prompt for a vertical 9:16 "
            "TikTok clip. Apply the user's instruction, keeping everything they did "
            "not ask to change. "
            f"Each shot is exactly {dur} seconds — keep the action within that time. "
            f"{self._NO_TEXT} "
            f"{fmt}\n\n"
            f"CURRENT PROMPT:\n{joined}\n\n"
            f"INSTRUCTION:\n{instruction}\n\n"
            f"Match this tone of voice: {json.dumps(tone_profile)}"
        )

    async def refine_veo_prompt(
        self, current_prompts: list[str], instruction: str, tone_profile: dict, mode: str,
    ) -> list[str]:
        system_prompt = self._refine_system(current_prompts, instruction, tone_profile, mode)
        text = await self._generate(instruction, [], system_prompt)
        if mode == "full":
            return self._split_scenes(text)
        return [text.strip()]
```

**Step 4: Run to verify pass**

Run: `PY -m pytest tests/services/test_gemini_service.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add bot/services/gemini_service.py tests/services/test_gemini_service.py
git commit -m "feat: GeminiService.refine_veo_prompt for instruction-driven revision"
```

---

## Task 7: Wire the refine loop into the TikTok handler

**Files:**
- Modify: `bot/handlers/tiktok.py` (add `veo:refine` callback + `refining_prompt` message handler; extract a re-show helper)
- Verify: manual (no handler unit tests in this repo)

**Step 1: Add a helper to re-display the review gate**

In `bot/handlers/tiktok.py`, add near the other helpers:

```python
async def _show_prompt_review(message: Message, state: FSMContext):
    data = await state.get_data()
    prompts = data.get("prompts", [])
    if data.get("video_mode") == "full":
        preview = "\n".join(f"Scene {i+1}: {p}" for i, p in enumerate(prompts))
    else:
        preview = prompts[0] if prompts else ""
    await state.set_state(TikTokStates.reviewing_prompt)
    await message.answer(
        f"Here's the video prompt:\n\n{preview}\n\nAccept it, refine, or rewrite?",
        reply_markup=prompt_review_keyboard(),
    )
```

**Step 2: Add the `veo:refine` callback handler** (after `on_prompt_edit`):

```python
@router.callback_query(TikTokStates.reviewing_prompt, F.data == "veo:refine")
async def on_prompt_refine(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TikTokStates.refining_prompt)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "What should I change? e.g. \"more energetic, sunset lighting, slower camera\""
    )
    await callback.answer()


@router.message(TikTokStates.refining_prompt)
async def on_prompt_refine_instruction(message: Message, state: FSMContext):
    instruction = (message.text or "").strip()
    if not instruction or instruction.startswith("/"):
        await message.answer("Send a plain-language instruction (not a command).")
        return
    data = await state.get_data()

    async with async_session_factory() as session:
        tov = await ToneOfVoiceRepository(session).get_active(message.from_user.id)
    tone_profile = tov.profile_json if tov else {}

    gemini = GeminiService()
    try:
        new_prompts = await gemini.refine_veo_prompt(
            current_prompts=data.get("prompts", []),
            instruction=instruction,
            tone_profile=tone_profile,
            mode=data.get("video_mode", "quick"),
        )
    except Exception as e:
        await _show_prompt_review(message, state)
        await message.answer(f"Couldn't refine that: {e}")
        return

    await state.update_data(prompts=new_prompts)
    await _show_prompt_review(message, state)
```

**Step 3: Run the full suite to confirm nothing broke**

Run: `PY -m pytest -q`
Expected: PASS (all prior tests + new ones).

**Step 4: Commit**

```bash
git add bot/handlers/tiktok.py
git commit -m "feat: instruction-driven refine loop in the veo review gate"
```

---

## Task 8: Full regression + manual smoke test

**Step 1: Full test run**

Run: `PY -m pytest -q`
Expected: all green (≥ 49 + the new tests).

**Step 2: Manual smoke test of the flow** (REQUIRED SUB-SKILL: superpowers:verification-before-completion)

Run the bot against Telegram (the user's normal launch) and walk the "🎬 Video from plot" flow:
1. Pick **⚡ Quick clip**, describe an idea, attach a **landscape** screenshot, `/done`.
2. At the review gate, confirm the 3 buttons appear. Hit **💬 Refine with instructions**, send "make it more energetic", confirm the prompt visibly changes and the gate re-appears.
3. Refine a second time to confirm it loops.
4. Accept → confirm the returned video is **vertical 9:16** (was previously flipping to landscape) and contains **no garbled text**.
5. Repeat with **🎬 Full video** and a multi-line edit to confirm scene cap = `veo_max_scenes`.

Record the observed results (verbatim) before claiming done.

**Step 3: Document the new env vars**

Add `VEO_DURATION_SECONDS` and `VEO_MAX_SCENES` (with defaults 8 / 3) to `.env.example` if those flows are documented there. Commit.

```bash
git add .env.example
git commit -m "docs: document VEO_DURATION_SECONDS and VEO_MAX_SCENES"
```

---

## Out of scope (do NOT implement here)

- **#6 / #7 — showing real screenshots exactly.** Deferred to a future montage/overlay (ffmpeg slideshow) or Veo reference-images session. Photos remain a single optional seed.

## Definition of done

- [ ] All tasks committed; `PY -m pytest -q` green.
- [ ] Manual smoke test: vertical output, no garbled text, working refine loop, refine loops more than once.
- [ ] New env vars documented.
- [ ] Branch ready for `superpowers:finishing-a-development-branch`.
