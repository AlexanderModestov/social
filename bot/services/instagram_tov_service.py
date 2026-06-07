import httpx


class PrivateProfileError(Exception):
    pass


class NoPostsError(Exception):
    pass


class ServiceError(Exception):
    pass


class InstagramTovService:
    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")

    async def analyze(self, username: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.post(
                    f"{self._base_url}/analyze",
                    json={"username": username},
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 404:
                try:
                    detail = e.response.json().get("detail", "")
                except Exception:
                    detail = ""
                if "No posts" in detail:
                    raise NoPostsError(detail) from e
                raise PrivateProfileError(str(e)) from e
            raise ServiceError(str(e)) from e
        except httpx.TransportError as e:
            raise ServiceError(str(e)) from e
