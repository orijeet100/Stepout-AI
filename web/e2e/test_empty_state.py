"""The empty chat in a real browser: a greeting, four things to try, and a click that sends exactly that text."""

from __future__ import annotations

from playwright.sync_api import expect


def test_a_new_chat_greets_and_offers_four_questions_and_a_click_sends_that_one(page):
    page.get_by_label("New chat", exact=True).click()
    expect(page.get_by_text("What can I help with?")).to_be_visible()
    group = page.get_by_role("group", name="Suggested questions")
    cards = group.get_by_role("button")
    expect(cards).to_have_count(4)

    # they sit above the composer, in a 2 by 2 grid at this width
    boxes = [cards.nth(i).bounding_box() for i in range(4)]
    assert boxes[0]["y"] == boxes[1]["y"] and boxes[2]["y"] > boxes[0]["y"], boxes
    assert boxes[3]["y"] + boxes[3]["height"] <= page.locator(".composer").bounding_box()["y"], "suggestions overlap the composer"

    text = cards.nth(0).inner_text()
    cards.nth(0).click()
    expect(page.locator(".user").last).to_have_text(text)  # sent exactly as shown
    expect(group).to_have_count(0)  # an open conversation does not offer them
    expect(page.get_by_text("What can I help with?")).to_have_count(0)
    expect(page.locator(".turn")).to_have_count(1, timeout=15000)  # the assistant has started: one tile
