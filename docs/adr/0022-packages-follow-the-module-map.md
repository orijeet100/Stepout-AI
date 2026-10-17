# 0022 — Packages follow the module map, and only where the move is free

Status: accepted · 2026-10-17 · built.

**Decision.** A row of the Modules table in [`architecture.md`](../architecture.md#2-modules) becomes a package under `src/stepout/` when it groups three or more files and moving them creates no import cycle. Every other module stays a flat file. Two rows qualify today:

- **`memory/`**: the seam is the package itself (`memory/__init__.py`, so `stepout.memory` imports did not change), with `persona.py`, `files.py`, `mem0.py`, `types.py`, `extract.py` and `commands.py` beside it.
- **`access/`**: what the Tools run on (`fetch.py`, `browser.py`, `search.py`, `files.py`, `reader.py`, `redact.py`), with an empty `__init__.py` so importing one pulls in nothing else. The network policy, the block list and the secret screen now sit in one folder.

`channels/` and `capabilities/` were packages already. `app.py` stays at the top: it is the entry point (`stepout.app:cli`, `python -m stepout.app`).

**Why.** Grouping by feature means a bug in one area is fixed in one folder, and the folder tree reads like the map. But a package is worth it only when it costs nothing. The rows left flat were each checked:

- **Model port** (`model`, `pydantic_model`, `retry`, `scope`) and **Runner** (`runner`, `roles`): `model.py` imports `roles`, and `runner` imports `model`. With each seam in its package's `__init__`, that becomes an import cycle. Fixing it would mean changing the code, not just moving it.
- **Ledger + Store** (`ledger`, `store`, `history`) and **Log + Capture** (`logs`, `capture`, `housekeeping`): three small, distinctly named files each. Moving `store` also moves `migrations/` and the wheel's package-data glob: risk for little gain.

**Consequences.** Log lines from the moved modules carry their new logger names (`stepout.access.browser`, `stepout.memory.mem0`); nothing filters on them. `access/files.py` finds the repo folder one level higher (`parents[3]`), and a test pins it to `paths._ROOT`. Revisit a flat row when it grows past a handful of files, or once the `model` → `roles` import is gone.
