"""A chat read back from the API after a restart looks exactly like the chat watched live: a finished run, one still going, and
the same against the real backend's own answers (not only the mock's). A reload is the restart: it loses everything the page
held and rebuilds it from /api/conversations, /api/conversations/{id} and /api/runs/{id}/events."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

FINISHED = re.compile(r"^\d+ steps? · \$[\d.]+ · \d+ s$")
QUESTION = "What are the top events this weekend?"


def ask_in_a_new_chat(page) -> None:
    page.get_by_label("New chat", exact=True).click()
    page.get_by_label("Message").fill(QUESTION)
    page.get_by_label("Message").press("Enter")


def look_of(page) -> dict:
    """What a reader sees of the last run and of the answer under it, with the run opened (a reader would open it)."""
    block = page.locator(".runblock").last
    if not block.locator("details").evaluate("el => el.open"):
        block.locator("summary").click()
    expect(block.locator(".steps li").first).to_be_visible()
    return {
        "block": block.evaluate("el => el.outerHTML"),
        "reply": page.locator(".reply").last.evaluate("el => el.outerHTML"),
        "title": page.locator("h1").inner_text(),
    }


def reopen(page, url: str) -> None:
    page.reload()
    page.wait_for_selector(".banner", state="detached")
    page.locator(".chat", has_text=QUESTION).first.click()
    expect(page.locator(".runblock").last).to_be_visible()


@pytest.mark.parametrize("backend", ["mock", "real"])
def test_a_finished_run_looks_the_same_after_a_reload(request, backend):
    page = request.getfixturevalue("page" if backend == "mock" else "real_page")
    ask_in_a_new_chat(page)
    expect(page.locator(".runblock").last.locator(".run__sum")).to_have_text(FINISHED, timeout=45000)
    expect(page.locator(".reply").last).to_be_visible()
    page.wait_for_timeout(600)  # the page refreshes the chat from the API when a run ends; let that settle
    live = look_of(page)
    assert "thumb" in live["block"], "the finished run's saved pages should be there"

    reopen(page, page.url)
    after = look_of(page)
    assert after["title"] == live["title"]
    assert after["block"] == live["block"], "the run reads differently after a restart"
    assert after["reply"] == live["reply"], "the answer reads differently after a restart"


@pytest.mark.parametrize("backend", ["mock", "real"])
def test_a_run_still_going_comes_back_live_after_a_reload(request, backend):
    page = request.getfixturevalue("page" if backend == "mock" else "real_page")
    ask_in_a_new_chat(page)
    block = page.locator(".runblock").last
    expect(block.locator(".steps li").nth(1)).to_be_visible(timeout=30000)  # under way

    page.reload()
    page.wait_for_selector(".banner", state="detached")
    page.locator(".chat", has_text=QUESTION).first.click()
    block = page.locator(".runblock").last
    expect(block.locator(".run__sum")).to_have_text(re.compile(r"^Working…"))  # as it was: working, open, with Stop
    assert block.locator("details").evaluate("el => el.open") is True
    expect(page.get_by_role("button", name="Stop", exact=True)).to_be_visible()
    steps_then = block.locator(".steps li").count()
    expect(block.locator(".steps li")).not_to_have_count(steps_then, timeout=30000)  # and it keeps filling in from the wire
    expect(block.locator(".run__sum")).to_have_text(FINISHED, timeout=45000)  # and ends like any other
    expect(page.locator(".reply").last).to_be_visible()
