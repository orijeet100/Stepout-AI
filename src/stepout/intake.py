"""Intake: slash commands, then the front door (stepout/screening.py).

Every other message gets one screening call. It may be declined, answered as plain chat, or let through with the
earlier Exchanges it depends on. If the call fails or makes no sense, the message goes through anyway, carrying the
last few Exchanges, and the failure is recorded: the front door must never be the reason a legitimate request dies.
"""

from __future__ import annotations

from typing import Callable, Literal

from pydantic import BaseModel

from stepout.domain import ChatReply, Decline, Event, Exchange, Message, Proceed
from stepout.ledger import Ledger
from stepout.screening import Screener

_FALLBACK_EXCHANGES = 3  # how much history a message carries when the front door could not say what it links to


class NewTask(BaseModel):
    kind: Literal["new_task"] = "new_task"
    request: str
    previous: list[Exchange] = []  # the Exchanges it builds on, oldest first; none for a new Task
    cost_usd: float = 0.0  # what the front door spent; it counts against the Run


class ChatReading(BaseModel):
    kind: Literal["chat"] = "chat"
    text: str
    cost_usd: float = 0.0


class CommandReading(BaseModel):
    kind: Literal["command"] = "command"
    name: str
    args: str


class DeclinedReading(BaseModel):
    kind: Literal["declined"] = "declined"
    reason: str
    alternative: str
    cost_usd: float = 0.0


Reading = NewTask | ChatReading | CommandReading | DeclinedReading


class Intake:
    def __init__(self, screener: Screener, ledger: Ledger, exchanges: Callable[[str], list[Exchange]] = lambda conversation_id: []) -> None:
        """`exchanges(conversation_id)`: the chat's recent answered Requests, oldest first (history.exchanges)."""
        self._screener = screener
        self._ledger = ledger
        self._exchanges = exchanges

    async def read(self, message: Message) -> Reading:
        text = message.text.strip()
        if text.startswith("/"):
            name, _, args = text[1:].partition(" ")
            return CommandReading(name=name, args=args)

        recent = self._exchanges(message.conversation_id)
        try:
            decision, cost = await self._screener.screen(text, recent)
            failure = "the answer was not usable"
        except Exception as exc:  # an API error, a timeout: the message still goes through
            decision, cost, failure = None, 0.0, type(exc).__name__
        if decision is None:
            self._record("screening_fallback", message, {"request": text, "failure": failure}, cost)
            return NewTask(request=text, previous=recent[-_FALLBACK_EXCHANGES:], cost_usd=cost)

        match decision:
            case Decline(reason=reason, alternative=alternative):
                reading = DeclinedReading(reason=reason, alternative=alternative, cost_usd=cost)
            case ChatReply(text=reply):
                reading = ChatReading(text=reply, cost_usd=cost)
            case Proceed(related=related):
                reading = NewTask(request=text, previous=[x for x in recent if x.id in related], cost_usd=cost)
        self._record("screening", message, {"request": text, "decision": decision.kind, "related": getattr(decision, "related", [])}, cost)
        return reading

    def _record(self, kind: str, message: Message, data: dict, cost: float) -> None:
        self._ledger.record(Event(kind=kind, conversation_id=message.conversation_id, data=data, cost_usd=cost))
