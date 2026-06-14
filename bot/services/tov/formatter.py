"""Generic tone-of-voice formatter for the channel-tuned TOV schemas.

Renders the LinkedIn/TikTok schemas produced by ``bot.services.tov.prompts``
(and degrades gracefully on any subset of fields). Instagram keeps its own
richer formatter in ``bot.services.instagram_tov_formatter`` for parity.
"""
from bot.db.channels import CHANNEL_LABELS


def format_tov_profile(channel: str, profile: dict) -> str:
    label = CHANNEL_LABELS.get(channel, channel)
    handle = profile.get("handle") or profile.get("username") or ""
    posts = profile.get("posts_analyzed", 0)
    lines = [f"{label} @{handle} — {posts} posts analyzed\n"]

    if profile.get("persona_summary"):
        lines.append(f"👤 Persona: {profile['persona_summary']}")
    if profile.get("archetype"):
        lines.append(f"🎭 Archetype: {profile['archetype']}")

    lang = profile.get("language") or {}
    lang_str = lang.get("primary", "")
    if lang.get("secondary"):
        lang_str += f" / {lang['secondary']}"
    extra = lang.get("mixing_note") or lang.get("register")
    if extra:
        lang_str += f" ({extra})"
    if lang_str:
        lines.append(f"\n🌍 Language: {lang_str}")

    # Channel-specific key: LinkedIn/TikTok use hook_patterns, IG caption_patterns.
    patterns = profile.get("hook_patterns") or profile.get("caption_patterns") or []
    if patterns:
        lines.append("\n🪝 Patterns:")
        for p in patterns:
            freq = p.get("frequency", "")
            suffix = f" ({freq})" if freq else ""
            lines.append(f"• {p.get('name', '')}{suffix}: {p.get('description', '')}")

    structure = profile.get("structure") or {}
    if structure.get("post_shape"):
        lines.append(f"\n🧱 Structure: {structure['post_shape']}")
    if structure.get("formatting"):
        lines.append(f"   Formatting: {structure['formatting']}")

    pacing = profile.get("pacing") or {}
    if pacing.get("energy"):
        lines.append(f"\n⚡ Energy: {pacing['energy']}")
    if pacing.get("caption_length"):
        lines.append(f"   Caption length: {pacing['caption_length']}")

    themes = profile.get("themes") or (profile.get("motifs") or {}).get("themes") or []
    if themes:
        lines.append(f"\n🎯 Themes: {', '.join(themes)}")

    ctas = [c for c in (profile.get("cta_patterns") or []) if c]
    if ctas:
        lines.append(f"\n📣 CTAs: {'; '.join(ctas)}")

    dos = profile.get("dos") or []
    if dos:
        lines.append("\n✅ Do:")
        lines += [f"• {d}" for d in dos]

    donts = profile.get("donts") or []
    if donts:
        lines.append("\n🚫 Don't:")
        lines += [f"• {d}" for d in donts]

    sig = profile.get("signature_elements") or {}
    style_parts = [s for s in [sig.get("punctuation"), sig.get("hashtags"), sig.get("emoji")] if s]
    if style_parts:
        lines.append(f"\n✍️ Style: {' | '.join(style_parts)}")
    phrases = sig.get("phrases") or []
    if phrases:
        lines.append(f"💬 Phrases: {', '.join(repr(p) for p in phrases)}")

    return "\n".join(lines)
