"""Runner: one agent loop, played as the Orchestrator and its specialist Roles (ADR 0010).

submit(task) runs the Orchestrator, which plans and delegates to specialists; every
Role shares one Budget, one Gate and one Ledger, and every event is streamed to `trace`.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Awaitable, Callable
from uuid import uuid4

import httpx

from stepout import gate
from stepout.domain import Allow, AnswerAction, BrowseAction, DelegateAction, Event, FetchAction, FilesAction, PlanAction, PlanStep, Reply, Task
from stepout.browser import Browser
from stepout.fetch import BlockedUrl, Fetcher
from stepout.files import Files
from stepout.ledger import Ledger
from stepout.model import Model, ModelRequest
from stepout.roles import ROLES

_MAX_PLANS = 3  # the first plan plus two re-plans
_TEXT_CHARS = 4000  # how much of a page or Finding a Role sees


@dataclass
class Finding:
    text: str
    ok: bool


@dataclass
class _Run:
    """Everything the Roles of one Run share."""

    task_id: str
    cap: float  # $ for the whole Run
    searches: int = 3  # web searches left
    spent: float = 0.0
    plan: list[PlanStep] = field(default_factory=list)
    plans: int = 0
    id: str = field(default_factory=lambda: uuid4().hex)


def _state(goal: str, plan: list[PlanStep], notes: list[str]) -> str:
    """What a Role sees each step: the goal, its plan, what it has learned. Not a transcript."""
    parts = [f"Task: {goal}"]
    if plan:
        parts.append("Plan:\n" + "\n".join(f"{i}. [{s.status}] {s.role}: {s.goal}" for i, s in enumerate(plan)))
    return "\n\n".join(parts + notes)


def _shrink_old_pages(notes: list[str], keep: int = 2) -> None:
    """Page views are big and a Role re-reads its notes every step: all but the newest two shrink to their first lines."""
    pages = [i for i, n in enumerate(notes) if n.startswith("browse ")]
    for i in pages[:-keep]:
        notes[i] = "(earlier page) " + " ".join(notes[i].splitlines()[1:3])[:200]


def _summary(action, plan: list[PlanStep]) -> str:
    match action:
        case PlanAction(steps=steps):
            return "plan: " + "; ".join(f"{s.role}: {s.goal[:70]}" for s in steps)
        case DelegateAction(step=i) if 0 <= i < len(plan):
            return f"delegate {i} → {plan[i].role}: {plan[i].goal}"
        case DelegateAction(step=i):
            return f"delegate {i}"
        case FetchAction(url=url):
            return f"fetch {url}"
        case FilesAction(op=op, path=path, pattern=pattern):
            return f"files {op} {path}" + (f" {pattern}" if pattern else "")
        case BrowseAction(op=op, url=url, link=link):
            return f"browse {op} {url or link or ''}".strip()
        case _:
            return action.kind


class Runner:
    def __init__(
        self,
        model: Model,
        fetcher: Fetcher,
        ledger: Ledger,
        notify: Callable[[Reply], Awaitable[None]],
        trace: Callable[[Event], Awaitable[None]] | None = None,
        cancel: asyncio.Event | None = None,
        files: Files | None = None,
        browser: Browser | None = None,
    ) -> None:
        self._model = model
        self._fetcher = fetcher
        self._ledger = ledger
        self._notify = notify
        self._files = files or Files()  # no Grants = no access
        self._browser = browser or Browser()  # starts Chrome only when a page is first opened
        self._trace = trace
        self._cancel = cancel or asyncio.Event()  # set by the Channel when the User presses Stop
        self._cap = float(os.environ.get("STEPOUT_TASK_CAP_USD", "1.00"))

    async def submit(self, task: Task) -> None:
        self._cancel.clear()
        run = _Run(task_id=task.id, cap=self._cap)
        try:
            finding = await self._agent("orchestrator", task.request, run, parent=None)
        finally:
            await self._browser.close(run.id)  # its pages are this Run's alone
        await self._notify(Reply(text=f"{finding.text}\n\n(cost: ${run.spent:.4f})"))

    async def _emit(self, run: _Run, kind: str, role: str, summary: str, *, parent=None, cost=0.0, **data) -> Event:
        event = Event(task_id=run.task_id, run_id=run.id, kind=kind, role=role, parent=parent, cost_usd=cost, data={"summary": summary, **data})
        self._ledger.record(event)
        if self._trace:
            await self._trace(event)
        return event

    async def _emit_plan(self, run: _Run) -> None:
        await self._emit(run, "plan", "orchestrator", "plan updated", steps=[s.model_dump() for s in run.plan])

    async def _stop(self, run: _Run, role: str, parent: str | None, text: str) -> Finding:
        await self._emit(run, "stop", role, text, parent=parent)
        return Finding(text, ok=False)

    async def _run_step(self, run: _Run, i: int, parent: str, notes: list[str]) -> None:
        """Run plan step `i` with its Role and note the Finding for the Orchestrator."""
        plan_step = run.plan[i]
        plan_step.status = "running"
        await self._emit_plan(run)
        child = await self._agent(plan_step.role, plan_step.goal, run, parent=parent)
        plan_step.status = "done" if child.ok else "failed"
        await self._emit_plan(run)
        await self._emit(run, "return", plan_step.role, f"{plan_step.status}: {child.text[:200]}", parent=parent, ok=child.ok)
        notes.append(f"Finding for step {i} ({plan_step.status}):\n{child.text[:_TEXT_CHARS]}")

    async def _agent(self, role_name: str, goal: str, run: _Run, parent: str | None) -> Finding:
        role = ROLES[role_name]
        notes: list[str] = []
        ran: set[str] = set()  # hand actions already run: asking again cannot change the answer
        for _ in range(role.max_steps):
            if self._cancel.is_set():
                return await self._stop(run, role_name, parent, "Stopped by you.")
            if run.spent >= run.cap:
                return await self._stop(run, role_name, parent, f"Stopped: the ${run.cap:.2f} budget for this run is used up.")

            plan = run.plan if role_name == "orchestrator" else []
            response = await self._model.call(
                ModelRequest(model=role.model, system=role.system, user_text=_state(goal, plan, notes), tools=list(role.tools), max_searches=run.searches)
            )
            run.spent += response.cost_usd
            run.searches -= response.searches

            action = response.action
            verdict = gate.check(action, role.actions)
            allowed = isinstance(verdict, Allow)
            summary = _summary(action, run.plan) if allowed else f"refused {action.kind}: {verdict.reason}"
            step = await self._emit(run, "step", role_name, summary, parent=parent, cost=response.cost_usd, action=action.model_dump(), verdict=verdict.kind)
            if not allowed:
                notes.append(f"Refused: {verdict.reason}")
                continue

            key = action.model_dump_json()
            match action:
                case FilesAction() | FetchAction() if key in ran:
                    notes.append("You already ran exactly this and the result will not change. Try something different, or answer.")
                case AnswerAction(text=text):
                    return Finding(text, ok=bool(text.strip()))
                case PlanAction(steps=steps):
                    if run.plans >= _MAX_PLANS:
                        notes.append("Refused: you have re-planned enough; answer with what you have.")
                    else:
                        run.plans += 1
                        run.plan = steps
                        await self._emit_plan(run)
                        await self._run_step(run, 0, step.id, notes)  # a plan starts itself: saves a model call per Task
                case DelegateAction(step=i):
                    if not 0 <= i < len(run.plan):
                        notes.append(f"Refused: there is no step {i}.")
                        continue
                    await self._run_step(run, i, step.id, notes)
                case FilesAction(op=op, path=path, pattern=pattern):
                    ran.add(key)
                    result = await self._files.run(op, path, pattern, self._cancel.is_set)
                    notes.append(f"files {op} {path}:\n{result[:_TEXT_CHARS]}")
                case BrowseAction(op=op, url=url, link=link):
                    view, shot = await self._browser.run(run.id, op, url, link)
                    notes.append(f"browse {op}:\n{view}")
                    _shrink_old_pages(notes)
                    if shot:
                        await self._emit(run, "shot", role_name, "page screenshot", parent=step.id, shot=shot)
                case FetchAction(url=url):
                    ran.add(key)
                    try:
                        page = await self._fetcher.get(url)
                        notes.append(f"Fetched {url}:\n{page.text[:_TEXT_CHARS]}")
                    except (BlockedUrl, httpx.HTTPError) as exc:
                        notes.append(f"Fetching {url} failed: {exc}")
        return Finding(f"The {role_name} agent couldn't finish in {role.max_steps} steps.", ok=False)
