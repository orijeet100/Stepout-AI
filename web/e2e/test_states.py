"""What the page says when the backend cannot be read, and what it says while it waits, in a real browser."""

from __future__ import annotations

import re

from playwright.sync_api import expect


def test_a_failed_chat_list_says_so_in_words_and_retry_recovers(page):
    page.route("**/api/conversations", lambda route: route.fulfill(status=500, body="no"))
    page.reload()
    expect(page.get_by_text("Your chats could not be loaded.")).to_be_visible()  # the sidebar, not an empty column
    expect(page.get_by_text("Nothing to show yet.")).to_be_visible()  # the thread, not a blank area
    expect(page.locator(".banner")).to_contain_text("Could not load your chats")
    page.unroute("**/api/conversations")
    page.get_by_role("button", name="Retry now").click()
    expect(page.locator(".chat").first).to_be_visible()  # the list is back
    expect(page.locator(".banner")).to_have_count(0)
    assert all(r.startswith("500 GET") for r in page.bad_responses), page.bad_responses  # only the 500s this flow provoked
    page.bad_responses.clear()
    page.console_errors[:] = [e for e in page.console_errors if "Failed to load resource" not in e]


def test_a_chat_that_fails_to_open_says_so_and_retry_reads_it_again(page):
    page.route(re.compile(r".*/api/conversations/[0-9a-f]{32}$"), lambda route: route.fulfill(status=500, body="no"))
    page.reload()
    expect(page.get_by_text("Nothing to show yet.")).to_be_visible()
    expect(page.locator(".banner")).to_contain_text("Could not load this chat")
    expect(page.locator(".chat").first).to_be_visible()  # the list itself is fine
    page.unroute(re.compile(r".*/api/conversations/[0-9a-f]{32}$"))
    page.get_by_role("button", name="Retry now").click()
    expect(page.locator(".user").first).to_be_visible()  # the open chat itself was read again
    expect(page.locator(".banner")).to_have_count(0)
    assert all(r.startswith("500 GET") for r in page.bad_responses), page.bad_responses
    page.bad_responses.clear()
    page.console_errors[:] = [e for e in page.console_errors if "Failed to load resource" not in e]
