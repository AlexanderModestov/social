# Veo Prompt Fidelity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Veo prompts faithfully express the user's idea — beat-structured, action-and-speech-forward — and make `refine` apply clear edits or ask a clarifying question on ambiguous ones.

**Architecture:** Rewrite the three Gemini system-prompt builders around a shared spec (core-idea anchor, timestamp beats, action/subject before atmosphere, scripted dialogue). Add a JSON-output path for `refine` so Gemini returns a discriminated `revision | clarify` result; wire the handler to loop on clarify with accumulated context. Short mode stays one 8s Veo generation (beats inside a single take). No new FSM state.

**Tech Stack:** Python 3.10, aiogram 3, google-genai (Vertex AI, gemini-2.5-flash), pytest.

**Design doc:** `docs/plans/2026-06-13-veo-prompt-fidelity-design.md`

**Conventions (match these):**
- Tests are network-free: exercise pure builders/parsers, never the live API. `_generate`/`_generate_json` (network) and the async public methods are NOT unit-tested — that's verified in the manual smoke test, consistent with `write_veo_*` today.
- `PY` = `"C:\Users\aleks\Documents\Projects\social\.venv\Scripts\python.exe"`. Run with cwd = the worktree root `C:\Users\aleks\Documents\Projects\social\.worktrees\veo-quality-patches`, e.g. `PY -m pytest -q`.
- Keep prompt-strings in pure builder methods so tests assert substrings without the network.

---

## Task 1: Refine JSON plumbing — `_generate_json` + `_parse_refine_result`

**Files:**
- Modify: `bot/services/gemini_service.py`
- Test: `tests/services/test_gemini_service.py`

**Step 1: Write the failing tests**

```python
def test_parse_refine_result_revision_caps_at_max_scenes():
    svc = GeminiService()
    raw = {"kind": "revision", "prompts": [f"p{i}" for i in range(5)]}
    out = svc._parse_refine_result(raw, max_scenes=2)
    assert out["kind"] == "revision"
    assert out["prompts"] == ["p0", "p1"]


def test_parse_refine_result_clarify_returns_question():
    svc = GeminiService()
    out = svc._parse_refine_result({"kind": "clarify", "question": "Which dog?"}, max_scenes=3)
    assert out == {"kind": "clarify", "question": "Which dog?"}


def test_parse_refine_result_revision_without_prompts_raises():
    svc = GeminiService()
    with pytest.raises(ValueError):
        svc._parse_refine_result({"kind": "revision", "prompts": []}, max_scenes=3)


def test_parse_refine_result_unknown_kind_raises():
    svc = GeminiService()
    with pytest.raises(ValueError):
        svc._parse_refine_result({"kind": "wat"}, max_scenes=3)
```

`import pytest` is already at the top of the test file (used by existing tests). If not, add it.

**Step 2: Run to verify failure**

Run: `PY -m pytest tests/services/test_gemini_service.py -q`
Expected: FAIL (`AttributeError: ... '_parse_refine_result'`).

**Step 3: Implement** — in `bot/services/gemini_service.py`, add the pure parser and the JSON generate path:

```python
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
```

(`json` and `types` are already imported.)

**Step 4: Run to verify pass**

Run: `PY -m pytest tests/services/test_gemini_service.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add bot/services/gemini_service.py tests/services/test_gemini_service.py
git commit -m "feat: refine JSON plumbing (generate_json + parse_refine_result)"
```

---

## Task 2: Shared `_CORE_SPEC` + rewrite `_veo_prompt_system` (short)

**Files:**
- Modify: `bot/services/gemini_service.py`
- Test: `tests/services/test_gemini_service.py`

**Step 1: Write the failing tests** (replace the existing `test_veo_prompt_system_has_duration_and_no_text` with this stronger version, and add the new asserts):

```python
def test_veo_prompt_system_is_idea_anchored_and_actionforward():
    svc = GeminiService()
    sys = svc._veo_prompt_system({"voice": "punchy"})
    assert "CORE IDEA" in sys                 # anchors the user's idea
    assert "[00:00" in sys                    # timestamp-beat instruction
    assert "before atmosphere" in sys         # action/subject before mood
    assert "quotation marks" in sys           # scripted dialogue guidance
    assert "8 second" in sys                   # duration
    assert "text" in sys.lower()              # no-on-screen-text retained
    assert "punchy" in sys                    # tone injected
```

**Step 2: Run to verify failure**

Run: `PY -m pytest tests/services/test_gemini_service.py -q`
Expected: FAIL (old prompt has no "CORE IDEA"/"[00:00"/etc.).

**Step 3: Implement** — add a shared spec constant to the `GeminiService` class body (near `_NO_TEXT`), and rewrite `_veo_prompt_system` to use it:

```python
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
```

**Step 4: Run to verify pass**

Run: `PY -m pytest tests/services/test_gemini_service.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add bot/services/gemini_service.py tests/services/test_gemini_service.py
git commit -m "feat: idea-anchored, beat-structured, action-forward short prompt"
```

---

## Task 3: Rewrite `_veo_scenes_system` (full)

**Files:**
- Modify: `bot/services/gemini_service.py`
- Test: `tests/services/test_gemini_service.py`

**Step 1: Write the failing test** (replace the existing `test_veo_scenes_system_has_duration_and_no_text`):

```python
def test_veo_scenes_system_is_idea_anchored_and_beatstructured():
    svc = GeminiService()
    sys = svc._veo_scenes_system({}, max_scenes=3)
    assert "CORE IDEA" in sys
    assert "[00:00" in sys
    assert "before atmosphere" in sys
    assert "quotation marks" in sys
    assert "8 second" in sys
    assert "text" in sys.lower()
    assert "3" in sys                          # max_scenes injected
    assert "Scene 1:" in sys                   # scene output format
```

**Step 2: Run to verify failure**

Run: `PY -m pytest tests/services/test_gemini_service.py -q`
Expected: FAIL.

**Step 3: Implement** — rewrite `_veo_scenes_system` to reuse `_CORE_SPEC`:

```python
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
```

Note: `_split_scenes` still splits on the `Scene N:` marker; the `[00:00-...]` beats live *inside* each scene's text and don't collide with that regex. No change to `_split_scenes`.

**Step 4: Run to verify pass**

Run: `PY -m pytest tests/services/test_gemini_service.py -q`
Expected: PASS (existing `_split_scenes` tests still pass).

**Step 5: Commit**

```bash
git add bot/services/gemini_service.py tests/services/test_gemini_service.py
git commit -m "feat: idea-anchored beat-structured full-video scene prompts"
```

---

## Task 4: Refine = apply-or-clarify via JSON

**Files:**
- Modify: `bot/services/gemini_service.py` (`_refine_system`, `refine_veo_prompt`)
- Test: `tests/services/test_gemini_service.py`

**Step 1: Write the failing test** (replace `test_refine_system_includes_instruction_and_constraints`):

```python
def test_refine_system_asks_json_and_keeps_constraints():
    svc = GeminiService()
    sys = svc._refine_system(
        current_prompts=["A cat naps on a sunny windowsill."],
        instruction="make it more energetic",
        tone_profile={"voice": "bold"},
        mode="quick",
    )
    assert "make it more energetic" in sys
    assert "A cat naps on a sunny windowsill." in sys
    assert '"kind"' in sys                     # JSON shape specified
    assert "revision" in sys and "clarify" in sys
    assert "before atmosphere" in sys          # core spec preserved
    assert "8 second" in sys
    assert "text" in sys.lower()
    assert "bold" in sys
```

**Step 2: Run to verify failure**

Run: `PY -m pytest tests/services/test_gemini_service.py -q`
Expected: FAIL.

**Step 3: Implement** — rewrite `_refine_system` to demand JSON apply-or-clarify, and rewire `refine_veo_prompt` to return the discriminated dict:

```python
    def _refine_system(
        self, current_prompts: list[str], instruction: str, tone_profile: dict, mode: str,
    ) -> str:
        dur = settings.veo_duration_seconds
        joined = "\n\n".join(current_prompts)
        shape = (
            "Respond with ONLY a JSON object. If the instruction is clear, apply it and "
            'return {"kind": "revision", "prompts": ["<full revised prompt>"]} — for a '
            'full video put one revised scene per array element. If the instruction is '
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
```

NOTE: `refine_veo_prompt` return type changes from `list[str]` to `dict` (`{kind, prompts|question}`). The handler is updated in Task 5.

**Step 4: Run to verify pass**

Run: `PY -m pytest tests/services/test_gemini_service.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add bot/services/gemini_service.py tests/services/test_gemini_service.py
git commit -m "feat: refine returns discriminated revision|clarify via JSON"
```

---

## Task 5: Wire the clarify-loop into the handler

**Files:**
- Modify: `bot/handlers/tiktok.py` (`on_prompt_refine`, `on_prompt_refine_instruction`)
- Verify: full suite + import check (no handler unit tests in this repo)

**Step 1: Reset refine context when entering refine.** In `on_prompt_refine`, add a context reset so each refine session starts clean. The handler currently sets state and prompts the user; add before answering:

```python
@router.callback_query(TikTokStates.reviewing_prompt, F.data == "veo:refine")
async def on_prompt_refine(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TikTokStates.refining_prompt)
    await state.update_data(refine_context="")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "What should I change? e.g. \"more energetic, sunset lighting, slower camera\""
    )
    await callback.answer()
```

**Step 2: Replace `on_prompt_refine_instruction`** with the clarify-loop version:

```python
@router.message(TikTokStates.refining_prompt)
async def on_prompt_refine_instruction(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        await message.answer("Send a plain-language instruction (not a command).")
        return
    data = await state.get_data()
    prev = data.get("refine_context", "")
    refine_context = f"{prev}\n{text}".strip() if prev else text

    async with async_session_factory() as session:
        tov = await ToneOfVoiceRepository(session).get_active(message.from_user.id)
    tone_profile = tov.profile_json if tov else {}

    gemini = GeminiService()
    try:
        result = await gemini.refine_veo_prompt(
            current_prompts=data.get("prompts", []),
            instruction=refine_context,
            tone_profile=tone_profile,
            mode=data.get("video_mode", "quick"),
        )
    except Exception as e:
        await state.update_data(refine_context="")
        await _show_prompt_review(message, state)
        await message.answer(f"Couldn't refine that: {e}")
        return

    if result["kind"] == "clarify":
        await state.update_data(refine_context=refine_context)
        await message.answer(result["question"])
        return  # stay in refining_prompt to receive the answer

    await state.update_data(prompts=result["prompts"], refine_context="")
    await _show_prompt_review(message, state)
```

Behavior: clear instruction → revision applied → back to the gate. Ambiguous → bot asks a question and stays in `refining_prompt`; the next message is appended to `refine_context` so Gemini sees instruction + question + answer. Error/parse-failure → back to the gate with the prompt intact (retryable), context reset.

**Step 3: Run the full suite + import check**

Run: `PY -m pytest -q`  → all green (no new tests; nothing should break).
Run: `PY -c "import os; os.environ.update(TELEGRAM_BOT_TOKEN='t',ANTHROPIC_API_KEY='a',GCP_PROJECT_ID='p',DATABASE_URL='sqlite+aiosqlite:///:memory:'); import bot.handlers.tiktok; print('IMPORT OK')"` → prints IMPORT OK.

**Step 4: Commit**

```bash
git add bot/handlers/tiktok.py
git commit -m "feat: refine clarify-loop wiring in the veo review gate"
```

---

## Task 6: Full regression + manual smoke test

**Step 1: Full test run** — `PY -m pytest -q` → all green (≥ 59 + the new parser/builder tests, minus the replaced ones; net should be ~62).

**Step 2: Manual smoke test** (REQUIRED SUB-SKILL: superpowers:verification-before-completion). Run the bot and walk 🎬 Video from plot:
1. **⚡ Quick clip**: give a short idea that has a clear action + someone speaking (e.g. "a barista slams an espresso on the counter and says 'order up!'"). Accept → confirm the video performs the ACTION and the SPEECH, reflects the idea, is vertical 9:16, no on-screen text.
2. At the gate, **Refine** with a clear edit ("make her smile and add steam") → confirm it's applied and the gate returns.
3. **Refine** with a deliberately vague edit ("make it better") → confirm the bot asks a clarifying question and applies your answer.
4. **🎬 Full video**: a multi-beat idea → confirm scenes carry the idea across, each beat-structured, within `VEO_MAX_SCENES`.

Record observed results verbatim before claiming done.

---

## Out of scope
- Real-screenshot reproduction (#6/#7) — still deferred.
- Per-video voiced-dialogue toggle.
- Real cuts / multi-clip short mode.

## Definition of done
- [ ] Tasks 1-5 committed; `PY -m pytest -q` green.
- [ ] Manual smoke: idea reflected with action + speech, in budget, vertical, no text; refine applies clear edits and asks on ambiguous ones.
- [ ] Branch finished via superpowers:finishing-a-development-branch.
