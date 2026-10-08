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


# --- redirects: every hop is a new request, to an address the model never named -----------------------------------------------------


def serve(monkeypatch, handler):
    """Fetcher over a fake network: example.com and other.example resolve to public addresses, an IP literal to itself."""
    monkeypatch.setattr("socket.gethostbyname", lambda host: {"example.com": "93.184.216.34", "other.example": "93.184.216.35"}.get(host, host))
    requests: list[str] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return handler(request)

    real_client = httpx.AsyncClient

    class PatchedClient(real_client):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(record)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("stepout.fetch.httpx.AsyncClient", PatchedClient)
    return requests


@pytest.mark.parametrize("target", ["http://127.0.0.1:8765/api/conversations", "http://10.0.0.5/admin", "file:///etc/passwd", "http://localhost/"])
async def test_a_redirect_to_a_private_or_local_address_is_blocked_before_it_is_requested(monkeypatch, target):
    requests = serve(monkeypatch, lambda request: httpx.Response(302, headers={"location": target}))
    with pytest.raises(BlockedUrl):
        await Fetcher().get("https://example.com/start")
    assert requests == ["https://example.com/start"]  # the second request was never sent


async def test_redirects_through_public_hosts_are_followed_and_a_relative_one_is_resolved(monkeypatch):
    def handler(request):
        match request.url.path:
            case "/a":
                return httpx.Response(301, headers={"location": "https://other.example/b"})
            case "/b":
                return httpx.Response(302, headers={"location": "/c"})
            case _:
                return httpx.Response(200, text="<p>arrived</p>")

    requests = serve(monkeypatch, handler)
    page = await Fetcher().get("https://example.com/a")
    assert page.text == "arrived" and page.url == "https://other.example/c"
    assert requests == ["https://example.com/a", "https://other.example/b", "https://other.example/c"]


async def test_a_redirect_loop_stops(monkeypatch):
    requests = serve(monkeypatch, lambda request: httpx.Response(302, headers={"location": "https://example.com/again"}))
    with pytest.raises(BlockedUrl, match="too many redirects"):
        await Fetcher().get("https://example.com/start")
    assert len(requests) <= 6
