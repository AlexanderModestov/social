def format_instagram_profile(profile: dict) -> str:
    lines = [
        f"📸 @{profile['username']} — {profile['posts_analyzed']} posts analyzed\n",
        f"👤 Persona: {profile.get('persona_summary', '')}",
        f"🎭 Archetype: {profile.get('archetype', '')}",
    ]

    dims = profile.get("voice_dimensions") or []
    if dims:
        lines.append("\n🗣 Voice dimensions:")
        for d in dims:
            lines.append(f"• {d['name']}: {d['description']}")

    lang = profile.get("language") or {}
    lang_str = lang.get("primary", "")
    if lang.get("secondary"):
        lang_str += f" / {lang['secondary']}"
    if lang.get("mixing_note"):
        lang_str += f" ({lang['mixing_note']})"
    lines.append(f"\n🌍 Language: {lang_str}")

    patterns = profile.get("caption_patterns") or []
    if patterns:
        lines.append("\n📝 Caption patterns:")
        for p in patterns:
            lines.append(f"• {p['name']} ({p.get('frequency', '')}): {p['description']}")

    motifs = profile.get("motifs") or {}
    if motifs.get("themes"):
        lines.append(f"\n🎯 Themes: {', '.join(motifs['themes'])}")
    if motifs.get("places"):
        lines.append(f"📍 Places: {', '.join(motifs['places'])}")
    if motifs.get("sensory"):
        lines.append(f"👃 Sensory: {', '.join(motifs['sensory'])}")

    dos = profile.get("dos") or []
    if dos:
        lines.append("\n✅ Do:")
        for d in dos:
            lines.append(f"• {d}")

    donts = profile.get("donts") or []
    if donts:
        lines.append("\n🚫 Don't:")
        for d in donts:
            lines.append(f"• {d}")

    sig = profile.get("signature_elements") or {}
    style_parts = [s for s in [sig.get("punctuation"), sig.get("hashtags")] if s]
    if style_parts:
        lines.append(f"\n✍️ Style: {' | '.join(style_parts)}")
    phrases = sig.get("phrases") or []
    if phrases:
        lines.append(f"💬 Phrases: {', '.join(repr(p) for p in phrases)}")

    return "\n".join(lines)


def split_message(text: str, max_len: int = 4096) -> list[str]:
    if len(text) <= max_len:
        return [text]
    parts = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at <= 0:
            split_at = max_len
        parts.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return parts
