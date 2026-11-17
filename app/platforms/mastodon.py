import httpx

from app.platforms.base import BasePlatform


class MastodonPlatform(BasePlatform):
    name = "Mastodon"

    def is_configured(self) -> bool:
        return bool(self.settings.mastodon_base_url and self.settings.mastodon_access_token)

    async def publish(self, client: httpx.AsyncClient, message: str, url: str) -> str:
        base_url = self.settings.mastodon_base_url.rstrip("/")
        response = await client.post(
            f"{base_url}/api/v1/statuses",
            headers={"Authorization": f"Bearer {self.settings.mastodon_access_token}"},
            json={"status": message, "visibility": "public"},
        )
        response.raise_for_status()
        return response.json()["url"]
