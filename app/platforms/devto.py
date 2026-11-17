import httpx

from app.platforms.base import BasePlatform, make_title


class DevToPlatform(BasePlatform):
    name = "Dev.to"

    def is_configured(self) -> bool:
        return bool(self.settings.devto_api_key)

    async def publish(self, client: httpx.AsyncClient, message: str, url: str) -> str:
        response = await client.post(
            "https://dev.to/api/articles",
            headers={
                "api-key": self.settings.devto_api_key,
                "Accept": "application/vnd.forem.api-v1+json",
            },
            json={
                "article": {
                    "title": make_title(message, url),
                    "body_markdown": message,
                    "published": True,
                }
            },
        )
        response.raise_for_status()
        return response.json()["url"]
