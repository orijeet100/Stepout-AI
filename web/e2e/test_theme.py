"""Light and dark in a real browser: the header's button flips the whole page, and the choice survives a reload."""

from __future__ import annotations

from playwright.sync_api import expect

BG = "getComputedStyle(document.querySelector('.main')).backgroundColor"


def test_the_theme_button_flips_the_page_and_the_choice_is_kept(page):
    start = page.evaluate(BG)
    to_dark = start == "rgb(255, 255, 255)"  # the browser starts in light; flip to dark (or back, if it started dark)
    page.get_by_role("button", name="Dark mode" if to_dark else "Light mode").click()
    flipped = page.evaluate(BG)
    assert flipped == ("rgb(33, 33, 33)" if to_dark else "rgb(255, 255, 255)"), flipped  # ChatGPT's #212121, or white

    page.reload()
    expect(page.get_by_role("button", name="Light mode" if to_dark else "Dark mode")).to_be_visible()
    assert page.evaluate(BG) == flipped  # kept, and applied before the page drew
    page.evaluate("localStorage.removeItem('stepout.theme')")  # leave the next flow on the system's theme
