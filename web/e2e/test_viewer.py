"""The screenshot viewer in a real browser, against the mock: reached and used with the keyboard alone, with the real
<dialog> doing the focus trap, Esc and focus restore."""

from __future__ import annotations

import re

from playwright.sync_api import expect

FINISHED = re.compile(r"^\d+ steps? · \$[\d.]+ · \d+ s$")
ACTIVE = "(() => { const a = document.activeElement; return { cls: a.className, label: a.getAttribute('aria-label'), inDialog: !!a.closest('dialog[open]'), tag: a.tagName } })()"


def finished_run(page):
    """A fresh chat, a Browser run, waited out; returns its block with the run expanded by the keyboard."""
    page.get_by_label("New chat", exact=True).click()
    page.get_by_label("Message").fill("What are the top events this weekend?")
    page.get_by_label("Message").press("Enter")
    run = page.locator(".run").last
    expect(run.locator(".run__sum")).to_have_text(FINISHED, timeout=40000)
    run.locator("summary").focus()
    page.keyboard.press("Enter")  # a <details> opens from the keyboard
    assert run.evaluate("el => el.open") is True
    return run


def tab_to_a_thumbnail(page) -> str:
    for _ in range(40):
        page.keyboard.press("Tab")
        now = page.evaluate(ACTIVE)
        if "thumb" in now["cls"].split():
            return now["label"]
    raise AssertionError("no thumbnail could be reached with Tab")


def test_the_viewer_works_with_the_keyboard_alone(page, tmp_path):
    finished_run(page)
    opener = tab_to_a_thumbnail(page)  # the thumbnails are in the tab order
    assert opener.startswith("Open screenshot 1 of 2")

    page.keyboard.press("Enter")  # open the viewer from the thumbnail
    dialog = page.locator("dialog[open]")
    expect(dialog).to_be_visible()
    assert page.evaluate(ACTIVE)["label"] == "Close viewer"  # focus went into it, onto Close
    expect(dialog.get_by_role("heading")).to_have_text("Discover events · Luma")
    expect(dialog.get_by_text("1 of 2")).to_be_visible()
    page.wait_for_function("() => { const i = document.querySelector('dialog[open] img.viewer__img'); return !!i && i.complete && i.naturalWidth > 0 }", timeout=10000)  # the large image decoded
    assert dialog.locator("img.viewer__img").get_attribute("alt") == "Screenshot of Discover events · Luma"  # alt text
    page.screenshot(path=str(tmp_path / "viewer.png"))

    page.keyboard.press("ArrowRight")  # the next page
    expect(dialog.get_by_role("heading")).to_have_text("New York · Luma")
    expect(dialog.get_by_text("2 of 2")).to_be_visible()
    page.keyboard.press("ArrowRight")  # wraps round to the first
    expect(dialog.get_by_text("1 of 2")).to_be_visible()
    page.keyboard.press("ArrowLeft")
    expect(dialog.get_by_text("2 of 2")).to_be_visible()

    # focus is trapped: Tab and Shift+Tab cycle inside the dialog and never land on the page behind it (a modal makes that
    # inert; focus may step out to the browser's own chrome, where the active element is just <body>)
    seen = set()
    for key in ["Tab"] * 8 + ["Shift+Tab"] * 8:
        page.keyboard.press(key)
        now = page.evaluate(ACTIVE)
        assert now["inDialog"] or now["tag"] == "BODY", f"focus reached page content on {key}: {now}"
        seen.add(now["label"] or now["tag"])
    assert {"Close viewer", "Previous", "Next"} & seen or len(seen) > 1, seen  # it really moved around the dialog
    page.evaluate("document.querySelector('.composer textarea').focus()")  # the composer behind the dialog cannot be focused at all
    assert page.evaluate(ACTIVE)["tag"] != "TEXTAREA"
    dialog.get_by_role("button", name="Close viewer").focus()  # back inside, as a keyboard user would be after cycling round

    page.keyboard.press("Escape")
    expect(page.locator("dialog[open]")).to_have_count(0)
    after = page.evaluate(ACTIVE)
    assert after["label"] == opener, after  # focus is back on the thumbnail that opened it


def test_a_missing_screenshot_is_a_placeholder_never_a_broken_image(page):
    page.route("**/shots/**", lambda route: route.abort())  # every saved page fails to load
    run = finished_run(page)
    expect(run.get_by_role("img", name="Screenshot unavailable").first).to_be_visible()
    thumbs = run.locator(".thumb")
    assert thumbs.count() == 2
    assert run.locator("img.thumb__img").count() == 0  # no <img> left that could show as broken
    thumbs.first.focus()
    page.keyboard.press("Enter")
    expect(page.locator("dialog[open]").get_by_role("img", name="Screenshot unavailable")).to_be_visible()  # the viewer says so too
    page.keyboard.press("Escape")
    expect(page.locator("dialog[open]")).to_have_count(0)
    # Chrome reports the aborted image requests itself as console errors; the page handled them
    page.console_errors[:] = [e for e in page.console_errors if "Failed to load resource" not in e]
