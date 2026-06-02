import httpx
from bs4 import BeautifulSoup


class ScraperService:
    async def scrape_url(self, url: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if response.status_code != 200:
                    return ""
                soup = BeautifulSoup(response.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
                return "\n".join(line for line in text.splitlines() if line.strip())
        except Exception:
            return ""

    async def scrape_urls(self, urls: list[str]) -> list[str]:
        import asyncio
        return await asyncio.gather(*[self.scrape_url(url) for url in urls])
