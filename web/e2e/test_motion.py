"""prefers-reduced-motion in a real browser: nothing spins, pulses, slides or eases, and nothing scrolls smoothly."""

from __future__ import annotations

import re

from playwright.sync_api import expect

FINISHED = re.compile(r"^\d+ steps? · \$[\d.]+ · \d+ s$")
# the computed motion of every kind of thing that moves, read from the page while a run is going
MOTION = """() => {
  const css = (sel) => { const e = document.querySelector(sel); return e ? getComputedStyle(e) : null }
  const spin = css('.run--running .glyph--running') // a plan step that is running
  const pulse = css('.run--running .dot--running')
  const chev = css('.run__chev')
  const bar = css('.meter__bar > span')
  const side = css('.side')
  return {
    spin: spin && spin.animationName, pulse: pulse && pulse.animationName,
    chev: chev && chev.transitionDuration, bar: bar && bar.transitionDuration, side: side && side.transitionDuration,
    smooth: [document.documentElement, document.body, document.querySelector('.scroll')].map((e) => e && getComputedStyle(e).scrollBehavior),
  }
}"""


def go(page) -> dict:
    page.get_by_label("New chat", exact=True).click()
    page.get_by_label("Message").fill("What are the top events this weekend?")
    page.get_by_label("Message").press("Enter")
    expect(page.locator(".run--running .glyph--running").first).to_be_visible(timeout=30000)  # a step that is working: the spinner
    return page.evaluate(MOTION)


def test_with_reduced_motion_nothing_spins_pulses_or_eases(page_with):
    m = go(page_with(reduced_motion="reduce"))
    assert m["spin"] == "none" and m["pulse"] == "none", m  # still there, standing still: the words "Working…" say it is going
    assert m["chev"] == m["bar"] == m["side"] == "0s", m
    assert all(b in (None, "auto") for b in m["smooth"]), m


def test_without_it_they_do_move(page_with):  # so the test above can tell
    m = go(page_with(reduced_motion="no-preference"))
    assert m["spin"] == "spin" and m["pulse"] == "pulse", m
    assert m["bar"] != "0s", m
