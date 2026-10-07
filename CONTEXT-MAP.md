# Context Map

Stepout has two bounded contexts. Telegram, the web page, the model provider and websites are outside both; their words never enter either glossary.

## Contexts

- [Assistant](./src/stepout/CONTEXT.md) — the product: takes Requests from the User on a Channel, carries out Tasks, asks Questions, and keeps Memory.
- [Evaluation](./tests/eval/CONTEXT.md) — the proof: runs Golden tasks against the Assistant as a Simulated user on the Simulated web, and decides what counts as an Intervention.

## Relationships

- **Evaluation → Assistant**: Evaluation is downstream and talks to the Assistant only the way a User would — as a Channel (the Simulated user sends Messages and gives Answers and Approvals) — and reads the Assistant's Ledger. It never reaches inside the Assistant.
- **Assistant → Evaluation**: none. The Assistant does not know it is being evaluated and never grades itself.
- **Outside world → Assistant**: Telegram updates, model completions and web pages are translated at the edge into Messages, Actions and Untrusted content.
