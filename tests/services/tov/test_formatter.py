from bot.services.tov.formatter import format_tov_profile
from bot.db.channels import LINKEDIN, TIKTOK


def test_format_linkedin_profile_renders_key_sections():
    profile = {
        "handle": "alexander-modestov",
        "posts_analyzed": 3,
        "persona_summary": "A pragmatic operator who writes from the trenches.",
        "archetype": "pragmatic operator",
        "language": {"primary": "English ~100%", "register": "thought-leader"},
        "hook_patterns": [
            {"name": "bold claim", "frequency": "~40%", "description": "opens with a contrarian take"},
        ],
        "structure": {"post_shape": "story -> lesson -> CTA", "formatting": "short lines"},
        "themes": ["leadership", "shipping"],
        "cta_patterns": ["asks a question", "invites DMs"],
        "dos": ["be specific", "use real numbers"],
        "donts": ["no buzzwords"],
        "signature_elements": {"emoji": "sparing", "hashtags": "1-2 max", "phrases": ["ship it"]},
    }
    out = format_tov_profile(LINKEDIN, profile)

    assert "@alexander-modestov" in out and "3 posts analyzed" in out
    assert "pragmatic operator" in out                      # archetype
    assert "trenches" in out                                # persona
    assert "thought-leader" in out                          # language register
    assert "bold claim" in out                              # hook pattern
    assert "story -> lesson -> CTA" in out                  # structure
    assert "leadership" in out                              # themes
    assert "invites DMs" in out                             # cta
    assert "be specific" in out and "no buzzwords" in out   # dos/donts
    assert "ship it" in out                                 # signature phrase


def test_format_tov_profile_degrades_on_sparse_dict():
    # Missing everything but the header fields — must not raise.
    out = format_tov_profile(TIKTOK, {"handle": "x", "posts_analyzed": 0})
    assert "@x" in out
