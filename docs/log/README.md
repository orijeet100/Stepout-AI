# Decision and change log

Every **decision** and every **behaviour-changing commit** gets one entry here: one markdown file, never edited into a different story (to reverse something, add a new entry and mark the old one `superseded`). History before 2026-10-07 lives in [`../adr/`](../adr/) and `git log`.

| Log | ADR |
|---|---|
| Every decision and change, small or large, in time order | Rare: hard to reverse, surprising, a real trade-off |
| Many entries; cheap to write | A few; long-lived; the log entry links to it |

## Write an entry

```bash
python scripts/log.py new --kind change --lane main --title "Persist conversations" --tags store,history
```

It creates `docs/log/<date>-<slug>.md` from a template; fill in the four lines. Commit it **in the same commit** as the change.

| Field | Values |
|---|---|
| `kind` | `decision` (we chose) · `change` (code or docs behaviour changed) · `contract` (the UI contract changed) · `term` (glossary) · `note` |
| `lane` | `main` · `ui` · `both` · `docs` |
| `status` | `accepted` · `superseded` · `reverted` |
| `tags` | free words, lower-case, comma-separated |
| `refs` | files, ADRs, commits, tickets |

A `change` entry names the files touched, the tests that prove it, and the commit hash once known.

## Query it

```bash
python scripts/log.py list                       # everything, oldest first
python scripts/log.py list --lane ui             # one lane (entries marked "both" always show)
python scripts/log.py list --kind decision --since 2026-10-01
python scripts/log.py list --tag intake
python scripts/log.py list --grep "Haiku"        # full text
```

Plain search works too: `rg -l "status: superseded" docs/log`, `rg "tags:.*taint" docs/log`.

## Keep it honest

- `python scripts/log.py check --staged` fails a commit that changes code (`src/**/*.py|sql`, `web/src/**`, `web/index.html`) with no entry.
- Enable the hook once per clone: `git config core.hooksPath .githooks` (worktrees share it). A typo-only commit can pass with `STEPOUT_LOG=skip`.
- The merge agent runs `python scripts/log.py check --range main..<lane>` before every merge, hook or no hook.
- State and "what's next" still live in [`../STATUS.md`](../STATUS.md); the log answers "when and why did this change?".
