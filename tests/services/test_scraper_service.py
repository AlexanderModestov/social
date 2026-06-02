import pytest
import respx
import httpx
from bot.services.scraper_service import ScraperService

@pytest.mark.asyncio
async def test_scrape_extracts_text():
    html = "<html><body><p>Hello world</p><p>Second paragraph</p></body></html>"
    with respx.mock:
        respx.get("https://example.com/article").mock(
            return_value=httpx.Response(200, text=html)
        )
        service = ScraperService()
        text = await service.scrape_url("https://example.com/article")
    assert "Hello world" in text
    assert "Second paragraph" in text

@pytest.mark.asyncio
async def test_scrape_returns_empty_on_error():
    with respx.mock:
        respx.get("https://example.com/bad").mock(
            return_value=httpx.Response(404)
        )
        service = ScraperService()
        text = await service.scrape_url("https://example.com/bad")
    assert text == ""

@pytest.mark.asyncio
async def test_scrape_multiple_urls():
    html1 = "<html><body><p>Article one</p></body></html>"
    html2 = "<html><body><p>Article two</p></body></html>"
    with respx.mock:
        respx.get("https://example.com/one").mock(return_value=httpx.Response(200, text=html1))
        respx.get("https://example.com/two").mock(return_value=httpx.Response(200, text=html2))
        service = ScraperService()
        texts = await service.scrape_urls(["https://example.com/one", "https://example.com/two"])
    assert len(texts) == 2
    assert "Article one" in texts[0]
