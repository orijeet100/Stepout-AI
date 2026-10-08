"""The real backend with a scripted model and browser: costs nothing, needs no API key and no Chrome.

    python web/mock/real_backend.py [--port 8765] [--db data/demo-real-backend.db] [--delay 1.2]
    then open http://127.0.0.1:8765   (after `cd web && npm run build`; or run `npm run dev` with VITE_BACKEND=http://127.0.0.1:8765)

This is the wiring of `python -m stepout.app web` (WebChannel, SavedChannel, Intake, Runner, Ledger, the SQLite Store, history.py,
the Gate), so what the page does here is what it does against the paid backend. Only the two things that cost money or
need Chrome are replaced: the model follows a short script chosen by the request, and the browser returns invented pages
whose screenshots are the ones in web/fixtures/shots. Chats are kept in --db (git-ignored data/), so restarting this
shows them again. Try: "events this weekend" (a web run), "summarise the blog" (slower, good for Stop), "2 + 3", "pay my invoice" (declined).
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from stepout import history  # noqa: E402
from stepout.app import SavedChannel, run  # noqa: E402
from stepout.capabilities.browse import BrowseAction  # noqa: E402
from stepout.channels.web import StoreHistory, WebChannel  # noqa: E402
from stepout.domain import AnswerAction, ChatReply, DelegateAction, Decline, PlanAction, PlanStep, Proceed, Task  # noqa: E402
from stepout.intake import Intake  # noqa: E402
from stepout.ledger import Ledger  # noqa: E402
from stepout.model import ModelRequest, ModelResponse  # noqa: E402
from stepout.runner import Runner  # noqa: E402
from stepout.store import Store  # noqa: E402

SHOTS = ROOT / "web" / "fixtures" / "shots"
PAGES = {  # url -> (title, screenshot in web/fixtures/shots)
    "https://luma.com/discover": ("Discover events · Luma", "959612fc4799adfc1594ee439ebc5832/1.jpg"),
    "https://luma.com/ny": ("New York · Luma", "959612fc4799adfc1594ee439ebc5832/2.jpg"),
    "https://blog.example/engineering": ("Engineering · Example Blog", "b617329283bea49463ba30655fa8a766/1.jpg"),
}


def say(text: str, cost: float = 0.004) -> ModelResponse:
    return ModelResponse(action=AnswerAction(text=text), cost_usd=cost)


def web_script(url: str, goal_a: str, goal_b: str, found: str, final: str) -> list[ModelResponse]:
    plan = PlanAction(steps=[PlanStep(role="browser", goal=goal_a), PlanStep(role="browser", goal=goal_b)])
    return [
        ModelResponse(action=plan, cost_usd=0.014),
        ModelResponse(action=BrowseAction(op="open", url=url), cost_usd=0.012),
        say(f"Opened {url}.", 0.011),
        ModelResponse(action=DelegateAction(step=1), cost_usd=0.015),
        ModelResponse(action=BrowseAction(op="click", link=3), cost_usd=0.009),
        say(found, 0.019),
        say(final, 0.042),
    ]


def script_for(request: str) -> list[ModelResponse]:
    text = request.lower()
    if any(w in text for w in ("event", "luma", "weekend")):
        return web_script("https://luma.com/discover", "Open the Luma discover page for New York", "Read the weekend events", "Rooftop Jazz Night, AI Builders Meetup, Sunday Sketch Club.",
                          "Here are the three most popular events in New York this weekend:\n\n1. **Rooftop Jazz Night** — Saturday, 7:00 pm\n2. **AI Builders Meetup** — Saturday, 6:30 pm\n3. **Sunday Sketch Club** — Sunday, 11:00 am")
    if any(w in text for w in ("blog", "summar")):
        return web_script("https://blog.example/engineering", "Open the engineering blog", "Read the three newest posts", "Three posts: caching, queues, and on-call.",
                          "The three newest posts cover **caching**, **queues** and **on-call**.")
    return [say(f"(Scripted model, no cost.) You said: {request}", 0.002)]


class DemoScreener:
    """Stands in for the Haiku front door (stepout.screening): payments are declined, a greeting is answered, "and ..." links the chat's last exchange."""

    async def screen(self, text: str, recent):
        t = text.lower()
        if re.search(r"\b(pay|invoice|transfer)\b", t):
            return Decline(reason="That's a payment, which I won't do.", alternative="I can search the web, read pages and count files, read-only."), 0.001
        if t.strip(" !.?") in ("hi", "hello", "thanks", "thank you"):
            return ChatReply(text="Hello! Ask me to look something up."), 0.001
        return Proceed(related=[recent[-1].id] if recent and t.startswith("and ") else []), 0.001


class DemoModel:
    def __init__(self, delay: float) -> None:
        self.delay, self.script = delay, []

    async def call(self, request: ModelRequest) -> ModelResponse:
        await asyncio.sleep(self.delay)  # a model call takes a moment: gives you time to watch, and to press Stop
        return self.script.pop(0)


class DemoRunner(Runner):
    def __init__(self, model: DemoModel, *args, **kwargs) -> None:
        super().__init__(model, *args, **kwargs)
        self._demo = model

    async def submit(self, task: Task, previous=(), screening_cost: float = 0.0) -> None:
        self._demo.script = script_for(task.request)
        await super().submit(task, previous, screening_cost)


class DemoBrowser:
    """Invented pages; what a page "says" is its title."""

    def __init__(self) -> None:
        self.url = ""

    async def run(self, run_id: str, op: str, url: str | None = None, link: int | None = None):
        self.url = url or "https://luma.com/ny"  # a click on link 3 lands on the New York list
        title, shot = PAGES.get(self.url, (self.url, "959612fc4799adfc1594ee439ebc5832/1.jpg"))
        return f"URL: {self.url}\nTitle: {title}\nText: {title}. Listings follow.\nLinks:\n1. Home\n2. Sign in\n3. New York", shot

    async def close(self, run_id: str) -> None:
        pass

    async def aclose(self) -> None:
        pass


class NoFetcher:
    async def get(self, url):  # these scripts never fetch
        raise RuntimeError("the demo backend does not fetch")


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--db", type=Path, default=ROOT / "data" / "demo-real-backend.db")
    ap.add_argument("--delay", type=float, default=1.2, help="seconds per scripted model call")
    args = ap.parse_args()

    store = Store(args.db)
    ledger = Ledger(store)
    channel = WebChannel(port=args.port, shots=SHOTS, history=StoreHistory(store))
    port = await channel.start()
    print(f"Real backend, scripted model (costs nothing): http://127.0.0.1:{port}   chats in {args.db}   (Ctrl+C to stop)")
    model = DemoModel(args.delay)
    saved = SavedChannel(channel, ledger)
    runner = DemoRunner(model, NoFetcher(), ledger, saved.send, trace=channel.trace, cancel=channel.cancel, browser=DemoBrowser())
    await run(saved, Intake(DemoScreener(), ledger, lambda conversation_id: history.exchanges(store, conversation_id)), runner)


if __name__ == "__main__":
    asyncio.run(main())
