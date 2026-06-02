import pytest
from bot.services.playwright_service import PlaywrightService

@pytest.mark.asyncio
async def test_record_validates_url():
    service = PlaywrightService()
    with pytest.raises(ValueError, match="Invalid URL"):
        await service.record_product_demo("not-a-valid-url")

@pytest.mark.asyncio
async def test_record_validates_url_no_scheme():
    service = PlaywrightService()
    with pytest.raises(ValueError, match="Invalid URL"):
        await service.record_product_demo("example.com/page")
