from bot.keyboards.inline import main_menu_keyboard, platform_keyboard, prompt_review_keyboard, tiktok_subtype_keyboard, tov_method_keyboard, video_mode_keyboard

def test_main_menu_has_two_buttons():
    kb = main_menu_keyboard()
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    assert len(buttons) == 2

def test_platform_keyboard_has_linkedin_and_tiktok():
    kb = platform_keyboard()
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "platform:linkedin" in callbacks
    assert "platform:tiktok" in callbacks

def test_tiktok_subtype_has_two_options():
    kb = tiktok_subtype_keyboard()
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    assert len(buttons) == 2

def test_tov_method_keyboard_has_two_buttons():
    from bot.db.channels import INSTAGRAM
    kb = tov_method_keyboard(INSTAGRAM)
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    assert len(buttons) == 2

def test_tov_method_keyboard_callback_data():
    from bot.db.channels import INSTAGRAM
    kb = tov_method_keyboard(INSTAGRAM)
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "tovm:wizard:instagram" in callbacks
    assert "tovm:import:instagram" in callbacks

def test_prompt_review_keyboard_has_accept_refine_edit():
    kb = prompt_review_keyboard()
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "veo:accept" in callbacks
    assert "veo:refine" in callbacks
    assert "veo:edit" in callbacks

def test_video_mode_keyboard_labels_reflect_settings():
    from bot.config import settings
    kb = video_mode_keyboard()
    labels = [btn.text for row in kb.inline_keyboard for btn in row]
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert any(f"{settings.veo_duration_seconds}s" in l for l in labels)
    assert any(f"{settings.veo_max_scenes} scenes" in l for l in labels)
    assert "videomode:quick" in callbacks and "videomode:full" in callbacks


from bot.keyboards.inline import linkedin_menu_keyboard


def test_post_actions_keyboard_has_publish():
    from bot.keyboards.inline import post_actions_keyboard
    data = [b.callback_data for row in post_actions_keyboard().inline_keyboard for b in row]
    assert "post:publish" in data
    # existing actions still present
    for cb in ("post:regenerate", "post:edit", "post:save"):
        assert cb in data


def test_humanizer_modes_keyboard_has_modes_and_save():
    from bot.keyboards.inline import humanizer_modes_keyboard
    data = [b.callback_data for row in humanizer_modes_keyboard().inline_keyboard for b in row]
    for cb in ("hmz:strict", "hmz:aesthetic", "hmz:forensic", "skill:save"):
        assert cb in data


def test_linkedin_menu_has_all_skills():
    kb = linkedin_menu_keyboard()
    data = [b.callback_data for row in kb.inline_keyboard for b in row]
    for skill in [
        "li:post-writer", "li:comment-drafter", "li:reply-handler",
        "li:humanizer", "li:post-audit", "li:hook-extractor",
        "li:engagement-monitor", "li:profile-optimizer",
        "li:content-planner", "li:employee-advocacy",
    ]:
        assert skill in data


from bot.keyboards.inline import (
    tov_channel_picker_keyboard, settings_keyboard,
)
from bot.db.channels import CHANNELS, INSTAGRAM, TIKTOK, LINKEDIN

def _labels(kb):
    return [b.text for row in kb.inline_keyboard for b in row]

def test_main_menu_shows_create_tov_when_channel_missing():
    kb = main_menu_keyboard(channels_with_tov={LINKEDIN})
    assert any("tone of voice" in t.lower() for t in _labels(kb))

def test_main_menu_hides_create_tov_when_all_present():
    kb = main_menu_keyboard(channels_with_tov=set(CHANNELS))
    assert not any("tone of voice" in t.lower() for t in _labels(kb))

def test_picker_lists_only_missing_channels():
    kb = tov_channel_picker_keyboard(channels_with_tov={LINKEDIN})
    data = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "tovchan:instagram" in data and "tovchan:tiktok" in data
    assert "tovchan:linkedin" not in data

def test_method_keyboard_carries_channel():
    kb = tov_method_keyboard(INSTAGRAM)
    data = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "tovm:wizard:instagram" in data and "tovm:import:instagram" in data

def test_settings_shows_status_per_channel():
    kb = settings_keyboard(channels_with_tov={INSTAGRAM})
    data = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "settings:delete:instagram" in data       # created → delete/edit
    assert "settings:create:tiktok" in data           # missing → create
