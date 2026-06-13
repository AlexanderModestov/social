"""Canonical channel slugs for per-channel tone of voice."""

INSTAGRAM = "instagram"
TIKTOK = "tiktok"
LINKEDIN = "linkedin"

# Order matters: drives picker + /settings display order.
CHANNELS: tuple[str, ...] = (INSTAGRAM, TIKTOK, LINKEDIN)

CHANNEL_LABELS = {
    INSTAGRAM: "📸 Instagram",
    TIKTOK: "🎵 TikTok",
    LINKEDIN: "💼 LinkedIn",
}
