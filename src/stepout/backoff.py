"""How long to wait before another try. Imports nothing from the app, so a capability (which may not import the Model or Runner) can use it too."""

from __future__ import annotations

import random
from typing import Callable

RETRY_AFTER_CEILING_S = 30.0  # a provider or site asking for longer than this is not waited for
TOOL_ATTEMPTS = 2  # a read-only tool: the first try and one more
TOOL_BASE_S, TOOL_CAP_S = 1.0, 8.0


def wait(attempt: int, base_s: float, cap_s: float, rng: Callable[[], float] = random.random) -> float:
    """Seconds to wait after try number `attempt` has failed: exponential from `base_s` up to `cap_s`, with up to half shaved off so that retries do not line up."""
    return min(cap_s, base_s * 2 ** (attempt - 1)) * (0.5 + 0.5 * rng())
