# 0007 — Brain and hands: Actions and Results are plain data

Status: accepted · 2026-10-07

The Assistant has a brain (Intake, Runner, Memory, Ledger, the model calls) and hands (Browser, Fetcher, Files). In V0 both run in one process on the laptop. In V1 the brain moves to a server, the Browser becomes a container per Task, and Files becomes a small helper on the User's laptop that connects *outward* (no inbound ports) and enforces Grants itself. To keep that move cheap, every Action and Result is plain serializable data from S1 — no live objects, handles or callbacks — and a round-trip test enforces it. Rejected: building the hub and helper in V0 (bigger than any slice, and V0's claim doesn't need it), and tunnelling into the laptop (exposes the laptop instead of connecting out).
