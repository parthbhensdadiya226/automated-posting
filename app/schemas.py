import re
from typing import List, Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

MAX_MESSAGE_LENGTH = 200

_LINK_PATTERN = re.compile(r"(?:https?://|www\.)[^\s<>\"]+", re.IGNORECASE)
_TRAILING_PUNCTUATION = ".,;:!?)]}'\""
_HOSTNAME_PATTERN = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", re.IGNORECASE
)


def extract_links(text: str) -> List[str]:
    return [match.rstrip(_TRAILING_PUNCTUATION) for match in _LINK_PATTERN.findall(text)]


def is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        parsed.port
    except ValueError:
        return False
    if parsed.scheme.lower() not in ("http", "https"):
        return False
    return bool(_HOSTNAME_PATTERN.match(parsed.hostname or ""))


class PostingRequest(BaseModel):
    message: str = Field(
        ...,
        examples=["Check out our latest business platform and grow your online visibility. https://example.com"],
    )

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        message = value.strip()
        if not message:
            raise ValueError("Message must not be empty.")
        if len(message) > MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"Message must not exceed {MAX_MESSAGE_LENGTH} characters (received {len(message)})."
            )
        links = extract_links(message)
        if len(links) != 1:
            raise ValueError(f"Message must contain exactly one CTA link (found {len(links)}).")
        if not is_valid_url(links[0]):
            raise ValueError(
                f"The CTA link '{links[0]}' is not a valid URL. "
                "It must start with http:// or https:// and use a real domain."
            )
        return message

    @property
    def cta_url(self) -> str:
        return extract_links(self.message)[0]


class PlatformResult(BaseModel):
    platform: str
    status: Literal["success", "failed"]
    posted_url: Optional[str] = None
    public_access: bool = False
    date: Optional[str] = None
    time: Optional[str] = None
    error: Optional[str] = None


class PostingResponse(BaseModel):
    success: bool
    results: List[PlatformResult]


class ValidationErrorItem(BaseModel):
    field: str
    message: str


class ValidationErrorResponse(BaseModel):
    success: bool = False
    errors: List[ValidationErrorItem]
