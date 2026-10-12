"""ChatKeeper: what the User may do to a saved chat, and the one place that does it: rename it, or delete everything about it.

The Ledger is append-only for the Assistant; deleting is the User's call (the page asks first). A delete takes the chat's rows in one
transaction, then what lives outside the database (screenshots) and whatever else has registered an `after_delete` hook (Memory's entries
that came from the chat, Capture files). A hook that fails is logged and does not undo the delete.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Awaitable, Callable, Sequence

from stepout.ledger import Ledger

_log = logging.getLogger(__name__)

AfterDelete = Callable[[str, list[str]], Awaitable[None]]  # (chat id, the ids of its Runs)


class ChatKeeper:
    def __init__(self, ledger: Ledger, shots: Path, after_delete: Sequence[AfterDelete] = ()) -> None:
        self._ledger, self._shots, self._after_delete = ledger, shots, list(after_delete)

    def rename(self, conversation_id: str, title: str) -> bool:
        return self._ledger.rename_conversation(conversation_id, title.strip())

    async def delete(self, conversation_id: str) -> bool:
        """Purge the chat. False if there is no such chat."""
        run_ids = self._ledger.delete_conversation(conversation_id)
        if run_ids is None:
            return False
        for run_id in run_ids:
            shutil.rmtree(self._shots / run_id, ignore_errors=True)
        for hook in self._after_delete:
            try:
                await hook(conversation_id, run_ids)
            except Exception:
                _log.exception("cleanup after deleting a chat failed")
        return True
