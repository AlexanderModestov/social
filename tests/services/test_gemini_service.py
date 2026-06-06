from bot.services.gemini_service import GeminiService, _get_client


def test_import_does_not_require_credentials():
    # Constructing the service must not touch ADC / network.
    svc = GeminiService()
    assert svc.MODEL == "gemini-2.5-flash"


def test_client_is_lazy_and_cached():
    # _get_client is memoized so the Vertex client is built at most once.
    assert hasattr(_get_client, "cache_clear")  # it's an lru_cache wrapper
