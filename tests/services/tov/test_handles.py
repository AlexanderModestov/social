import pytest
from bot.services.tov.handles import extract_handle
from bot.db.channels import INSTAGRAM, TIKTOK, LINKEDIN

@pytest.mark.parametrize("channel,raw,expected", [
    (INSTAGRAM, "@alex", "alex"),
    (INSTAGRAM, "https://instagram.com/alex/", "alex"),
    (TIKTOK, "@alex", "alex"),
    (TIKTOK, "https://www.tiktok.com/@alex?lang=en", "alex"),
    (LINKEDIN, "https://www.linkedin.com/in/alex-smith/", "alex-smith"),
    (LINKEDIN, "alex-smith", "alex-smith"),
])
def test_extract_handle(channel, raw, expected):
    assert extract_handle(channel, raw) == expected

def test_extract_handle_empty_raises():
    with pytest.raises(ValueError):
        extract_handle(INSTAGRAM, "   ")
