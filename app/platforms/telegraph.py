import json

import httpx

from app.platforms.base import BasePlatform, PlatformError, make_title


class TelegraphPlatform(BasePlatform):
    name = "Telegraph"

    def is_configured(self) -> bool:
        return bool(self.settings.telegraph_access_token)

    async def publish(self, client: httpx.AsyncClient, message: str, url: str) -> str:
        before, _, after = message.partition(url)
        link = {"tag": "a", "attrs": {"href": url}, "children": [url]}
        paragraph = [part for part in (before, link, after) if part]

        response = await client.post(
            "https://api.telegra.ph/createPage",
            data={
                "access_token": self.settings.telegraph_access_token,
                "title": make_title(message, url),
                "content": json.dumps([{"tag": "p", "children": paragraph}]),
            },
        )
        response.raise_for_status()
        body = response.json()
        # Telegraph reports errors with HTTP 200 and "ok": false.
        if not body.get("ok"):
            raise PlatformError(f"Telegraph error: {body.get('error', 'unknown error')}")
        return body["result"]["url"]
