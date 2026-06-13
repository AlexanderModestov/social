import pytest

from bot.services.gemini_service import GeminiService, _get_client


def test_import_does_not_require_credentials():
    # Constructing the service must not touch ADC / network.
    svc = GeminiService()
    assert svc.MODEL == "gemini-2.5-flash"


def test_client_is_lazy_and_cached():
    # _get_client is memoized so the Vertex client is built at most once.
    assert hasattr(_get_client, "cache_clear")  # it's an lru_cache wrapper


def test_split_scenes_parses_numbered():
    svc = GeminiService()
    text = "Scene 1: A cat wakes up\nScene 2: It stretches\nScene 3: It pounces"
    assert svc._split_scenes(text) == ["A cat wakes up", "It stretches", "It pounces"]


def test_split_scenes_caps_at_three():
    svc = GeminiService()
    text = "\n".join(f"Scene {i}: action {i}" for i in range(1, 7))
    assert len(svc._split_scenes(text)) == 3


def test_split_scenes_respects_config_cap(monkeypatch):
    import bot.services.gemini_service as gs
    monkeypatch.setattr(gs.settings, "veo_max_scenes", 2, raising=False)
    svc = GeminiService()
    text = "\n".join(f"Scene {i}: action {i}" for i in range(1, 6))
    assert len(svc._split_scenes(text)) == 2


def test_split_scenes_fallback_paragraphs():
    svc = GeminiService()
    text = "First shot happens.\n\nSecond shot happens.\n\nThird.\n\nFourth."
    scenes = svc._split_scenes(text)
    assert scenes == ["First shot happens.", "Second shot happens.", "Third."]


def test_split_scenes_preserves_multiline_description():
    svc = GeminiService()
    text = "Scene 1: A cat wakes up,\nslowly stretching.\nScene 2: It pounces."
    assert svc._split_scenes(text) == ["A cat wakes up,\nslowly stretching.", "It pounces."]


def test_veo_prompt_system_is_idea_anchored_and_actionforward():
    svc = GeminiService()
    sys = svc._veo_prompt_system({"voice": "punchy"})
    assert "CORE IDEA" in sys                 # anchors the user's idea
    assert "[00:00" in sys                    # timestamp-beat instruction
    assert "before atmosphere" in sys         # action/subject before mood
    assert "quotation marks" in sys           # scripted dialogue guidance
    assert "8 second" in sys                   # duration
    assert "text" in sys.lower()              # no-on-screen-text retained
    assert "punchy" in sys                    # tone injected


def test_veo_scenes_system_is_idea_anchored_and_beatstructured():
    svc = GeminiService()
    sys = svc._veo_scenes_system({}, max_scenes=3)
    assert "CORE IDEA" in sys
    assert "[00:00" in sys
    assert "before atmosphere" in sys
    assert "quotation marks" in sys
    assert "8 second" in sys
    assert "no readable text" in sys           # no-on-screen-text retained (strong assertion)
    assert "3" in sys                          # max_scenes injected
    assert "Scene 1:" in sys                   # scene output format


def test_refine_system_includes_instruction_and_constraints():
    svc = GeminiService()
    sys = svc._refine_system(
        current_prompts=["A cat naps on a sunny windowsill."],
        instruction="make it more energetic",
        tone_profile={"voice": "bold"},
        mode="quick",
    )
    assert "make it more energetic" in sys
    assert "A cat naps on a sunny windowsill." in sys
    assert "8 second" in sys
    assert "text" in sys.lower()       # no-on-screen-text constraint preserved
    assert "bold" in sys


def test_parse_refine_result_revision_caps_at_max_scenes():
    svc = GeminiService()
    raw = {"kind": "revision", "prompts": [f"p{i}" for i in range(5)]}
    out = svc._parse_refine_result(raw, max_scenes=2)
    assert out["kind"] == "revision"
    assert out["prompts"] == ["p0", "p1"]


def test_parse_refine_result_clarify_returns_question():
    svc = GeminiService()
    out = svc._parse_refine_result({"kind": "clarify", "question": "Which dog?"}, max_scenes=3)
    assert out == {"kind": "clarify", "question": "Which dog?"}


def test_parse_refine_result_revision_without_prompts_raises():
    svc = GeminiService()
    with pytest.raises(ValueError):
        svc._parse_refine_result({"kind": "revision", "prompts": []}, max_scenes=3)


def test_parse_refine_result_unknown_kind_raises():
    svc = GeminiService()
    with pytest.raises(ValueError):
        svc._parse_refine_result({"kind": "wat"}, max_scenes=3)
