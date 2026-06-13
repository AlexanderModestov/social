from bot.services.tov.preprocess import preprocess_posts
from bot.db.channels import INSTAGRAM, TIKTOK


def test_preprocess_filters_empty_and_counts():
    posts = [{"caption": "Привет мир"}, {"caption": ""}, {"caption": "Hello world"}]
    data = preprocess_posts(INSTAGRAM, posts)
    assert data["posts_with_text"] == 2
    assert data["total_posts"] == 3
    assert data["avg_text_length"] > 0
    langs = data["language_counts"]
    assert langs["ru"] == 1 and langs["en"] == 1


def test_preprocess_tiktok_channel():
    posts = [{"text": "Привет мир"}, {"text": "Hello world"}, {"text": ""}]
    data = preprocess_posts(TIKTOK, posts)
    assert data["total_posts"] == 3
    assert data["posts_with_text"] == 2
    langs = data["language_counts"]
    assert langs["ru"] == 1 and langs["en"] == 1


def test_preprocess_empty_returns_zero_counts():
    data = preprocess_posts(INSTAGRAM, [])
    assert data["total_posts"] == 0
    assert data["posts_with_text"] == 0
    assert data["avg_text_length"] == 0
    assert data["language_counts"] == {"ru": 0, "en": 0, "mixed": 0}
    assert data["texts"] == []
