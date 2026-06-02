from bot.db.models import User, ToneOfVoice, PostHistory

def test_user_model_has_required_fields():
    u = User(telegram_id=123, username="alex")
    assert u.telegram_id == 123
    assert u.username == "alex"

def test_tone_of_voice_has_is_active():
    tov = ToneOfVoice(user_id=1, name="Pro Alex", profile_json={}, is_active=True)
    assert tov.is_active is True

def test_post_history_has_platform():
    ph = PostHistory(user_id=1, platform="linkedin", format="post", input_data={}, output_data={})
    assert ph.platform == "linkedin"
