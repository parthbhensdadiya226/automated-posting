import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app

VALID_MESSAGE = "Check out our latest business platform. https://example.com"
PLATFORM_COUNT = 5


def make_client(**credentials) -> TestClient:
    settings = Settings(_env_file=None, **credentials)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "message, expected_error",
    [
        ("", "must not be empty"),
        ("x" * 190 + " https://example.com", "must not exceed 200 characters"),
        ("No link in this message at all", "exactly one CTA link (found 0)"),
        ("Two links https://a.com and https://b.com", "exactly one CTA link (found 2)"),
        ("Broken link http://not_a_domain here", "not a valid URL"),
        ("Missing scheme www.example.com here", "not a valid URL"),
    ],
)
def test_invalid_messages_are_rejected(message, expected_error):
    response = make_client().post("/posting", json={"message": message})

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["errors"][0]["field"] == "message"
    assert expected_error in body["errors"][0]["message"]


def test_missing_message_field_is_rejected():
    response = make_client().post("/posting", json={})

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "message"


def test_message_of_exactly_200_characters_is_accepted():
    link = " https://example.com"
    message = "x" * (200 - len(link)) + link

    response = make_client().post("/posting", json={"message": message})

    assert response.status_code == 200


def test_link_followed_by_punctuation_is_accepted():
    response = make_client().post(
        "/posting", json={"message": "Visit us today at https://example.com/offers."}
    )

    assert response.status_code == 200


def test_unconfigured_platforms_are_reported_as_failed():
    response = make_client().post("/posting", json={"message": VALID_MESSAGE})

    body = response.json()
    assert body["success"] is False
    assert len(body["results"]) == PLATFORM_COUNT
    for result in body["results"]:
        assert result["status"] == "failed"
        assert result["posted_url"] is None
        assert "not configured" in result["error"]


@respx.mock
def test_one_platform_failing_does_not_stop_the_others():
    respx.post("https://mastodon.social/api/v1/statuses").mock(
        return_value=httpx.Response(200, json={"url": "https://mastodon.social/@me/1"})
    )
    respx.post("https://api.github.com/gists").mock(
        return_value=httpx.Response(401, json={"message": "Bad credentials"})
    )
    respx.post("https://dev.to/api/articles").mock(side_effect=httpx.ConnectTimeout("slow"))

    client = make_client(mastodon_access_token="token", github_token="BAD", devto_api_key="key")
    body = client.post("/posting", json={"message": VALID_MESSAGE}).json()

    assert body["success"] is True
    results = {result["platform"]: result for result in body["results"]}

    assert results["Mastodon"]["status"] == "success"
    assert results["Mastodon"]["posted_url"] == "https://mastodon.social/@me/1"
    assert results["Mastodon"]["public_access"] is True
    assert results["Mastodon"]["date"] and results["Mastodon"]["time"]
    assert results["Mastodon"]["error"] is None

    assert results["GitHub Gist"]["status"] == "failed"
    assert results["GitHub Gist"]["error"] == "Authentication failed (HTTP 401): Bad credentials"

    assert results["Dev.to"]["status"] == "failed"
    assert results["Dev.to"]["error"] == "Request timed out"


@respx.mock
def test_all_platforms_succeed():
    respx.post("https://mastodon.social/api/v1/statuses").mock(
        return_value=httpx.Response(200, json={"url": "https://mastodon.social/@me/1"})
    )
    respx.post("https://bsky.social/xrpc/com.atproto.server.createSession").mock(
        return_value=httpx.Response(
            200, json={"accessJwt": "jwt", "did": "did:plc:abc", "handle": "me.bsky.social"}
        )
    )
    bluesky_post = respx.post("https://bsky.social/xrpc/com.atproto.repo.createRecord").mock(
        return_value=httpx.Response(200, json={"uri": "at://did:plc:abc/app.bsky.feed.post/3kkey"})
    )
    respx.post("https://dev.to/api/articles").mock(
        return_value=httpx.Response(201, json={"url": "https://dev.to/me/post-1"})
    )
    respx.post("https://api.github.com/gists").mock(
        return_value=httpx.Response(201, json={"html_url": "https://gist.github.com/me/abc"})
    )
    respx.post("https://api.telegra.ph/createPage").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {"url": "https://telegra.ph/Post-11-16"}})
    )

    client = make_client(
        mastodon_access_token="token",
        bluesky_handle="me.bsky.social",
        bluesky_app_password="app-password",
        devto_api_key="key",
        github_token="token",
        telegraph_access_token="token",
    )
    body = client.post("/posting", json={"message": VALID_MESSAGE}).json()

    assert body["success"] is True
    results = {result["platform"]: result for result in body["results"]}
    assert len(results) == PLATFORM_COUNT
    assert all(result["status"] == "success" for result in results.values())
    assert results["Bluesky"]["posted_url"] == "https://bsky.app/profile/me.bsky.social/post/3kkey"
    assert results["Telegraph"]["posted_url"] == "https://telegra.ph/Post-11-16"

    record = json.loads(bluesky_post.calls.last.request.content)["record"]
    index = record["facets"][0]["index"]
    link_bytes = VALID_MESSAGE.encode()[index["byteStart"] : index["byteEnd"]]
    assert link_bytes.decode() == "https://example.com"


@respx.mock
def test_error_reported_inside_a_200_response_is_a_failure():
    respx.post("https://api.telegra.ph/createPage").mock(
        return_value=httpx.Response(200, json={"ok": False, "error": "ACCESS_TOKEN_INVALID"})
    )

    body = make_client(telegraph_access_token="wrong").post(
        "/posting", json={"message": VALID_MESSAGE}
    ).json()

    results = {result["platform"]: result for result in body["results"]}
    assert results["Telegraph"]["status"] == "failed"
    assert "ACCESS_TOKEN_INVALID" in results["Telegraph"]["error"]
