"""Writes web/fixtures/*.json: invented runs in the v1 contract's shape (docs/ui-contract.md).

Each file is one chat as a JSON list of server frames (message, trace, status), in the order the server would have
sent them, with realistic gaps between events. Ids are deterministic 32-hex strings. Optional fields are null, times
are ISO UTC ending in Z. Wording copies the real backend (runner.py, gate.py). Everything is invented: no real
paths, pages, or runs. Regenerate with:  python web/mock/make_fixtures.py
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "fixtures"
CAP = 1.0


def hid(*parts: str) -> str:
    return hashlib.md5("|".join(parts).encode()).hexdigest()  # 32 hex, stable


def iso(t: datetime) -> str:
    return t.isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Chat:
    def __init__(self, name: str, start: str) -> None:
        self.name, self.t = name, datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
        self.conv, self.run = hid(name, "conv"), hid(name, "run")
        self.frames: list[dict] = []
        self.spent = 0.0
        self._n = 0
        self.shots = 0

    def _eid(self) -> str:
        self._n += 1
        return hid(self.name, f"e{self._n}")

    def wait(self, seconds: float) -> None:
        self.t += timedelta(seconds=seconds)

    def user(self, text: str) -> None:
        self.frames.append(self._message("user", text, None, None))

    def reply(self, text: str, wait: float, with_run: bool = True) -> None:
        self.wait(wait)
        self.frames.append(self._message("assistant", text, self.run if with_run else None, round(self.spent, 4) if with_run else None))
        if with_run:
            self._status(False)

    def _message(self, role: str, text: str, run_id: str | None, cost: float | None) -> dict:
        return {"type": "message", "id": self._eid(), "conversation_id": self.conv, "role": role, "text": text, "run_id": run_id, "cost_usd": cost, "at": iso(self.t)}

    def _status(self, running: bool) -> None:
        active = {"conversation_id": self.conv, "run_id": self.run, "cap_usd": CAP} if running else None
        self.frames.append({"type": "status", "state": "running" if running else "idle", "active": active, "queued": [], "at": iso(self.t)})

    def start(self, wait: float = 0.3) -> None:
        self.wait(wait)
        self._status(True)

    def event(self, kind: str, role: str, wait: float, parent: str | None = None, cost: float = 0.0, **data) -> str:
        self.wait(wait)
        self.spent += cost
        eid = self._eid()
        self.frames.append(
            {"type": "trace", "id": eid, "conversation_id": self.conv, "run_id": self.run, "parent": parent, "kind": kind, "role": role, "data": data, "cost_usd": cost, "at": iso(self.t)}
        )
        return eid

    # --- the Runner's events, with its wording -------------------------------------------------------------

    def plan_step(self, wait: float, cost: float, steps: list[tuple[str, str]]) -> str:
        summary = "plan: " + "; ".join(f"{r}: {g[:70]}" for r, g in steps)
        action = {"kind": "plan", "steps": [{"role": r, "goal": g, "status": "pending"} for r, g in steps]}
        return self.event("step", "orchestrator", wait, cost=cost, summary=summary, action=action, verdict="allow")

    def plan(self, steps: list[tuple[str, str, str]], wait: float = 0.05) -> None:
        self.event("plan", "orchestrator", wait, summary="plan updated", steps=[{"role": r, "goal": g, "status": s} for r, g, s in steps])

    def delegate(self, wait: float, cost: float, i: int, role: str, goal: str) -> str:
        return self.event("step", "orchestrator", wait, cost=cost, summary=f"delegate {i} → {role}: {goal}", action={"kind": "delegate", "step": i}, verdict="allow")

    def act(self, role: str, wait: float, parent: str, cost: float, summary: str, action: dict, verdict: str = "allow") -> str:
        return self.event("step", role, wait, parent=parent, cost=cost, summary=summary, action=action, verdict=verdict)

    def answer(self, role: str, wait: float, parent: str | None, cost: float, text: str) -> str:
        return self.event("step", role, wait, parent=parent, cost=cost, summary="answer", action={"kind": "answer", "text": text}, verdict="allow")

    def ret(self, role: str, parent: str, ok: bool, text: str, wait: float = 0.05) -> None:
        self.event("return", role, wait, parent=parent, summary=f"{'done' if ok else 'failed'}: {text[:200]}", ok=ok)

    def shot(self, role: str, wait: float, parent: str, url: str, title: str) -> None:
        self.shots += 1
        self.event("shot", role, wait, parent=parent, summary="page screenshot", shot=f"{self.run}/{self.shots}.jpg", url=url, title=title)

    def stop(self, role: str, wait: float, text: str, parent: str | None = None) -> None:
        self.event("stop", role, wait, parent=parent, summary=text)


def browse(op: str, url: str | None = None, link: int | None = None) -> dict:
    return {"kind": "browse", "op": op, "url": url, "link": link}


def web_run() -> Chat:
    c = Chat("web-run", "2026-10-01T09:14:00")
    c.user("What are the top three events on Luma this weekend in New York?")
    c.start()
    p = c.plan_step(2.1, 0.0141, [("browser", "Open the Luma discover page for New York"), ("browser", "Read the three most popular weekend events")])
    c.plan([("browser", "Open the Luma discover page for New York", "running"), ("browser", "Read the three most popular weekend events", "pending")])
    s = c.act("browser", 3.2, p, 0.0124, "browse open https://luma.com/discover", browse("open", "https://luma.com/discover"))
    c.shot("browser", 1.4, s, "https://luma.com/discover", "Discover events · Luma")
    c.answer("browser", 2.4, p, 0.0112, "The discover page is open; the New York list is behind link 3.")
    c.plan([("browser", "Open the Luma discover page for New York", "done"), ("browser", "Read the three most popular weekend events", "pending")])
    c.ret("browser", p, True, "The discover page is open; the New York list is behind link 3.")
    d = c.delegate(2.2, 0.0153, 1, "browser", "Read the three most popular weekend events")
    c.plan([("browser", "Open the Luma discover page for New York", "done"), ("browser", "Read the three most popular weekend events", "running")])
    s = c.act("browser", 3.0, d, 0.0153, "browse click 3", browse("click", link=3))
    c.shot("browser", 1.6, s, "https://luma.com/ny", "New York · Luma")
    c.act("browser", 2.8, d, 0.0088, "browse more", browse("more"))
    c.answer("browser", 2.6, d, 0.0192, "Rooftop Jazz Night, AI Builders Meetup, Sunday Sketch Club.")
    c.plan([("browser", "Open the Luma discover page for New York", "done"), ("browser", "Read the three most popular weekend events", "done")])
    c.ret("browser", d, True, "Rooftop Jazz Night (Sat 7:00 pm), AI Builders Meetup (Sat 6:30 pm), Sunday Sketch Club (Sun 11:00 am).")
    text = (
        "Here are the three most popular events in New York this weekend:\n\n"
        "1. **Rooftop Jazz Night** — Saturday, 7:00 pm · Williamsburg · [luma.com/e/jazz-rooftop](https://luma.com/e/jazz-rooftop)\n"
        "2. **AI Builders Meetup** — Saturday, 6:30 pm · SoHo · [luma.com/e/ai-meetup](https://luma.com/e/ai-meetup)\n"
        "3. **Sunday Sketch Club** — Sunday, 11:00 am · Chelsea · [luma.com/e/sketch-club](https://luma.com/e/sketch-club)"
    )
    c.answer("orchestrator", 3.4, None, 0.0425, text)
    c.reply(text, 0.4)
    return c


def files_run() -> Chat:
    c = Chat("files-run", "2026-10-01T08:30:00")
    goal = "Count the PDF files under D:\\Example\\Projects"
    c.user("How many PDFs are in my Projects folder?")
    c.start()
    p = c.plan_step(1.9, 0.0098, [("files", goal)])
    c.plan([("files", goal, "running")])
    c.act("files", 2.4, p, 0.0071, "files count D:\\Example\\Projects *.pdf", {"kind": "files", "op": "count", "path": "D:\\Example\\Projects", "pattern": "*.pdf"})
    c.answer("files", 3.1, p, 0.0048, "42 PDF files, in 9 folders.")
    c.plan([("files", goal, "done")])
    c.ret("files", p, True, "42 PDF files, in 9 folders.")
    text = "There are **42** PDF files under `D:\\Example\\Projects`, spread over 9 folders."
    c.answer("orchestrator", 2.2, None, 0.0213, text)
    c.reply(text, 0.3)
    return c


def refused_action() -> Chat:
    c = Chat("refused-action", "2026-09-30T18:05:00")
    goal = "Open a forecast page for Lisbon and read next week"
    c.user("What's the weather in Lisbon next week?")
    c.start()
    p = c.plan_step(2.0, 0.0102, [("browser", goal)])
    c.plan([("browser", goal, "running")])
    c.act("browser", 2.5, p, 0.0067, "refused fetch: a fetch action is not available to this role", {"kind": "fetch", "url": "https://forecast.example/lisbon"}, "refuse")
    s = c.act("browser", 2.9, p, 0.0119, "browse open https://forecast.example/lisbon", browse("open", "https://forecast.example/lisbon"))
    c.shot("browser", 1.5, s, "https://forecast.example/lisbon", "Lisbon, 7-day forecast · Example Weather")
    c.answer("browser", 2.7, p, 0.0151, "Mostly sunny, 22–25 °C; rain on Thursday.")
    c.plan([("browser", goal, "done")])
    c.ret("browser", p, True, "Mostly sunny, 22–25 °C; rain on Thursday.")
    text = "Lisbon next week is **mostly sunny**, 22–25 °C, with one rainy day on **Thursday**."
    c.answer("orchestrator", 2.4, None, 0.0176, text)
    c.reply(text, 0.3)
    return c


def stopped() -> Chat:
    c = Chat("stopped", "2026-09-30T14:20:00")
    goal = "Open the engineering blog and read the three newest posts"
    c.user("Summarise the three most recent posts on the Example Engineering blog.")
    c.start()
    p = c.plan_step(2.2, 0.0119, [("browser", goal)])
    c.plan([("browser", goal, "running")])
    s = c.act("browser", 3.1, p, 0.0131, "browse open https://blog.example/engineering", browse("open", "https://blog.example/engineering"))
    c.shot("browser", 1.3, s, "https://blog.example/engineering", "Engineering · Example Blog")
    c.stop("browser", 4.0, "Stopped by you.", p)  # the User pressed Stop between steps
    c.plan([("browser", goal, "failed")])
    c.ret("browser", p, False, "Stopped by you.")
    c.stop("orchestrator", 0.1, "Stopped by you.")
    c.reply("Stopped by you.", 0.1)
    return c


def over_budget() -> Chat:
    c = Chat("over-budget", "2026-09-29T16:40:00")
    goal = "Compare prices for 12 laptop models across the shops"
    c.user("Compare the price of every 14-inch laptop on all the big shop sites.")
    c.start()
    p = c.plan_step(2.4, 0.0188, [("browser", goal)])
    c.plan([("browser", goal, "running")])
    for i, shop in enumerate(["shop-a", "shop-b", "shop-c", "shop-d", "shop-e", "shop-f"], 1):
        url = f"https://{shop}.example/laptops?size=14"
        s = c.act("browser", 3.6, p, 0.164, f"browse open {url}", browse("open", url))  # long pages: expensive reads
        if i in (1, 3):
            c.shot("browser", 1.8, s, url, f"14-inch laptops · {shop}.example")
    c.stop("browser", 1.0, f"Stopped: the ${CAP:.2f} budget for this run is used up.", p)
    c.plan([("browser", goal, "failed")])
    c.ret("browser", p, False, f"Stopped: the ${CAP:.2f} budget for this run is used up.")
    c.stop("orchestrator", 0.1, f"Stopped: the ${CAP:.2f} budget for this run is used up.")
    c.reply(f"Stopped: the ${CAP:.2f} budget for this run is used up.", 0.1)
    return c


def declined() -> Chat:
    c = Chat("declined", "2026-09-29T11:00:00")
    c.user("Pay my electricity invoice from my bank account.")
    c.reply(
        "That's payments and transfers, which I won't do. I can look things up, fetch public pages, and answer questions — just not that.",
        1.2,
        with_run=False,
    )
    return c


def chat_reply() -> Chat:
    c = Chat("chat-reply", "2026-09-28T20:15:00")
    c.user("What is 2 + 3?")
    c.start()
    c.answer("orchestrator", 1.8, None, 0.0182, "5")
    c.reply("5", 0.3)
    return c


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for build, name in [(web_run, "web-run"), (files_run, "files-run"), (refused_action, "refused-action"), (stopped, "stopped"), (over_budget, "over-budget"), (declined, "declined"), (chat_reply, "chat-reply")]:
        chat = build()
        (OUT / f"{name}.json").write_text(json.dumps(chat.frames, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{name}.json  {len(chat.frames)} frames  ${chat.spent:.4f}  {chat.shots} shots")


if __name__ == "__main__":
    main()
