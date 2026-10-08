"""The chat-list drawer under 900 px, in a real browser: reachable, keyboard-safe, and nothing spills off a phone screen."""

from __future__ import annotations

import re

from playwright.sync_api import expect

FINISHED = re.compile(r"^\d+ steps? · \$[\d.]+ · \d+ s$")
ACTIVE = "(() => { const a = document.activeElement; return { label: a.getAttribute('aria-label') || a.textContent.trim().slice(0, 30), inSide: !!a.closest('aside.side'), inMain: !!a.closest('main'), tag: a.tagName } })()"


def phone(page, width: int = 390) -> None:
    page.set_viewport_size({"width": width, "height": 800})


def test_at_phone_width_the_chat_list_is_a_drawer_you_can_open_choose_from_and_start_a_chat_in(page):
    phone(page)
    expect(page.locator("aside.side")).to_be_hidden()  # no longer taking the screen
    menu = page.locator("button.menu")
    expect(menu).to_be_visible()  # the way in

    menu.click()
    expect(page.locator("aside.side")).to_be_visible()
    expect(menu).to_have_attribute("aria-expanded", "true")
    page.locator(".chat", has_text="Pay my electricity invoice").click()  # choosing a chat closes the drawer
    expect(page.locator("aside.side")).to_be_hidden()
    expect(page.locator("h1")).to_contain_text("Pay my electricity invoice")

    menu.click()
    page.locator(".scrim").click(position={"x": 370, "y": 400})  # the scrim, outside the drawer
    expect(page.locator("aside.side")).to_be_hidden()

    menu.click()
    page.get_by_label("New chat", exact=True).click()  # starting a chat from the drawer: it closes, and the chat works
    expect(page.locator("aside.side")).to_be_hidden()
    expect(page.locator("h1")).to_have_text("New chat")
    page.get_by_label("Message").fill("What is 2 + 3?")
    page.get_by_label("Message").press("Enter")
    expect(page.locator(".reply").last).to_contain_text("5", timeout=30000)


def test_the_boundary_is_899_and_900(page):
    phone(page, 900)
    expect(page.locator("aside.side")).to_be_visible()
    expect(page.locator("button.menu")).to_be_hidden()  # at 900 the list is simply there
    phone(page, 899)
    expect(page.locator("aside.side")).to_be_hidden()
    expect(page.locator("button.menu")).to_be_visible()


def test_the_drawer_is_keyboard_safe(page):
    phone(page)
    # closed: Tab never lands in it
    for _ in range(12):
        page.keyboard.press("Tab")
        assert not page.evaluate(ACTIVE)["inSide"], "focus reached the closed drawer"
    page.locator("button.menu").focus()
    page.keyboard.press("Enter")  # open it from the keyboard
    expect(page.locator("aside.side")).to_be_visible()
    now = page.evaluate(ACTIVE)
    assert now["inSide"] and now["label"] == "New chat", now  # focus moved into the drawer
    for key in ["Tab"] * 10 + ["Shift+Tab"] * 10:  # open: focus stays in the drawer; the page behind cannot be reached
        page.keyboard.press(key)
        got = page.evaluate(ACTIVE)
        assert got["inSide"] or got["tag"] == "BODY", f"focus reached the page behind the drawer: {got}"
    page.locator("aside.side button").first.focus()
    page.keyboard.press("Escape")  # Esc closes it
    expect(page.locator("aside.side")).to_be_hidden()
    assert page.evaluate(ACTIVE)["label"] == "Chats"  # and focus is back on the menu button


def test_a_skip_link_is_the_first_stop_and_leads_to_the_message_box(page):
    # first in document order, which is tab order (no positive tabindex anywhere): what a keyboard user meets first.
    # (Not tested by a first synthetic Tab: from a fresh page headless Chrome starts in its own UI and wraps to the last control.)
    first = page.evaluate(
        """() => [...document.querySelectorAll('a[href], button:not([disabled]), textarea, input, select, [tabindex]')]
             .find((e) => !e.closest('[inert]'))?.textContent.trim()"""
    )
    assert first == "Skip to the message box", first
    assert page.evaluate("[...document.querySelectorAll('[tabindex]')].every((e) => e.tabIndex <= 0)")
    page.get_by_role("link", name="Skip to the message box").focus()
    expect(page.get_by_role("link", name="Skip to the message box")).to_be_visible()  # it comes on screen when focused
    page.keyboard.press("Enter")
    assert page.evaluate("document.activeElement.id") == "message"  # straight to the message box, past the whole chat list


def test_nothing_spills_off_a_phone_screen_even_with_a_whole_browser_run_on_it(page):
    phone(page)
    page.locator("button.menu").click()
    page.get_by_label("New chat", exact=True).click()
    page.get_by_label("Message").fill("What are the top events this weekend?")
    page.get_by_label("Message").press("Enter")
    run = page.locator(".run").last
    expect(run.locator(".run__sum")).to_have_text(FINISHED, timeout=45000)
    run.locator("summary").click()  # everything open: the browser panel, meters, plan, steps, thumbnails
    page.wait_for_timeout(300)
    wide = page.evaluate(
        """() => {
          const vw = document.documentElement.clientWidth
          const over = [...document.querySelectorAll('.app *')].filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.right > vw + 1 && !e.closest('aside.side') })
          return { scroll: document.documentElement.scrollWidth, vw, over: over.slice(0, 5).map((e) => e.className || e.tagName) }
        }"""
    )
    assert wide["scroll"] <= wide["vw"], wide  # no horizontal scrolling
    assert wide["over"] == [], wide  # and nothing painted past the right edge
