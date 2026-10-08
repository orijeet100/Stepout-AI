"""The live view in a real browser, against the mock (which feeds the channel's own LiveView): it shows while the Browser
works, really delivers frames, takes no input, and gives way to the last saved page when the Run is over."""

from __future__ import annotations

import re

from playwright.sync_api import expect

LIVE = "img.browser__live"
DECODED = "(sel) => { const i = document.querySelector(sel); return !!i && i.complete && i.naturalWidth > 0 }"


def ask(page, text: str):
    """A fresh chat (the mock keeps earlier runs), the message, and this run's block."""
    page.get_by_label("New chat", exact=True).click()  # the icon button, not a sidebar row that happens to be titled so
    page.get_by_label("Message").fill(text)
    page.get_by_label("Message").press("Enter")
    return page.locator(".run").last


def test_the_live_view_shows_while_the_browser_works_and_gives_way_to_the_last_page(page, tmp_path):
    run = ask(page, "What are the top events this weekend?")

    # while it runs: a live image, marked Live, whose frames the browser has really decoded
    expect(run.locator(LIVE)).to_be_visible(timeout=15000)
    expect(run.locator(".browser__badge.is-live")).to_have_text(re.compile(r"Live"))
    page.wait_for_function(DECODED, arg=LIVE, timeout=15000)
    # it is view-only: nothing in the panel can take input, and the image is not a link or a button
    assert run.locator(".browser button, .browser input, .browser textarea, .browser select").count() == 0
    assert run.locator(f"a {LIVE}, button {LIVE}").count() == 0
    # the caption follows the pages the Browser has saved
    expect(run.locator(".browser__title")).to_have_text("Discover events · Luma", timeout=20000)
    expect(run.locator("a.page__url")).to_have_text("https://luma.com/discover")
    page.screenshot(path=str(tmp_path / "live.png"))

    # when the Run is over: no stream any more, the last saved page instead (and not a broken image)
    expect(run.locator(LIVE)).to_have_count(0, timeout=40000)
    run.locator("summary").click()  # a finished run is collapsed; open it
    expect(run.locator(".browser__badge", has_text="Last page")).to_be_visible()
    expect(run.locator(".browser__title")).to_have_text("New York · Luma")
    page.wait_for_function(DECODED, arg=".run:last-of-type .browser img", timeout=10000)
    assert run.locator(".browser img").evaluate("img => img.getAttribute('src')").startswith("/shots/")
    page.screenshot(path=str(tmp_path / "last-page.png"))


def test_if_the_stream_is_not_there_the_page_shows_the_last_screenshot_not_a_broken_image(page):
    page.route("**/live/*", lambda route: route.fulfill(status=404))  # the contracted way a stream can be gone
    run = ask(page, "What are the top events this weekend?")
    expect(run.locator(".browser__badge", has_text="Last page")).to_be_visible(timeout=20000)  # as soon as a page has been saved
    expect(run.locator(LIVE)).to_have_count(0)
    page.wait_for_function(DECODED, arg=".run:last-of-type .browser img", timeout=10000)
    # Chrome reports the 404 itself as a console error; the page handled it, so that one is expected here
    page.console_errors[:] = [e for e in page.console_errors if "404" not in e]


def test_a_run_with_no_browser_step_has_no_live_view(page):
    run = ask(page, "What is 2 + 3?")
    expect(run.locator(".run__sum")).to_have_text(re.compile(r"^1 step"), timeout=20000)  # it ran and finished
    assert run.locator(".browser").count() == 0
    assert page.locator(LIVE).count() == 0
