import asyncio
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright


class PlaywrightService:
    VIEWPORT = {"width": 390, "height": 844}
    RECORD_DURATION = 15

    async def record_product_demo(self, url: str) -> str:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {url}")

        output_dir = Path(tempfile.mkdtemp())

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport=self.VIEWPORT,
                record_video_dir=str(output_dir),
                record_video_size=self.VIEWPORT,
            )
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, window.innerHeight * 0.6)")
                await asyncio.sleep(self.RECORD_DURATION / 5)
            video = page.video  # capture reference before close
            await page.close()
            await context.close()
            video_path = await video.path()
            await browser.close()

        return video_path
