"""The run view in a real browser, against the mock: it updates live, and its final numbers are the Run's own."""

from __future__ import annotations

import re
from datetime import datetime

from playwright.sync_api import expect

# Playwright turns a Python regex into a JavaScript one, so the one it waits for has no named groups; the one we parse with does.
FINISHED = re.compile(r"^(?:Stopped by you · |Over budget · |Failed · )?\d+ actions? · \$[\d.]+ · \d+ s$")
PARSE = re.compile(r"^(?P<label>(?:Stopped by you|Over budget|Failed) · )?(?P<steps>\d+) actions? · \$(?P<cost>[\d.]+) · (?P<secs>\d+) s$")


def send(page, text: str) -> None:
    page.get_by_label("Message").fill(text)
    page.get_by_label("Message").press("Enter")


def seconds(a: str, b: str) -> int:
    return int((datetime.fromisoformat(b.replace("Z", "+00:00")) - datetime.fromisoformat(a.replace("Z", "+00:00"))).total_seconds())


def test_a_run_updates_live_and_ends_with_the_numbers_of_its_events(page, stack, tmp_path):
    send(page, "What are the top events this weekend?")
    run = page.locator(".run").last
    summary = run.locator(".run__sum")

    # while it works: open, "Working…", a Stop button, the plan ticking along, spend against the cap
    expect(summary).to_have_text(re.compile(r"^Working…"))
    assert run.evaluate("el => el.open") is True  # open while it runs
    expect(page.get_by_role("button", name="Stop", exact=True)).to_be_visible()
    expect(run.get_by_role("progressbar", name="Budget")).to_have_attribute("aria-valuemax", "1")
    expect(run.get_by_role("img", name="done").first).to_be_visible(timeout=15000)  # a plan step finishes while we watch
    seen_working = summary.inner_text()
    assert re.search(r"\d+ of \d+ steps · \d+ s$", seen_working) or seen_working.startswith("Working…"), seen_working
    page.screenshot(path=str(tmp_path / "running.png"))

    # when it ends: collapsed, Stop gone, `N actions · $cost · S s`
    expect(summary).to_have_text(FINISHED, timeout=30000)
    expect(page.get_by_role("button", name="Stop", exact=True)).to_have_count(0)
    assert run.evaluate("el => el.open") is False
    m = PARSE.match(summary.inner_text())
    assert m and m["label"] is None

    # ... and those numbers are the Run's own events (read back from the API the page uses)
    chats = page.request.get(f"{stack[0]}/api/conversations").json()
    detail = page.request.get(f"{stack[0]}/api/conversations/{chats[0]['id']}").json()
    events = page.request.get(f"{stack[0]}/api/runs/{detail['runs'][-1]['run_id']}/events").json()
    assert int(m["steps"]) == sum(e["kind"] == "step" and e["data"].get("action", {}).get("kind") not in ("plan", "delegate", "answer") for e in events)  # the tool calls, not the planning and answering
    assert float(m["cost"]) == round(sum(e["cost_usd"] for e in events), 2)
    assert int(m["secs"]) == seconds(events[0]["at"], events[-1]["at"])
    page.screenshot(path=str(tmp_path / "finished.png"))

    # expanding shows the plan and a card per task; a task opens onto its tool calls, and a call onto its request
    run.locator("summary").click()
    expect(run.get_by_role("list", name="Plan")).to_be_visible()
    tasks = run.get_by_role("region", name="Tasks")
    expect(tasks.locator(".task")).to_have_count(2)
    tasks.get_by_role("button", name=re.compile("Open the Luma discover page")).click()
    call = tasks.get_by_role("button", name=re.compile("Opened a page"))
    expect(call).to_contain_text("luma.com/discover")
    call.click()
    expect(tasks.get_by_text('"url": "https://luma.com/discover"', exact=False)).to_be_visible()
    page.screenshot(path=str(tmp_path / "opened.png"))


def test_stop_ends_a_run_and_says_so(page):
    send(page, "Summarise the engineering blog")
    run = page.locator(".run").last
    expect(run.locator(".run__sum")).to_have_text(re.compile(r"^Working…"))
    page.get_by_role("button", name="Stop", exact=True).click()
    expect(run.locator(".run__sum")).to_have_text(re.compile(r"^Stopped by you · \d+ actions? · \$[\d.]+ · \d+ s$"), timeout=15000)
    expect(page.get_by_role("button", name="Stop", exact=True)).to_have_count(0)
    expect(page.locator(".reply").last).to_contain_text("Stopped by you.")


def test_a_request_the_gate_declines_has_no_run(page):
    page.wait_for_load_state("networkidle")  # the open chat's history has arrived: runs of earlier tests are in `before`, not mistaken for a new one
    before = page.locator(".run").count()
    send(page, "Pay my electricity invoice")
    expect(page.locator(".reply").last).to_contain_text("payments and transfers")
    page.wait_for_load_state("networkidle")
    assert page.locator(".run").count() == before  # a decline starts no Run


def test_a_message_sent_while_a_run_is_busy_is_tagged_queued(page):
    send(page, "Show me the weekend events again")
    expect(page.locator(".run__sum").last).to_have_text(re.compile(r"^Working…"))
    page.get_by_role("button", name="New chat").click()
    send(page, "What is 2 + 3?")
    expect(page.locator(".tag", has_text="Queued")).to_be_visible()  # waiting behind the first Run
    expect(page.locator(".pill", has_text="Queued")).to_be_visible()
    expect(page.locator(".user").last).to_have_text("What is 2 + 3?Queued")
    expect(page.locator(".tag", has_text="Queued")).to_have_count(0, timeout=40000)  # its turn came
    expect(page.locator(".reply").last).to_contain_text("5")
