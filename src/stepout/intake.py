"""Intake: fast paths, scope screening, cheap-model routing."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from stepout import gate
from stepout.domain import Accept, Decline, Event, Message, Route, Unsure
from stepout.ledger import Ledger
from stepout.model import HAIKU, Model, ModelRequest

_ROUTE_SYSTEM = (
    "Classify the user's request as exactly one word: 'answer' if it can be "
    "answered from general knowledge with no tools, or 'lookup' if it needs "
    "a web search or a specific URL. Reply with only that one word."
)


class NewTask(BaseModel):
    kind: Literal["new_task"] = "new_task"
    request: str
    route: Route


class CommandReading(BaseModel):
    kind: Literal["command"] = "command"
    name: str
    args: str


class DeclinedReading(BaseModel):
    kind: Literal["declined"] = "declined"
    reason: str
    alternative: str


Reading = NewTask | CommandReading | DeclinedReading


class Intake:
    def __init__(self, model: Model, ledger: Ledger) -> None:
        self._model = model
        self._ledger = ledger

    async def read(self, message: Message) -> Reading:
        text = message.text.strip()
        if text.startswith("/"):
            name, _, args = text[1:].partition(" ")
            return CommandReading(name=name, args=args)

        screening = gate.screen(text)
        cost = 0.0
        match screening:
            case Decline(reason=reason, alternative=alternative):
                reading = DeclinedReading(reason=reason, alternative=alternative)
            case Accept(route=route):
                reading = NewTask(request=text, route=route)
            case Unsure():
                response = await self._model.call(
                    ModelRequest(model=HAIKU, system=_ROUTE_SYSTEM, user_text=text)
                )
                cost = response.cost_usd
                route = Route.LOOKUP if "lookup" in response.action.text.lower() else Route.ANSWER
                reading = NewTask(request=text, route=route)

        self._ledger.record(
            Event(kind="screening", conversation_id=message.conversation_id, data={"request": text, "reading": reading.model_dump()}, cost_usd=cost)
        )
        return reading
