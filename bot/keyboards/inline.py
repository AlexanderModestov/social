from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import settings
from bot.db.channels import CHANNELS, CHANNEL_LABELS


def main_menu_keyboard(channels_with_tov: set[str] | None = None) -> InlineKeyboardMarkup:
    channels_with_tov = channels_with_tov or set()
    rows = []
    if set(channels_with_tov) != set(CHANNELS):
        rows.append([InlineKeyboardButton(text="🎭 Create tone of voice", callback_data="action:tone_of_voice")])
    rows.append([InlineKeyboardButton(text="✍️ Create content", callback_data="action:create_content")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def platform_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💼 LinkedIn post", callback_data="platform:linkedin")],
        [InlineKeyboardButton(text="🎵 TikTok video", callback_data="platform:tiktok")],
    ])


def linkedin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Write post", callback_data="li:post-writer")],
        [InlineKeyboardButton(text="💬 Draft comment", callback_data="li:comment-drafter"),
         InlineKeyboardButton(text="↩️ Draft reply", callback_data="li:reply-handler")],
        [InlineKeyboardButton(text="🧹 Humanize", callback_data="li:humanizer"),
         InlineKeyboardButton(text="🔎 Audit", callback_data="li:post-audit")],
        [InlineKeyboardButton(text="🪝 Hook extractor", callback_data="li:hook-extractor"),
         InlineKeyboardButton(text="📊 Engagement", callback_data="li:engagement-monitor")],
        [InlineKeyboardButton(text="👤 Profile", callback_data="li:profile-optimizer")],
        [InlineKeyboardButton(text="🗓 7-day plan", callback_data="li:content-planner"),
         InlineKeyboardButton(text="🤝 Advocacy", callback_data="li:employee-advocacy")],
    ])


def tiktok_subtype_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Product demo", callback_data="tiktok:product_demo")],
        [InlineKeyboardButton(text="🎬 Video from plot", callback_data="tiktok:video_plot")],
    ])


def post_actions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Regenerate", callback_data="post:regenerate"),
         InlineKeyboardButton(text="✏️ Edit", callback_data="post:edit")],
        [InlineKeyboardButton(text="💾 Save", callback_data="post:save")],
        [InlineKeyboardButton(text="🚀 Publish", callback_data="post:publish")],
    ])


def linkedin_report_keyboard(extra_rows=None) -> InlineKeyboardMarkup:
    rows = list(extra_rows or [])
    rows.append([InlineKeyboardButton(text="💾 Save", callback_data="skill:save")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def humanizer_modes_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Strict", callback_data="hmz:strict"),
         InlineKeyboardButton(text="Aesthetic", callback_data="hmz:aesthetic"),
         InlineKeyboardButton(text="Forensic", callback_data="hmz:forensic")],
        [InlineKeyboardButton(text="💾 Save", callback_data="skill:save")],
    ])


def tone_of_voice_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Save", callback_data="tov:save"),
         InlineKeyboardButton(text="🔄 Regenerate", callback_data="tov:regenerate")],
    ])


def style_words_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    words = ["Formal", "Casual", "Inspiring", "Analytical", "Direct", "Storyteller"]
    rows = []
    for i in range(0, len(words), 3):
        row = []
        for word in words[i:i+3]:
            prefix = "✅ " if word in selected else ""
            row.append(InlineKeyboardButton(
                text=f"{prefix}{word}",
                callback_data=f"style:{word}"
            ))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="➡️ Continue", callback_data="style:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def video_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⚡ Quick clip ({settings.veo_duration_seconds}s)", callback_data="videomode:quick")],
        [InlineKeyboardButton(text=f"🎬 Full video (≤{settings.veo_max_scenes} scenes)", callback_data="videomode:full")],
    ])


def prompt_review_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Accept", callback_data="veo:accept")],
        [InlineKeyboardButton(text="💬 Refine with instructions", callback_data="veo:refine")],
        [InlineKeyboardButton(text="✏️ Rewrite manually", callback_data="veo:edit")],
    ])


def tov_channel_picker_keyboard(channels_with_tov: set[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=CHANNEL_LABELS[c], callback_data=f"tovchan:{c}")]
        for c in CHANNELS if c not in channels_with_tov
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def tov_method_keyboard(channel: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧙 Answer a few questions", callback_data=f"tovm:wizard:{channel}")],
        [InlineKeyboardButton(text="📥 Import from my profile", callback_data=f"tovm:import:{channel}")],
    ])


def settings_keyboard(channels_with_tov: set[str]) -> InlineKeyboardMarkup:
    rows = []
    for c in CHANNELS:
        if c in channels_with_tov:
            rows.append([
                InlineKeyboardButton(text=f"{CHANNEL_LABELS[c]} · ✏️ Recreate", callback_data=f"settings:create:{c}"),
                InlineKeyboardButton(text="🗑 Delete", callback_data=f"settings:delete:{c}"),
            ])
        else:
            rows.append([InlineKeyboardButton(text=f"{CHANNEL_LABELS[c]} · ➕ Create", callback_data=f"settings:create:{c}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
