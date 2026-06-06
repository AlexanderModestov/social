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


def test_split_scenes_fallback_paragraphs():
    svc = GeminiService()
    text = "First shot happens.\n\nSecond shot happens.\n\nThird.\n\nFourth."
    scenes = svc._split_scenes(text)
    assert scenes == ["First shot happens.", "Second shot happens.", "Third."]


def test_split_scenes_preserves_multiline_description():
    svc = GeminiService()
    text = "Scene 1: A cat wakes up,\nslowly stretching.\nScene 2: It pounces."
    assert svc._split_scenes(text) == ["A cat wakes up,\nslowly stretching.", "It pounces."]
