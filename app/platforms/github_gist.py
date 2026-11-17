import httpx

from app.platforms.base import BasePlatform, make_title


class GitHubGistPlatform(BasePlatform):
    name = "GitHub Gist"

    def is_configured(self) -> bool:
        return bool(self.settings.github_token)

    async def publish(self, client: httpx.AsyncClient, message: str, url: str) -> str:
        response = await client.post(
            "https://api.github.com/gists",
            headers={
                "Authorization": f"Bearer {self.settings.github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={
                "description": make_title(message, url),
                "public": True,
                "files": {"post.md": {"content": message}},
            },
        )
        response.raise_for_status()
        return response.json()["html_url"]
