"""No failed request, no console error: the page must never ask for something that is not there yet.

The `page` fixture fails every flow on a console error or an HTTP answer of 400 or more that the flow did not provoke on
purpose, so these flows just drive the moments that used to ask for the events of a Run that had no events yet."""

from __future__ import annotations

import re

from playwright.sync_api import expect

FINISHED = re.compile(r"^\d+ steps? · \$[\d.]+ · \d+ s$")


def type_in(page, text: str) -> None:
    page.get_by_label("Message").fill(text)
    page.get_by_label("Message").press("Enter")


def test_a_second_message_in_the_same_chat_starts_its_run_without_a_failed_request(page):
    page.get_by_label("New chat", exact=True).click()
    type_in(page, "What is 2 + 3?")
    type_in(page, "What is 2 + 3 again?")  # waits behind the first; when the first ends the second starts at once
    expect(page.locator(".reply")).to_have_count(2, timeout=40000)
    expect(page.locator(".run__sum")).to_have_count(2)
    expect(page.locator(".run__sum").last).to_have_text(FINISHED)


def test_reloading_the_page_the_moment_a_run_has_started_asks_for_nothing_that_is_not_there(page):
    page.get_by_label("New chat", exact=True).click()
    type_in(page, "What are the top events this weekend?")
    page.wait_for_selector(".chat .dot--running")  # the Run is active: listed by the backend, with no events yet
    page.reload()
    page.wait_for_selector(".chat")
    expect(page.locator(".run__sum").last).to_have_text(FINISHED, timeout=40000)  # it carried on, and the page followed it


def test_switching_chats_while_a_run_is_going_asks_for_nothing_that_is_not_there(page):
    page.get_by_label("New chat", exact=True).click()
    type_in(page, "What are the top events this weekend?")
    page.wait_for_selector(".chat .dot--running")
    for _ in range(3):  # away and back, each time re-reading the chat
        page.locator(".chat").nth(1).click()
        page.locator(".chat", has=page.locator(".dot--running")).first.click()
    expect(page.locator(".run__sum").last).to_have_text(FINISHED, timeout=40000)
