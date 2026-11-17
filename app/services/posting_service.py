import asyncio
from typing import List, Type

import httpx

from app.config import Settings
from app.platforms.base import BasePlatform
from app.platforms.bluesky import BlueskyPlatform
from app.platforms.devto import DevToPlatform
from app.platforms.github_gist import GitHubGistPlatform
from app.platforms.mastodon import MastodonPlatform
from app.platforms.telegraph import TelegraphPlatform
from app.schemas import PostingResponse

PLATFORM_CLASSES: List[Type[BasePlatform]] = [
    MastodonPlatform,
    BlueskyPlatform,
    DevToPlatform,
    GitHubGistPlatform,
    TelegraphPlatform,
]


async def publish_to_all(message: str, url: str, settings: Settings) -> PostingResponse:
    platforms = [platform_class(settings) for platform_class in PLATFORM_CLASSES]

    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        results = await asyncio.gather(
            *(platform.post(client, message, url) for platform in platforms)
        )

    return PostingResponse(
        success=any(result.status == "success" for result in results),
        results=list(results),
    )
