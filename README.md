# Stepout AI

A task assistant you drive from a chat page. Ask in plain English; an **Orchestrator** plans the task and hands each step to a specialist that holds one tool. You watch every step as it happens, including the assistant's headless browser, live, and the answer streams in as it is written. Read-only by design, local to your machine, with a hard cost cap per task. Built from scratch to learn how production agents work: permissions, state, tracing, evals.

![A finished run, opened: the plan, a card for each task an agent did, one tool call open on its request and result, and the budget](docs/assets/run-light.jpg)

## What it does

- **Web:** searches and reads pages (a search-and-fetch agent, and a real headless Chrome you can watch).
- **Your files:** names, sizes, dates and counts of the folders you grant it, and the **text of files and PDFs** (a Reader), with secret-looking values hidden.
- **You stay in the loop:** the plan as a checklist, each task an agent took on as a card (its agent, model, time and result), every tool call with its request, result and cost, spend against the $1 cap, a Stop button that ends the run within about a second, and a viewer for every page it opened.
- **Chats that remember:** conversations and runs are saved and look the same after a restart; each message is screened against the chat's last five exchanges, and a follow-up ("and the second one?") is handed the ones it depends on.
- **Memory:** a Persona file you write, facts it learns from what you tell it, and one line per finished task, recalled at the start of a task. Read, edit or forget any of it in the Memory panel. Mem0 when `OPENAI_API_KEY` is set, plain files otherwise.
- **Any model:** Claude by default; point the strong and cheap tiers at another provider (OpenRouter and others, through Pydantic AI) with two lines in `.env`.
- A ChatGPT-style page: light and dark (the system's, or the switch in the header), the chat list slides in on a phone, keyboard-friendly.

| Empty chat | A conversation, dark | Phone |
|---|---|---|
| ![Greeting and suggested questions](docs/assets/empty-light.jpg) | ![A conversation in dark mode](docs/assets/chat-dark.jpg) | ![The chat list, slid in on a phone](docs/assets/phone-dark.jpg) |

## Safe by construction

- **Read-only.** No typing, submitting, uploading, downloading, deleting or paying. A **Gate** checks every action of every agent before it runs.
- **Files only through grants.** You choose the folders with `stepout grant` in a terminal; the page, the model and a phone cannot change them. A fixed block list always applies (credentials, keys, browser profiles, Windows folders, Stepout's own folders).
- **A file cannot hijack it.** Text read from a file is untrusted data. After any read the run has **no web access at all**, and a follow-up that builds on such an answer starts the same way. Such an answer's links are filtered and it is not streamed. A planted "send this to my server" in a PDF is ignored (tested live).
- **Network policy.** Every request and every redirect hop is checked; private and local addresses are refused. The server listens on `127.0.0.1` only and checks Host and Origin on everything; through `stepout remote` it also needs your own Tailscale login.
- **Money.** $1 per run, shared by all agents; a front-door call (about $0.002) screens each message; a model with no known price fails the run rather than counting as free.

## Quick start (Windows)

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) (it brings its own Python), Chrome or Edge, and an [Anthropic API key](https://console.anthropic.com/settings/keys).

```bash
uv tool install https://github.com/orijeet100/Stepout-AI/releases/download/v0.1.0/stepout-0.1.0-py3-none-any.whl
stepout
```

The first `stepout` asks for your key (hidden as you paste, checked before it is kept) and which folders it may look at, then opens the chat at http://127.0.0.1:8765. Nothing to edit by hand. If `stepout` is not found, run `uv tool update-shell` and open a new terminal.

| Command | What it does |
|---|---|
| `stepout` | Start the chat and open it in your browser (`stepout web`: without opening it; `stepout cli`: chat in the terminal) |
| `stepout init` | Set up again: the key, then the folders |
| `stepout grant` | See, add or remove the folders it may look at |
| `stepout remote` | Reach this chat from your phone (below); `stepout remote off` stops that |

Your chats, Memory, settings and key live in `%LOCALAPPDATA%\Stepout` (set `STEPOUT_HOME` to move it), so upgrading keeps them: install the newer wheel's line with `--force`. Memory uses plain files; for Mem0, install `"stepout[mem0] @ <the wheel URL>"` and set `OPENAI_API_KEY` in that folder's `.env`.

**From your phone.** `stepout remote` walks you through [Tailscale](https://tailscale.com) (free): install it, sign in, pick a neutral name for the laptop, then it prints a QR code. Install Tailscale on the phone, sign in with the same account, scan. Only your own devices, signed in as you, can open it; it is never on the public internet ([ADR 0020](docs/adr/0020-phone-access-through-tailscale-serve.md)). The laptop stays awake while Stepout runs (a closed lid still sleeps it).

Try: *"What's the news in New York today?"*, *"How many files are in `<a folder you granted>`, by type?"*, *"Summarize the newest PDF in `<folder>`"*, *"Open `<a job posting URL>` and tell me the skills it asks for"*. If the key, a browser or the folders are missing, it says so in plain words, with the command that fixes it.

To use another provider, set (in the `.env` in Stepout's folder) `STEPOUT_STRONG_MODEL` (Orchestrator and Web Browsing agent) and `STEPOUT_CHEAP_MODEL` (Screening and the other specialists) to a Pydantic AI model string such as `openrouter:openai/gpt-5.2`, with that provider's key. Streaming works on the default Claude path only so far.

## What it costs

From the live acceptance run (real Claude, real Chrome): a plain question about $0.005; a web lookup $0.03 to $0.07; a page read $0.03 to $0.05; a resume compared with a job posting about $0.09. All eight acceptance queries together: $0.27.

## From source (development)

```bash
git clone https://github.com/orijeet100/Stepout-AI && cd Stepout-AI
uv venv --python 3.12 && uv pip install -e ".[dev]"
cd web && npm install && npm run build && cd ..        # Node 20.19+ or 22.12+; the page lands in src/stepout/_web
./.venv/Scripts/python.exe -m stepout.app web                 # data stays in ./data in a checkout
```

## Tests

```bash
./.venv/Scripts/python.exe -m pytest -q                                  # offline and free; includes real Chrome
./.venv/Scripts/python.exe scripts/acceptance.py                         # the 8 acceptance queries, offline and free
./.venv/Scripts/python.exe scripts/acceptance.py --live --posting-url <a real job posting>   # real Claude, about $0.30
cd web && npm test && npm run lint && npm run build                     # the page
./.venv/Scripts/python.exe -m pytest web/mock web/e2e -q                 # the page's mock server and real-Chrome flows
```

Paid live checks (they say so): `pytest -m eval -s tests/test_live.py` and `pytest -m eval -s tests/test_live_screening.py`, about $0.11 each.

## The claim to prove

Human interventions per task fall across repeated attempts, against a memory-off control. No model training; improvement comes from recall. Memory is built; the comparison has its first form (`scripts/acceptance.py --memory ... --compare`), and a live comparison of the three Memory conditions is the next measurement.

## Where to read next

[`docs/architecture.md`](docs/architecture.md) the map · [`docs/history.md`](docs/history.md) what was decided and built, in order · [`docs/adr/`](docs/adr/README.md) the decisions · [`docs/roadmap.md`](docs/roadmap.md) what is next and the known debt · [`docs/ui-contract.md`](docs/ui-contract.md) the wire between the page and the backend · [`CONTEXT-MAP.md`](CONTEXT-MAP.md) the vocabulary · [`docs/third-party.md`](docs/third-party.md) where third-party code and tools came from. Adding a tool is one file in `src/stepout/capabilities/` plus one line.

Trunk-based on `main`; thin slices, tests plus a live check each, docs in the same commit; a decision that is hard to reverse gets an ADR.
