# Veo Prompt Fidelity Redesign

**Date:** 2026-06-13
**Status:** Approved design, ready for implementation planning
**Branch:** `feature/veo-quality-patches`
**Flow affected:** TikTok → "🎬 Video from plot" (Veo 3.1 on Vertex AI)
**Files:** `bot/services/gemini_service.py`, `bot/handlers/tiktok.py` (states unchanged)

---

## Background

After the Veo quality patches (`docs/plans/2026-06-10-veo-quality-patches-design.md`),
the generated prompts have a fidelity problem: they don't faithfully express the user's
idea, and they over-index on atmosphere at the expense of action and speech. Four reported
issues, all rooted in the prompt-engineering shipped in that round:

| # | Symptom | Root cause |
|---|---------|-----------|
| 1 | Generated prompt doesn't carry the user's key idea | Nothing anchors the user's core idea; embellishment displaces it. |
| 2 | Short (≤8s) prompt lacks shot framing; description too thin; video incomplete | `_veo_prompt_system` says "ONE continuous action… do not pack a longer story… 2-4 sentences." Under-describes and ignores beat structure. |
| 3 | `refine` doesn't reliably understand/apply requested changes | `_refine_system` is one-shot best-effort; no clarification path; weak "apply the change" wording. |
| 4 | Prompt is atmosphere/mood-heavy; barely covers character actions, speech, appearance | Both builders enumerate "subject, camera, lighting, mood" — never *actions, dialogue, appearance*. |

This redesign is a **prompt-engineering overhaul** that recalibrates the prior round's
constraints toward idea-faithful, beat-structured, action-and-speech-forward prompts, plus
a refine clarify-loop. The "no on-screen text" rule is retained (spoken dialogue is audio,
not on-screen captions, so there is no conflict).

### Grounding: Google's Veo 3.1 prompt guidance

Source: [Ultimate prompting guide for Veo 3.1](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1).
The redesign adopts its recommendations:
- **Formula:** `[Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance]`.
- **Timestamp prompting** for multi-beat sequences within ONE generation:
  `[00:00–00:02] … [00:02–00:04] …`.
- **Dialogue** via quotes: `A woman says, "We have to leave now."` (Veo lip-syncs).
- **Sound** via `SFX:` and `Ambient noise:` directives.

### Decisions taken (from brainstorming)

- **Short-clip "shot breakdown" = beat-structured single take.** Short mode stays ONE Veo
  generation (8s); richness comes from timestamp beats inside that continuous take — not
  real cuts and not multi-clip stitching.
- **Refine = ask back when unclear.** Ambiguous instruction → bot asks a short clarifying
  question and waits; clear instruction → applies directly. No per-change changelog.
- **Dialogue = scripted when implied, in the user's language.** When the idea involves
  speech, include short quoted lines + delivery; otherwise invent none. AI audio quality
  variance is an accepted Veo limitation.

---

## Section 1 — Prompt generation (issues #1, #2, #4)

Both builders (`_veo_prompt_system`, `_veo_scenes_system`) are rewritten around a shared spec:

1. **Anchor the core idea first.** Instruct Gemini to first identify the user's central
   action/event/message, state it must remain the focus, and treat every added detail as
   serving it — never replacing it.
2. **Beat-structured, timestamped take.** Replace "one continuous action / 2-4 sentences"
   with timestamp beats spanning the full duration — e.g. for 8s, 2–4 beats like
   `[00:00–00:03] … [00:03–00:06] … [00:06–00:08] …`. Beat count/pacing chosen from the
   idea's content; beats must be performable within their seconds.
3. **Action- and subject-forward, balanced.** Each beat specifies cinematography,
   **subject (who + appearance)**, **action (concrete things they DO)**, context, and
   style/ambiance — with action/subject ordered *before* atmosphere so mood stops crowding
   out what actually happens.
4. **Full mode** keeps ≤`max_scenes` scenes; each scene is itself beat-structured, and the
   core idea / continuity carries across scenes.
5. Retains the **no-on-screen-text** rule (`_NO_TEXT`).

This deliberately recalibrates the Task 3 constraints that caused #2/#4. We drop "one
simple action / don't pack a story / 2-4 sentences" in favor of "fully express the idea,
beat-structured, fit the time."

## Section 2 — Dialogue, audio, fixed rules (issue #4 speech)

1. **Scripted dialogue when implied.** If the idea involves people speaking, include short
   spoken lines via Veo's quoted form — `A woman says, "…"` — **in the user's language**,
   with a delivery/tone note. If no speech is implied, invent none.
2. **Sound direction.** Beats may include `SFX:` / `Ambient noise:` directives where they
   serve the idea — sparingly, never crowding out dialogue/action.
3. **`generate_audio=True` stays on** in `veo_service.py` (already set).
4. **No on-screen text stays** (`_NO_TEXT` unchanged). Spoken dialogue is audio, not
   captions — no conflict.
5. **Language handling.** Dialogue stays in the user's language (Russian idea → Russian
   lines), mitigating wrong-language audio as far as the model allows.
6. **Time budget.** Spec tells Gemini to keep spoken lines short enough to be delivered
   within the beat's seconds, so speech doesn't blow the duration budget.

## Section 3 — Refine clarify-loop (issue #3)

`refine_veo_prompt` returns one of two outcomes, decided by Gemini via **structured (JSON)
output** with a `kind` discriminator:

- **`{kind: "revision", prompts: [...]}`** — instruction was clear; apply it (preserving
  everything not asked to change) and loop back to the review gate (as today).
- **`{kind: "clarify", question: "..."}`** — instruction ambiguous; bot sends the short
  question and **stays in `refining_prompt`** to receive the answer.

**Context carries across the exchange.** State holds a small running `refine_context`
(original instruction + any clarifying Q&A). Each message in `refining_prompt` is appended
to that context and re-submitted, so when the user answers a clarifying question, Gemini
sees the original instruction + its question + the answer, then produces the revision.
Loops until a revision is returned (or the user leaves the gate).

**Why JSON:** a `kind`-discriminated schema is far more reliable than parsing free text to
infer "question vs. prompt." Add a JSON-returning generate variant alongside the text
`_generate`; keep `_refine_system` a pure, network-free string builder. The refine system
prompt is also strengthened: actually *apply* the change ("even if it alters earlier
style/detail"), and only ask a question when genuinely ambiguous — never as a stall.

## Section 4 — Code mapping, errors, testing

**Files touched** (branch `feature/veo-quality-patches`):
- `bot/services/gemini_service.py` — rewrite the three system-prompt builders around the
  shared spec; add a JSON-returning generate path + a pure parser helper; change
  `refine_veo_prompt` to return a discriminated `revision | clarify` result.
- `bot/handlers/tiktok.py` — `on_prompt_refine_instruction` handles both outcomes:
  clarify → send question, accumulate `refine_context`, stay in `refining_prompt`;
  revision → update prompts, back to gate. Empty/`/`-command guard stays.
- `bot/states/states.py` — no new state (`refining_prompt` is reused for the clarify turn).

**Error handling.** JSON parse/validation failure or a Gemini error in refine falls back
gracefully: return to the review gate with the existing prompt intact + a short "couldn't
refine, try rephrasing" message (mirrors the existing retryable pattern — never strands the
user or clears state).

**Testing** (network-free, matching repo convention):
- Builder assertions: each system prompt contains the core-idea anchor, the timestamp-beat
  instruction, action-before-atmosphere ordering, the dialogue/quote guidance, and the
  duration/no-text constraints.
- Pure JSON parser: valid `revision` → prompts list; valid `clarify` → question; malformed
  → raises/handled.
- `refine_veo_prompt` shape per mode (quick→1, full→list) on the revision path.
- Existing 59 tests stay green.
- Real Gemini/Veo behavior (idea reflected, action + speech present, within budget) is
  verified in the **manual smoke test** — the only true proof.

## Out of scope

- Real-screenshot reproduction (#6/#7 from the prior round) — still deferred.
- Per-video voiced-dialogue toggle — not added (dialogue is auto, when implied).
- Real cuts within a short clip / multi-clip short mode — rejected in favor of beat-take.

## Definition of done

- [ ] Three builders rewritten; refine returns discriminated result; handler loops on clarify.
- [ ] Network-free tests green (≥ 59) covering builders, JSON parser, refine shapes.
- [ ] Manual smoke test: short + full videos reflect the idea with action & speech, in
      budget, vertical, no on-screen text; refine applies clear edits and asks on ambiguous.
- [ ] Implementation plan written and executed; branch finished via
      superpowers:finishing-a-development-branch.
