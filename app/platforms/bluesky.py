from datetime import datetime, timezone

import httpx

from app.platforms.base import BasePlatform

PDS_URL = "https://bsky.social"


class BlueskyPlatform(BasePlatform):
    name = "Bluesky"

    def is_configured(self) -> bool:
        return bool(self.settings.bluesky_handle and self.settings.bluesky_app_password)

    async def publish(self, client: httpx.AsyncClient, message: str, url: str) -> str:
        login = await client.post(
            f"{PDS_URL}/xrpc/com.atproto.server.createSession",
            json={
                "identifier": self.settings.bluesky_handle.lstrip("@"),
                "password": self.settings.bluesky_app_password,
            },
        )
        login.raise_for_status()
        session = login.json()

        # Bluesky does not auto-link URLs; a facet marks the link's byte range.
        start = message.encode("utf-8").find(url.encode("utf-8"))
        record = {
            "$type": "app.bsky.feed.post",
            "text": message,
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "facets": [
                {
                    "index": {"byteStart": start, "byteEnd": start + len(url.encode("utf-8"))},
                    "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}],
                }
            ],
        }

        response = await client.post(
            f"{PDS_URL}/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {session['accessJwt']}"},
            json={"repo": session["did"], "collection": "app.bsky.feed.post", "record": record},
        )
        response.raise_for_status()

        record_key = response.json()["uri"].rsplit("/", 1)[-1]
        return f"https://bsky.app/profile/{session['handle']}/post/{record_key}"
