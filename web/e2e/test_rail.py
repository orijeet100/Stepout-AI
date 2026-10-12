"""The desktop sidebar folds to a rail of icons and back, and the choice survives a reload."""

from __future__ import annotations

from playwright.sync_api import expect


def width(page) -> float:
    return page.locator("aside.side").bounding_box()["width"]


def test_the_sidebar_folds_to_a_rail_and_back_and_remembers(page):
    side = page.locator("aside.side")
    assert width(page) == 260
    page.get_by_label("Collapse sidebar").click()
    page.wait_for_timeout(450)  # the column eases over 300 ms
    assert width(page) == 48
    expect(page.get_by_label("Expand sidebar")).to_be_visible()
    expect(page.locator(".chat").first).to_be_hidden()  # the history is not in the rail, and not in the tab order
    expect(page.get_by_label("New chat", exact=True)).to_be_visible()  # but a new chat is one click away

    page.reload()
    page.wait_for_selector(".banner", state="detached")
    page.wait_for_timeout(450)
    assert width(page) == 48  # remembered by this browser

    page.get_by_label("New chat", exact=True).click()  # works from the rail
    expect(page.locator("h1")).to_have_text("New chat")
    page.get_by_label("Expand sidebar").click()
    page.wait_for_timeout(450)
    assert width(page) == 260
    expect(side.locator(".chat").first).to_be_visible()
