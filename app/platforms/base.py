import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import httpx

from app.config import Settings
from app.schemas import PlatformResult

logger = logging.getLogger("automated_posting")


class PlatformError(Exception):
    pass


def make_title(message: str, url: str, max_length: int = 60) -> str:
    text = " ".join(message.replace(url, " ").split()).strip(" .,;:!?-")
    if not text:
        return "New post"
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rsplit(" ", 1)[0].rstrip(" .,;:!?-") + "..."


def describe_http_error(response: httpx.Response) -> str:
    status = response.status_code
    if status in (401, 403):
        label = "Authentication failed"
    elif status == 429:
        label = "Rate limit exceeded"
    elif status >= 500:
        label = "Platform server error"
    else:
        label = "Request rejected"

    detail = ""
    try:
        body = response.json()
        if isinstance(body, dict):
            for key in ("message", "error_description", "error"):
                if isinstance(body.get(key), str) and body[key]:
                    detail = body[key][:150]
                    break
    except ValueError:
        pass

    text = f"{label} (HTTP {status})"
    return f"{text}: {detail}" if detail else text


class BasePlatform(ABC):
    name: str = "Platform"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    async def publish(self, client: httpx.AsyncClient, message: str, url: str) -> str:
        """Publish the message and return the public URL of the post."""

    async def post(self, client: httpx.AsyncClient, message: str, url: str) -> PlatformResult:
        if not self.is_configured():
            return self._failed("Platform not configured (missing credentials)")

        try:
            posted_url = await self.publish(client, message, url)
        except httpx.TimeoutException:
            return self._failed("Request timed out")
        except httpx.HTTPStatusError as exc:
            return self._failed(describe_http_error(exc.response))
        except httpx.RequestError as exc:
            return self._failed(f"Network error: {type(exc).__name__}")
        except PlatformError as exc:
            return self._failed(str(exc))
        except (KeyError, TypeError, ValueError):
            return self._failed("Unexpected response format from platform")
        except Exception as exc:
            logger.exception("%s: unexpected failure", self.name)
            return self._failed(f"Unexpected error: {type(exc).__name__}")

        now = datetime.now(timezone.utc)
        logger.info("%s: posted to %s", self.name, posted_url)
        return PlatformResult(
            platform=self.name,
            status="success",
            posted_url=posted_url,
            public_access=True,
            date=now.strftime("%Y-%m-%d"),
            time=now.strftime("%H:%M:%S"),
        )

    def _failed(self, error: str) -> PlatformResult:
        logger.warning("%s: failed - %s", self.name, error)
        return PlatformResult(platform=self.name, status="failed", error=error)
