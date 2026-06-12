from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎭 Create tone of voice", callback_data="action:tone_of_voice")],
        [InlineKeyboardButton(text="✍️ Create content", callback_data="action:create_content")],
    ])


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
        [InlineKeyboardButton(text="⚡ Quick clip (5–8s)", callback_data="videomode:quick")],
        [InlineKeyboardButton(text="🎬 Full video (≤3 scenes)", callback_data="videomode:full")],
    ])


def prompt_review_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Accept", callback_data="veo:accept"),
         InlineKeyboardButton(text="✏️ Edit", callback_data="veo:edit")],
    ])


def tov_method_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧙 Answer a few questions", callback_data="tov:wizard")],
        [InlineKeyboardButton(text="📸 Import from Instagram", callback_data="tov:instagram")],
    ])
