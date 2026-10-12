"""Renaming and deleting a chat in a real browser, against the real backend: rename in the row itself, delete behind a modal that
asks first (no browser prompt or confirm box), and both reach the API."""

from __future__ import annotations

import re

from playwright.sync_api import expect

FINISHED = re.compile(r"^\d+ actions? · \$[\d.]+ · \d+ s$")


def a_finished_chat(page, text: str):
    page.get_by_label("New chat", exact=True).click()
    page.get_by_label("Message").fill(text)
    page.get_by_label("Message").press("Enter")
    expect(page.locator(".run__sum").last).to_have_text(FINISHED, timeout=45000)  # idle again: only then are rename and delete offered
    row = page.locator(".chatrow", has=page.locator(".chat[aria-current='true']"))
    expect(row).to_have_count(1)
    return row


def test_a_chat_is_renamed_in_its_row_and_deleted_after_a_modal_asks(real_page):
    page = real_page
    page.on("dialog", lambda d: (_ for _ in ()).throw(AssertionError(f"a browser {d.type} box opened: {d.message}")))  # none may appear
    row = a_finished_chat(page, "What are the top events this weekend?")

    row.hover()
    row.get_by_role("button", name="Rename chat").click()
    box = page.get_by_role("textbox", name="Chat title")
    expect(box).to_be_focused()
    box.fill("Weekend plans")
    box.press("Enter")
    expect(page.locator(".chat[aria-current='true']")).to_have_text("Weekend plans")
    expect(page.locator("h1")).to_have_text("Weekend plans")
    page.reload()  # the backend kept it
    expect(page.get_by_role("button", name="Weekend plans")).to_be_visible()

    row = page.locator(".chatrow", has_text="Weekend plans")
    row.hover()
    row.get_by_role("button", name="Delete chat").click()
    dialog = page.get_by_role("dialog", name="Delete chat?")
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text("Weekend plans")
    expect(dialog.get_by_role("button", name="Cancel")).to_be_focused()  # the safe answer is where focus starts
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()
    expect(page.get_by_role("button", name="Weekend plans")).to_be_visible()  # Esc kept it

    row.hover()
    row.get_by_role("button", name="Delete chat").click()
    dialog.get_by_role("button", name="Delete", exact=True).click()
    expect(dialog).to_be_hidden()
    expect(page.get_by_role("button", name="Weekend plans")).to_have_count(0)
    page.reload()
    page.wait_for_load_state("networkidle")  # the chat list has been read again
    expect(page.get_by_role("button", name="Weekend plans")).to_have_count(0)  # gone from the backend too
