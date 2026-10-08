"""The last lines of a conversation are never hidden under the composer, and the view only follows when the reader is at the end."""

from __future__ import annotations

import re

from playwright.sync_api import expect

FINISHED = re.compile(r"^\d+ steps? · \$[\d.]+ · \d+ s$")
# how far the last thing in the thread reaches below the top of the composer (> 0: it is hidden under it)
HIDDEN = """() => {
  const last = [...document.querySelector('.col').children].at(-1).getBoundingClientRect()
  return Math.round(last.bottom - document.querySelector('.composer').getBoundingClientRect().top)
}"""
SCROLL = "document.querySelector('.scroll').scrollTop"


def ask(page, text: str) -> None:
    """On a phone, in a new chat (so there is no earlier run for a locator to land on), ask something."""
    page.set_viewport_size({"width": 390, "height": 800})
    page.locator("button.menu").click()
    page.get_by_label("New chat", exact=True).click()
    page.get_by_label("Message").fill(text)
    page.get_by_label("Message").press("Enter")


def test_a_taller_composer_does_not_cover_the_last_lines(page):
    ask(page, "What are the top events this weekend?")
    run = page.locator(".run").last
    expect(run.locator(".run__sum")).to_have_text(FINISHED, timeout=45000)
    expect(page.locator(".reply").last).to_be_visible()
    run.locator("summary").click()  # the whole run open
    page.locator(".scroll").evaluate("el => el.scrollTop = el.scrollHeight")  # and the reader at the end of it
    assert page.evaluate(HIDDEN) <= 0

    box = page.get_by_label("Message")
    box.click()
    for _ in range(6):  # a long, multi-line message: the composer grows by ~100 px
        box.press("Shift+Enter")
        box.type("one more line of a long message")
    page.wait_for_timeout(300)
    assert page.evaluate(HIDDEN) <= 0, "the composer grew over the last lines"


def test_a_reader_who_scrolled_up_is_not_pulled_down_by_a_running_run(page):
    ask(page, "What are the top events this weekend?")
    steps = page.locator(".run").last.locator(".steps li")
    expect(steps.nth(1)).to_be_visible(timeout=30000)  # it is under way
    page.wait_for_function("() => { const s = document.querySelector('.scroll'); return s.scrollHeight - s.clientHeight > 150 }")  # and well taller than the screen
    page.locator(".scroll").evaluate("el => el.scrollTop = 0")  # the reader goes back up to the top
    page.wait_for_timeout(200)
    before = steps.count()
    expect(steps).not_to_have_count(before, timeout=30000)  # more of the run arrives while they read
    assert page.evaluate(SCROLL) < 5, "the view was pulled away from where the reader was"


def test_opening_a_finished_run_keeps_its_top_in_view(page):
    ask(page, "What are the top events this weekend?")
    run = page.locator(".run").last
    expect(run.locator(".run__sum")).to_have_text(FINISHED, timeout=45000)
    expect(page.locator(".reply").last).to_be_visible()
    run.locator("summary").click()  # opening it grows the page above the answer, and must not throw the reader down to the answer
    page.wait_for_timeout(300)
    assert page.evaluate(SCROLL) < 5
    expect(run.locator("summary")).to_be_in_viewport()
