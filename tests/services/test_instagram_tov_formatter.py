from bot.services.instagram_tov_formatter import format_instagram_profile, split_message

FULL_PROFILE = {
    "username": "alex",
    "posts_analyzed": 47,
    "persona_summary": "A reflective creator.",
    "archetype": "Urban nomad",
    "voice_dimensions": [{"name": "Warmth", "description": "Always approachable."}],
    "language": {"primary": "English ~80%", "secondary": "Russian ~20%", "mixing_note": "switches mid-post"},
    "caption_patterns": [{"name": "Observation", "frequency": "~60%", "description": "Starts with a scene.", "examples": ["Walking through..."]}],
    "motifs": {"themes": ["travel", "coffee"], "places": ["Berlin"], "sensory": ["rain smell"]},
    "dos": ["Be specific", "Use metaphors"],
    "donts": ["Avoid clichés"],
    "signature_elements": {"punctuation": "ellipses often", "hashtags": "1-2 only", "phrases": ["you know", "just"]},
}


def test_format_contains_username():
    text = format_instagram_profile(FULL_PROFILE)
    assert "@alex" in text
    assert "47 posts analyzed" in text


def test_format_contains_persona_and_archetype():
    text = format_instagram_profile(FULL_PROFILE)
    assert "reflective creator" in text
    assert "Urban nomad" in text


def test_format_contains_dos_and_donts():
    text = format_instagram_profile(FULL_PROFILE)
    assert "Be specific" in text
    assert "Avoid clichés" in text


def test_format_contains_voice_dimensions():
    text = format_instagram_profile(FULL_PROFILE)
    assert "Warmth" in text


def test_format_contains_language():
    text = format_instagram_profile(FULL_PROFILE)
    assert "English" in text
    assert "Russian" in text


def test_format_contains_motifs():
    text = format_instagram_profile(FULL_PROFILE)
    assert "travel" in text
    assert "Berlin" in text


def test_format_contains_phrases():
    text = format_instagram_profile(FULL_PROFILE)
    assert "you know" in text


def test_split_message_short_stays_as_one():
    parts = split_message("hello", max_len=4096)
    assert parts == ["hello"]


def test_split_message_long_splits_on_newline():
    chunk = "a" * 2000
    text = chunk + "\n" + chunk + "\n" + chunk
    parts = split_message(text, max_len=4096)
    assert len(parts) == 2
    for p in parts:
        assert len(p) <= 4096
