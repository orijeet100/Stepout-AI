import httpx
import pytest

from stepout.fetch import BlockedUrl, Fetcher, _check_policy, _html_to_text

BLOCKED_URLS = [
    "file:///etc/passwd",
    "http://localhost/",
    "http://127.0.0.1/",
    "http://192.168.1.1/",
    "http://10.0.0.5/",
]


def test_policy_blocks_file_and_local_and_private_addresses():
    for url in BLOCKED_URLS:
        with pytest.raises(BlockedUrl):
            _check_policy(url)


def test_html_to_text_strips_tags():
    assert _html_to_text("<p>Hello <b>world</b></p>") == "Hello world"


async def test_fetch_happy_path(monkeypatch):
    monkeypatch.setattr("socket.gethostbyname", lambda host: "93.184.216.34")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<p>sunny, 70F</p>")

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    class PatchedClient(real_client):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("stepout.fetch.httpx.AsyncClient", PatchedClient)

    page = await Fetcher().get("https://example.com/weather")
    assert page.text == "sunny, 70F"
