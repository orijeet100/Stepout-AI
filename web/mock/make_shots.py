"""Writes web/fixtures/shots/<run>/<n>.jpg: one invented page photographed per `shot` event in web/fixtures/*.json.

Same camera as the real thing: installed Chrome, 1000x700, JPEG quality 50. The pages are made up here (a header
with the host, a title, a few cards), so no real site is ever fetched or copied. Regenerate with:
    python web/mock/make_fixtures.py && python web/mock/make_shots.py
"""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
CARDS = ["Rooftop Jazz Night", "AI Builders Meetup", "Sunday Sketch Club", "Harbour Run Club", "Pottery for Beginners", "Open Mic Friday",
         "Bike Repair Workshop", "Board Game Cafe", "Sunrise Yoga", "Photo Walk", "Book Swap", "Taco Tuesday Tasting"]


def page(url: str, title: str) -> str:
    seed = int(hashlib.md5(title.encode()).hexdigest(), 16)
    hue = seed % 360
    cards = "".join(
        f'<div class="c"><div class="i" style="background:hsl({(hue + 40 * k) % 360} 55% 82%)"></div><b>{html.escape(CARDS[(seed >> k) % len(CARDS)])}</b><small>Sat · {6 + k % 4}:30 pm</small></div>'
        for k in range(6)
    )
    return f"""<style>
body{{margin:0;font:16px/1.5 'Segoe UI',system-ui,sans-serif;color:#1f2430;background:#fff}}
header{{display:flex;justify-content:space-between;padding:18px 40px;border-bottom:1px solid #e6e8ee;color:#566070}}
h1{{margin:28px 40px 6px;font-size:32px}} p{{margin:0 40px 22px;color:#566070}}
.g{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;padding:0 40px}}
.c{{border:1px solid #e6e8ee;border-radius:12px;padding:14px;display:grid;gap:4px}} .i{{height:110px;border-radius:8px;margin-bottom:6px}} small{{color:#566070}}
</style><header><b>{html.escape(urlparse(url).netloc)}</b><span>Sign in</span></header>
<h1>{html.escape(title.split(" · ")[0])}</h1><p>{html.escape(url)}</p><div class="g">{cards}</div>"""


def main() -> None:
    shots = [(e["data"]["shot"], e["data"]["url"], e["data"]["title"]) for f in sorted(FIXTURES.glob("*.json"))
             for e in json.loads(f.read_text(encoding="utf-8")) if e.get("type") == "trace" and e["kind"] == "shot"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": 1000, "height": 700})
        tab = ctx.new_page()
        for rel, url, title in shots:
            path = FIXTURES / "shots" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            tab.set_content(page(url, title))
            path.write_bytes(tab.screenshot(type="jpeg", quality=50))
            print(rel, path.stat().st_size, "bytes")
        browser.close()


if __name__ == "__main__":
    main()
