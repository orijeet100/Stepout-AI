---
date: 2026-10-08
kind: change
lane: ui
status: accepted
title: C3f: words while it waits and when a read fails; Retry reloads the open chat; reduced motion proven
tags: [ui,states,a11y,motion]
refs: []
---

**What.** (1) While the chat list has not been read yet the sidebar says "Loading chats…" (it used to say "No chats yet.", which was a guess); once read and empty it says "No chats yet."; if the read failed, "Your chats could not be loaded." (2) A chat that is open but not read yet shows "Loading…" in the thread instead of the new-chat prompt; if its read failed, "Nothing to show yet. Use “Retry now” above." (the banner above names what failed). A chat the backend has nothing stored for (404 on its detail) is an empty chat and is shown as one, not as loading forever. State: `listed` and `loaded` in the reducer. (3) **Retry now** after a failed read now reads the open chat again as well as the list (it read only the list, so a chat that failed to open stayed failed). (4) Reduced motion: the rule already existed (`animation` and `transition` off under `prefers-reduced-motion`, no smooth scrolling anywhere); it is now checked in real Chrome with the preference on (spinner, pulse, chevron, meter, drawer all stand still) and off (they do move), and mutation-checked.

**Why.** The Merge Agent's last slice: words instead of blank or wrong areas, and the reduced-motion claim proven. Only one live region (the banner) announces; the new texts are plain text so a screen reader is not told three things at once.

**Not done (known gaps, also in STATUS).** A skeleton (shimmer) loader; an `error` event line inside the run's step list (the reason already reaches the reply); a full keyboard pass beyond the drawer, the viewer, the skip link and the thumbnails (each has its own flow; there is no single whole-page tab-order test); a "chat does not exist" page (an unknown chat cannot be reached from the UI today).

**Evidence.** `web/src/store.ts`, `useBackend.ts`, `Sidebar.tsx`, `ChatView.tsx`, `App.tsx`. Vitest `States.test.tsx` (5; mutation-checked: a wrong waiting rule fails three). Playwright `test_motion.py` (2; dropping the reduced-motion rule fails it), `test_states.py` (2: a failed list and a failed chat, each recovered by Retry now).
