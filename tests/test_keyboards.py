from bot.keyboards.inline import main_menu_keyboard, platform_keyboard, tiktok_subtype_keyboard, tov_method_keyboard

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
    kb = tov_method_keyboard()
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    assert len(buttons) == 2

def test_tov_method_keyboard_callback_data():
    kb = tov_method_keyboard()
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "tov:wizard" in callbacks
    assert "tov:instagram" in callbacks

from bot.keyboards.inline import linkedin_menu_keyboard


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
