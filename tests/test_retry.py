"""The retry policy (ADR 0015): every row of the table, offline, with a fake clock. Nothing here sleeps."""

import asyncio
import math

import pytest

from stepout import scope
from stepout.domain import AnswerAction
from stepout.failure import Failure
from stepout.model import HAIKU, PRICING, ModelRequest, ModelResponse
from stepout.retry import RetryingModel
from stepout.scope import RunScope
from tests.support.faulty_model import Cut, FaultyModel


def ok(text="fine", cost=0.001):
    return ModelResponse(action=AnswerAction(text=text), cost_usd=cost)


def request(user_text="u"):
    return ModelRequest(model=HAIKU, system="s", user_text=user_text)


class Rig:
    """A RetryingModel over scripted outcomes, inside a Run scope that records what it was told."""

    def __init__(self, *outcomes, budget=math.inf, with_scope=True):
        self.inner = FaultyModel(*outcomes)
        self.sleeps: list[float] = []
        self.events: list[tuple[str, str, dict]] = []
        self.resets = 0
        self.charged = 0.0
        self.words: list[str] = []

        async def sleep(seconds):
            self.sleeps.append(seconds)

        async def emit(kind, summary, **data):
            self.events.append((kind, summary, data))

        async def reset():
            self.resets += 1

        def charge(usd):
            self.charged += usd

        self.model = RetryingModel(self.inner, sleep=sleep, rng=lambda: 1.0)  # rng 1.0: no jitter shaved off, so waits are exactly 1, 2, 4 ...
        self.scope = RunScope(run_id="r", task_id="t", conversation_id="c", emit=emit, reset_stream=reset, budget_left=lambda: budget, charge=charge) if with_scope else None

    async def call(self, streaming=False):
        async def on_text(words):
            self.words.append(words)

        token = scope.enter(self.scope) if self.scope else None
        try:
            return await self.model.call(request(), on_text if streaming else None)
        finally:
            if token is not None:
                scope.leave(token)

    def retries(self):
        return [data for kind, _, data in self.events if kind == "retry"]


async def test_a_rate_limit_waits_as_told_then_succeeds():
    rig = Rig(Failure("rate_limit", "slow down", 429, retry_after=2.0), ok())
    response = await rig.call()
    assert response.attempts == 2 and rig.sleeps == [2.0]
    (event,) = rig.retries()
    assert (event["cause"], event["status"], event["attempt"], event["wait_s"]) == ("rate_limit", 429, 1, 2.0)
    assert rig.scope.retries == 1 and rig.scope.retry_wait_s == 2.0


async def test_a_retry_after_beyond_the_ceiling_fails_fast_and_names_the_wait():
    rig = Rig(Failure("rate_limit", "slow down", 429, retry_after=120.0), ok())
    with pytest.raises(Failure) as caught:
        await rig.call()
    assert rig.inner.calls == 1 and rig.sleeps == []
    assert caught.value.kind == "rate_limit" and "2 minutes" in caught.value.message


async def test_an_overloaded_provider_is_retried_with_growing_waits():
    rig = Rig(Failure("overloaded", "busy", 529), Failure("overloaded", "busy", 529), ok())
    response = await rig.call()
    assert response.attempts == 3 and rig.sleeps == [1.0, 2.0] and len(rig.retries()) == 2


async def test_three_failures_in_a_row_end_with_the_providers_own_line():
    rig = Rig(Failure("overloaded", "busy", 529), Failure("overloaded", "busy", 529), Failure("overloaded", "still busy", 529), ok())
    with pytest.raises(Failure) as caught:
        await rig.call()
    assert rig.inner.calls == 3 and caught.value.message == "still busy"


@pytest.mark.parametrize("kind", ["server_error", "timeout", "connection"])
async def test_the_other_transient_kinds_are_retried_too(kind):
    rig = Rig(Failure(kind, "x"), ok())
    assert (await rig.call()).attempts == 2


@pytest.mark.parametrize("kind", ["auth", "no_key", "credit", "rejected", "pricing", "no_search", "internal"])
async def test_a_failure_that_will_not_change_is_never_retried(kind):
    rig = Rig(Failure(kind, "no"), ok())
    with pytest.raises(Failure):
        await rig.call()
    assert rig.inner.calls == 1 and rig.sleeps == [] and rig.events == []


async def test_a_stream_cut_after_words_tells_the_page_to_drop_them_and_tries_once_more():
    rig = Rig(Cut(["Hel", "lo"], Failure("connection", "cut")), ok("Hello"))
    response = await rig.call(streaming=True)
    assert rig.words == ["Hel", "lo"] and rig.resets == 1 and response.attempts == 2


async def test_a_stream_that_is_cut_twice_stops_after_two_attempts():
    rig = Rig(Cut(["a"], Failure("connection", "cut")), Cut(["b"], Failure("connection", "cut again")), ok())
    with pytest.raises(Failure):
        await rig.call(streaming=True)
    assert rig.inner.calls == 2


async def test_a_cut_stream_is_charged_an_estimate_of_what_it_was_sent():
    rig = Rig(Cut(["words"], Failure("connection", "cut")), ok())
    await rig.call(streaming=True)
    estimate = (len("s") + len("u")) / 4 * PRICING[HAIKU][0] / 1_000_000
    assert rig.charged == pytest.approx(estimate) and rig.retries()[0]["cost"] == pytest.approx(estimate)


async def test_a_failure_before_any_byte_costs_nothing():
    rig = Rig(Failure("connection", "refused"), ok())
    await rig.call()
    assert rig.charged == 0.0


async def test_without_a_scope_a_cut_stream_cannot_be_dropped_so_it_is_not_retried():
    rig = Rig(Cut(["a"], Failure("connection", "cut")), ok(), with_scope=False)
    with pytest.raises(Failure):
        await rig.call(streaming=True)
    assert rig.inner.calls == 1


async def test_without_a_scope_screening_still_gets_the_policy():
    rig = Rig(Failure("overloaded", "busy", 529), ok(), with_scope=False)
    assert (await rig.call()).attempts == 2 and rig.events == []


async def test_one_run_retries_at_most_eight_times():
    rig = Rig(Failure("overloaded", "busy", 529), ok())
    rig.scope.retries = 8
    with pytest.raises(Failure):
        await rig.call()
    assert rig.inner.calls == 1


async def test_one_run_waits_at_most_sixty_seconds_in_all():
    rig = Rig(Failure("overloaded", "busy", 529), ok())
    rig.scope.retry_wait_s = 59.5  # the next wait is 1 s
    with pytest.raises(Failure):
        await rig.call()
    assert rig.inner.calls == 1 and rig.sleeps == []


async def test_no_retry_starts_when_the_budget_is_used_up():
    rig = Rig(Failure("overloaded", "busy", 529), ok(), budget=0.0)
    with pytest.raises(Failure):
        await rig.call()
    assert rig.inner.calls == 1


async def test_stop_during_a_wait_ends_the_call_at_once():
    waiting = asyncio.Event()

    async def hang(seconds):
        waiting.set()
        await asyncio.Event().wait()  # never set: only a cancel gets out

    rig = Rig(Failure("overloaded", "busy", 529), ok())
    rig.model = RetryingModel(rig.inner, sleep=hang, rng=lambda: 1.0)

    task = asyncio.ensure_future(rig.call())
    await waiting.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert rig.inner.calls == 1


async def test_a_success_reports_how_long_it_took_and_how_many_tries():
    response = await Rig(ok()).call()
    assert response.attempts == 1 and response.duration_ms >= 0


def test_what_the_inner_model_declares_is_passed_through():
    assert RetryingModel(FaultyModel()).streams is True
    assert getattr(RetryingModel(object()), "streams", False) is False


# --- a reply that cannot be read is asked for once more, with what was wrong (never the value) ---


def unreadable(cost=0.002, detail="step: int_parsing"):
    return Failure("malformed", "The model's reply could not be understood.", detail=detail, cost_usd=cost)


async def test_an_unreadable_reply_is_repaired_once_with_what_was_wrong():
    rig = Rig(unreadable(), ok("fixed"))
    response = await rig.call()
    assert response.action.text == "fixed" and response.attempts == 2
    first, second = (r.user_text for r in rig.inner.requests)
    assert first == "u" and second.startswith("u\n\n") and "step: int_parsing" in second
    assert "could not be understood" not in second  # the User-facing line is not fed back
    (event,) = rig.retries()
    assert event["cause"] == "malformed" and event["repair"] is True and rig.sleeps == []
    assert rig.charged == pytest.approx(0.002) and rig.scope.repairs == 1


async def test_a_second_unreadable_reply_ends_the_call_and_both_were_billed():
    rig = Rig(unreadable(0.002), unreadable(0.003), ok())
    with pytest.raises(Failure) as caught:
        await rig.call()
    assert caught.value.kind == "malformed" and rig.inner.calls == 2
    assert rig.charged == pytest.approx(0.005)


async def test_a_run_repairs_at_most_three_replies():
    rig = Rig(unreadable(), ok())
    rig.scope.repairs = 3
    with pytest.raises(Failure):
        await rig.call()
    assert rig.inner.calls == 1


async def test_no_repair_is_asked_for_when_the_budget_is_used_up():
    rig = Rig(unreadable(), ok(), budget=0.0)
    with pytest.raises(Failure):
        await rig.call()
    assert rig.inner.calls == 1


# --- the Fetcher retries what a second try can cure, and nothing else ---


class FlakyFetcher:
    def __init__(self, *outcomes):
        self._outcomes, self.urls = list(outcomes), []

    async def get(self, url):
        from stepout.access.fetch import FetchedPage

        self.urls.append(url)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return FetchedPage(url=url, text=outcome)


def status_error(code, **headers):
    import httpx

    request = httpx.Request("GET", "https://example.com/p")
    return httpx.HTTPStatusError(f"{code}", request=request, response=httpx.Response(code, headers=headers, request=request))


async def fetch_with(monkeypatch, *outcomes):
    from stepout.capabilities import fetch as fetch_module
    from stepout.capabilities.base import RunContext
    from stepout.domain import FetchAction

    waits, events = [], []

    async def no_sleep(seconds):
        waits.append(seconds)

    async def emit(kind, summary, **data):
        events.append((kind, data))

    monkeypatch.setattr(fetch_module.asyncio, "sleep", no_sleep)
    fetcher = FlakyFetcher(*outcomes)
    ctx = RunContext(run_id="r", role="web_research", hands={"fetch": fetcher}, cancelled=lambda: False, emit=emit)
    text = await fetch_module.Fetch().run(FetchAction(url="https://example.com/p"), ctx)
    return text, fetcher, waits, events


async def test_a_busy_site_is_fetched_again_once(monkeypatch):
    text, fetcher, waits, events = await fetch_with(monkeypatch, status_error(503), "the page")
    assert text.startswith("Fetched") and "the page" in text
    assert len(fetcher.urls) == 2 and len(waits) == 1 and [k for k, _ in events] == ["retry"]


async def test_a_dropped_connection_is_fetched_again(monkeypatch):
    import httpx

    text, fetcher, _, _ = await fetch_with(monkeypatch, httpx.ConnectError("reset"), "the page")
    assert text.startswith("Fetched") and len(fetcher.urls) == 2


async def test_a_missing_page_a_blocked_address_and_a_long_wait_are_not_retried(monkeypatch):
    from stepout.access.fetch import BlockedUrl

    for outcome in (status_error(404), BlockedUrl("private/local address blocked: 10.0.0.1"), status_error(429, **{"retry-after": "120"})):
        text, fetcher, waits, events = await fetch_with(monkeypatch, outcome, "never reached")
        assert text.startswith("Fetching https://example.com/p failed") and len(fetcher.urls) == 1 and not waits and not events


async def test_a_site_that_keeps_failing_is_tried_twice_and_then_reported(monkeypatch):
    text, fetcher, _, _ = await fetch_with(monkeypatch, status_error(503), status_error(503), "never reached")
    assert text.startswith("Fetching https://example.com/p failed") and len(fetcher.urls) == 2
