# 0003 — Memory: plain files first, mem0 as a measured challenger

Date: 2026-10-06 · Status: accepted

**Decision.** Memory starts as plain files (Persona in `persona.md`, History, Notes) behind `recall`, `remember` and `forget`. The write rules sit above an internal storage seam; mem0 is added later as a second store behind that seam and compared on the golden set (S9).

**Why.** Memory is what the headline metric tests, so owning the first version means every improvement is explainable. "Memory off" is just an empty folder, and the user can edit the files directly. "Which layer is best?" becomes a measurement instead of an opinion.

**Rules that don't depend on the implementation.** Writes only from the user's own messages/corrections and the agent's own run outcomes; never from page/search/fetched content; never secrets or critical PII; user edits are pinned; `/forget` deletes; site notes expire.
