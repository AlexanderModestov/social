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
    kb = tov_method_keyboard()
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    assert len(buttons) == 2

def test_tov_method_keyboard_callback_data():
    kb = tov_method_keyboard()
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "tov:wizard" in callbacks
    assert "tov:instagram" in callbacks

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
