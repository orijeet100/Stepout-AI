"""The live-frame limiter in Browser, without Chrome: what is sent, when, and what can never go wrong.

(tests/test_browser.py runs the same thing against a real headless Chrome.)
"""

import asyncio
import logging
import time

from stepout.browser import FRAME_GAP_S, FRAME_QUALITY, VIEWPORT, Browser, _Session


class FakeScreencast:
    """Playwright's page.screencast: it hands `deliver` to whoever calls start(), and tests push frames through it."""

    def __init__(self, fail_to_start=False):
        self.deliver, self.stopped, self.args, self.fail = None, 0, None, fail_to_start

    async def start(self, on_frame, quality, size):
        if self.fail:
            raise RuntimeError("no screencast here")
        self.deliver, self.args = on_frame, (quality, size)

    async def stop(self):
        self.stopped += 1


class FakeContext:
    closed = False

    async def close(self):
        self.closed = True


def rig(callback=None, fail_to_start=False):
    sent = []  # (monotonic time, run_id, jpeg)
    browser = Browser(on_frame=callback or (lambda run_id, jpeg: sent.append((time.monotonic(), run_id, jpeg))))
    page = type("FakePage", (), {"screencast": FakeScreencast(fail_to_start)})()
    session = _Session(FakeContext(), page)
    browser._sessions["r1"] = session
    return browser, session, page.screencast, sent


async def test_frames_start_before_the_first_page_with_the_viewport_size_and_a_modest_quality():
    browser, session, screencast, _ = rig()
    await browser._start_frames(session, "r1")
    assert screencast.args == (FRAME_QUALITY, VIEWPORT) == (50, {"width": 1000, "height": 700}) and session.framing


async def test_a_burst_sends_the_first_frame_now_and_after_the_gap_only_the_newest():
    browser, session, screencast, sent = rig()
    await browser._start_frames(session, "r1")
    for i in range(10):
        screencast.deliver({"data": bytes([i])})
    assert [j for _, _, j in sent] == [bytes([0])]  # at once
    await asyncio.sleep(FRAME_GAP_S + 0.15)
    assert [j for _, _, j in sent] == [bytes([0]), bytes([9])]  # frames 1 to 8 were stale by then: dropped. The page's last state is not lost.
    assert {run_id for _, run_id, _ in sent} == {"r1"}


async def test_a_steady_stream_never_exceeds_four_a_second_and_ends_on_the_last_frame():
    browser, session, screencast, sent = rig()
    await browser._start_frames(session, "r1")
    fed = 0
    end = time.monotonic() + 1.4
    while time.monotonic() < end:  # about 50 frames a second, twice what Chrome gives on an animated page
        screencast.deliver({"data": fed.to_bytes(2, "big")})
        fed += 1
        await asyncio.sleep(0.02)
    await asyncio.sleep(FRAME_GAP_S + 0.15)
    times = [t for t, _, _ in sent]
    assert len(times) >= 4  # they do flow
    assert all(b - a >= FRAME_GAP_S - 0.01 for a, b in zip(times, times[1:]))  # no two closer than the gap
    assert all(sum(1 for u in times if t <= u < t + 1.0) <= 4 for t in times)  # at most four in any second
    assert sent[-1][2] == (fed - 1).to_bytes(2, "big")  # the newest frame fed is the last one shown


async def test_a_callback_that_raises_is_logged_once_and_never_reaches_playwright(caplog):
    calls = []

    def boom(run_id, jpeg):
        calls.append(jpeg)
        raise RuntimeError("the viewer is gone")

    browser, session, screencast, _ = rig(callback=boom)
    await browser._start_frames(session, "r1")
    with caplog.at_level(logging.WARNING, logger="stepout.browser"):
        for i in range(4):
            screencast.deliver({"data": bytes([i])})  # must not raise: Playwright would surface it in the Run's next page call
            await asyncio.sleep(FRAME_GAP_S + 0.05)
    assert len(calls) >= 3  # it is still called each time it is allowed
    assert len([r for r in caplog.records if "on_frame raised" in r.getMessage()]) == 1


async def test_a_frame_that_is_not_a_frame_is_ignored():
    browser, session, screencast, sent = rig()
    await browser._start_frames(session, "r1")
    screencast.deliver({})  # no "data"
    screencast.deliver({"data": b"ok"})
    assert [j for _, _, j in sent] == [b"ok"]


async def test_closing_the_browser_stops_the_screencast_and_cancels_the_pending_frame():
    browser, session, screencast, sent = rig()
    await browser._start_frames(session, "r1")
    for i in range(5):
        screencast.deliver({"data": bytes([i])})  # frame 0 goes; 4 waits for its turn
    await browser.close("r1")
    await asyncio.sleep(FRAME_GAP_S + 0.15)
    assert [j for _, _, j in sent] == [bytes([0])]  # the waiting frame never went out after the close
    assert screencast.stopped == 1 and session.context.closed and not session.framing and session.timer is None
    screencast.deliver({"data": b"late"})  # a frame still in flight when the page closed
    assert [j for _, _, j in sent] == [bytes([0])]


async def test_if_frames_cannot_start_browsing_goes_on_without_them(caplog):
    browser, session, screencast, sent = rig(fail_to_start=True)
    with caplog.at_level(logging.WARNING, logger="stepout.browser"):
        await browser._start_frames(session, "r1")  # must not raise
    assert not session.framing and "could not start" in caplog.text
    await browser.close("r1")
    assert screencast.stopped == 0 and session.context.closed  # nothing to stop; the context still closes
