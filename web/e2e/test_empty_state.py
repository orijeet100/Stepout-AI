"""The empty chat in a real browser: a greeting with the composer under it, four things to try, and a click that sends exactly that text."""

from __future__ import annotations

from playwright.sync_api import expect


def test_a_new_chat_greets_and_offers_four_questions_and_a_click_sends_that_one(page):
    page.get_by_label("New chat", exact=True).click()
    expect(page.get_by_text("What can I help with?")).to_be_visible()
    group = page.get_by_role("group", name="Suggested questions")
    cards = group.get_by_role("button")
    expect(cards).to_have_count(4)

    # at this width the greeting, the composer and the pills sit together in the middle: greeting, then composer, then pills
    # (layout positions: the pills are still rising in, which moves the painted ones)
    composer = page.locator(".composer").bounding_box()
    title = page.locator(".greeting__title").bounding_box()
    assert title["y"] + title["height"] <= composer["y"], "the greeting overlaps the composer"
    assert composer["y"] + composer["height"] < page.viewport_size["height"] * 0.75, composer  # not docked at the bottom
    assert cards.nth(0).evaluate("el => el.offsetTop") >= page.locator(".composer").evaluate("el => el.offsetTop + el.offsetHeight"), "pills not under the composer"

    text = cards.nth(0).inner_text()
    cards.nth(0).click()
    expect(page.locator(".user").last).to_have_text(text)  # sent exactly as shown
    expect(group).to_have_count(0)  # an open conversation does not offer them
    expect(page.get_by_text("What can I help with?")).to_have_count(0)
    expect(page.locator(".turn")).to_have_count(1, timeout=15000)  # the assistant has started: one row
