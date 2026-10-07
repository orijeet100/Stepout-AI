"""Runner: the agent loop, without a browser. submit(task) -> drives it to a reply."""

from __future__ import annotations

import os
from typing import Awaitable, Callable

from stepout import gate
from stepout.domain import AnswerAction, Event, FetchAction, Reply, Task
from stepout.fetch import Fetcher
from stepout.ledger import Ledger
from stepout.model import SONNET, Model, ModelRequest

_SYSTEM = (
    "You are a helpful assistant answering one request. For time-sensitive or "
    "current-fact questions, use web_search and cite a source. If you already "
    "know the exact URL to read, use the fetch tool instead of guessing content."
)
_MAX_STEPS = 2


class Runner:
    def __init__(
        self,
        model: Model,
        fetcher: Fetcher,
        ledger: Ledger,
        notify: Callable[[Reply], Awaitable[None]],
    ) -> None:
        self._model = model
        self._fetcher = fetcher
        self._ledger = ledger
        self._notify = notify
        self._task_cap = float(os.environ.get("STEPOUT_TASK_CAP_USD", "0.50"))

    async def submit(self, task: Task) -> None:
        spent = 0.0
        user_text = task.request
        for _ in range(_MAX_STEPS):
            if spent >= self._task_cap:
                await self._notify(Reply(text=f"Stopping — task budget (${self._task_cap:.2f}) reached."))
                return

            response = await self._model.call(
                ModelRequest(model=SONNET, system=_SYSTEM, user_text=user_text, tools=True)
            )
            spent += response.cost_usd
            self._ledger.record(
                Event(task_id=task.id, kind="model_call", data={"action": response.action.model_dump()}, cost_usd=response.cost_usd)
            )

            verdict = gate.check(response.action)
            self._ledger.record(Event(task_id=task.id, kind="verdict", data={"verdict": verdict.model_dump()}))

            match response.action:
                case AnswerAction(text=text):
                    await self._notify(Reply(text=f"{text}\n\n(cost: ${spent:.4f})"))
                    return
                case FetchAction(url=url):
                    page = await self._fetcher.get(url)
                    self._ledger.record(Event(task_id=task.id, kind="action", data={"fetch": url}))
                    user_text = f"{task.request}\n\nFetched {url}:\n{page.text[:4000]}"

        await self._notify(Reply(text=f"Couldn't finish in {_MAX_STEPS} steps. (cost: ${spent:.4f})"))
