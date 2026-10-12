"""The streamed reply in a real browser: the words grow on the page as they are written, in the assistant's own row, and the
finished reply replaces them without the row being rebuilt. (The mock streams the fixture's reply three words at a time, as
the real backend does with `delta` frames.)"""

from __future__ import annotations

import re

from playwright.sync_api import expect

FINISHED = re.compile(r"^\d+ actions? · \$[\d.]+ · \d+ s$")

# records, on every change to the page, how much reply text is showing and how many assistant rows and tiles there are
SAMPLER = """() => {
  window.__samples = []
  const take = () => {
    const replies = [...document.querySelectorAll('.reply')]
    const last = replies.at(-1)
    window.__samples.push({ len: last ? last.textContent.length : 0, replies: replies.length, tiles: document.querySelectorAll('.turn__tile').length, rows: document.querySelectorAll('.turn').length })
  }
  new MutationObserver(take).observe(document.body, { subtree: true, childList: true, characterData: true })
}"""


def test_the_reply_grows_on_the_page_in_one_row_and_the_finished_reply_replaces_it(page):
    page.get_by_label("New chat", exact=True).click()
    page.evaluate(SAMPLER)
    page.get_by_label("Message").fill("What are the top events this weekend?")
    page.get_by_label("Message").press("Enter")
    expect(page.locator(".run__sum").last).to_have_text(FINISHED, timeout=45000)
    expect(page.locator(".reply").last).to_contain_text("Rooftop Jazz Night")

    samples = page.evaluate("window.__samples")
    lengths = [s["len"] for s in samples if s["replies"]]
    grown = sorted({n for n in lengths if n > 0})
    assert len(grown) >= 4, f"the reply appeared whole, not as it was written: {grown}"
    assert lengths == sorted(lengths), "the words only ever grow"
    assert grown[0] < grown[-1] / 2, f"the first words came well before the end: {grown}"
    # the assistant's row and tile are never rebuilt into two, whatever is on screen
    assert max(s["tiles"] for s in samples) == 1 and max(s["rows"] for s in samples) == 1, samples[-3:]
    assert max(s["replies"] for s in samples) == 1  # the words and the finished reply are never both on screen
