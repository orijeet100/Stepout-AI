---
title: "feat: Stepout on macOS (the chat, web research and the phone)"
type: feat
status: draft
date: 2026-10-16
origin: conversation 2026-10-14 (triage after the Windows start flow; macOS deliberately left out of that work)
---

# feat: Stepout on macOS

## Overview

Stepout installs and runs on Windows with one command and repairs itself on every start ([ADR 0019](../adr/0019-one-command-install.md), [0020](../adr/0020-phone-access-through-tailscale-serve.md), [0021](../adr/0021-start-repairs-itself.md)). This plan makes the same true on a Mac for the chat, web research and the phone link. **File access stays off on a Mac in this plan** (Units below, and Open questions): its block list is Windows paths, and a wrong block list is a security bug, not a convenience bug.

Nothing here is built. Every fact about macOS below is marked *to verify* until it has been checked on a Mac or in the vendor's docs; this plan was written without one.

## Support list (what we would promise)

| Platform | Status |
|---|---|
| Windows 11, x64 | built; tested on one laptop and on GitHub's `windows-latest` runner. Windows 10 is expected to work and has not been tested |
| macOS on Apple Silicon (the oldest version to be set by what Tailscale and Playwright support: *to verify*) | this plan |
| Intel Macs, Linux, Windows on ARM | not planned, and not tested; Files already fails closed off Windows |

Anything outside the list should say "not supported yet" once, at start-up, and stop. Today `stepout` starts on other systems; only Files ("no file access on this system yet" when asked) and the phone setup ("Windows-only for now") say so, and nothing stops at start-up.

## What differs from Windows

| Piece | Windows (built) | macOS (to verify each) |
|---|---|---|
| Install `uv` | `winget install astral-sh.uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` (uv's documented installer) |
| Data folder (`paths.home()`) | `%LOCALAPPDATA%\Stepout` | `~/Library/Application Support/Stepout` (today the fallback is `~/.local/share/Stepout`) |
| Install Tailscale | `winget install Tailscale.Tailscale`, after a yes | the Homebrew cask or the download page; whether the Mac App Store build or the standalone build exposes the CLI and `serve` |
| Tailscale CLI | `Program Files\Tailscale\tailscale.exe` | inside the app bundle (`Tailscale.app/Contents/MacOS/Tailscale`) |
| First sign-in | tray icon, browser | menu bar icon; the first run also asks to approve a VPN configuration or system extension in System Settings (one more step than Windows, and it cannot be automated) |
| Keep awake | `SetThreadExecutionState` | `caffeinate -i -w <pid>` |
| Headless browser | Chrome, else Edge (every PC has Edge) | Chrome if installed, else offer `playwright install chromium` with consent; many Macs have neither Chrome nor Edge |
| Stop | `taskkill /PID <pid> /T /F` | `os.kill(pid, SIGTERM)` (already the non-Windows branch in `stop()`) |
| Phone question at first run | asked (`os.name == "nt"`) | must be asked there too |
| File access | built | **off**, with "not on a Mac yet" |
| Shell | PowerShell 5.1: no `&&` | zsh |

## Units

1. **One platform table in code.** Today the Windows checks are scattered (`os.name` in `files.py`, `init.py`, `remote.py` and `app.py`). One small module names, per platform: the Tailscale installer command, where its CLI lives, how to keep the machine awake, the data folder, and whether Files is on. Nothing else branches on the platform.
2. **Home on macOS.** `~/Library/Application Support/Stepout`; a test per platform with the environment faked.
3. **Tailscale on macOS** in `remote.setup`: find the CLI, offer the install, wait for the sign-in and the approval prompt, and say what to click. The fake-`tailscale` tests run once per platform with that platform's paths and states (not installed, not signed in, HTTPS off, rename lag, Serve fails, port taken).
4. **Keep awake** with `caffeinate`, ended with the process.
5. **The browser**: Chrome, then Edge, then the Chromium offer; the "not installed" message names what it tried.
6. **First run and `stop`** work without the Windows gate; the unsupported-platform message from the support list.
7. **CI**: a macOS runner (Apple Silicon) next to `windows-latest`, running the same smoke install, with the Windows-only tests marked and skipped there.
8. **Docs**: per-platform install lines in the README, the support list in the architecture map, and an ADR for the platform table.

## Verify first

- The Tailscale CLI's path and which macOS build has `serve`; the Homebrew cask's name; whether `tailscale serve --bg` and its output are the same.
- Playwright's `chrome` and `msedge` channels on macOS, and `page.screencast` there (the live view uses it).
- uv's installer line and where it puts `uv` on a Mac.
- The first-run approvals on a Mac, step by step.

## How we would know it works

A macOS runner proves the install and the start on a clean machine; the fake-`tailscale` tests prove each state for each platform's paths. The Tailscale sign-in and a real phone cannot be run on a runner, so a real Mac and a phone stay a manual checklist, with `stepout status` pasted into the report. Without a Mac to test on, the Mac path ships labelled "not tested on real hardware" in the README.

## Later (not in this plan)

- **Files on a Mac:** a macOS block list (Keychains, browser profiles, `/System`, `/Library`, Home), POSIX path resolution in place of the Windows shape checks, and a security review, since a wrong block list gives the agents the disk.
- **`stepout remote --always-on`:** start the chat at login so the phone link survives a reboot: a Task Scheduler entry on Windows, a LaunchAgent on a Mac. Opt-in and removable (`--always-on off`); it adds a startup entry the user has to understand.

## Risks

| Risk | Handling |
|---|---|
| macOS Tailscale builds differ in what the CLI offers | the *Verify first* list; fall back to "open Tailscale and sign in" with the download page |
| A Mac with no Chrome and no Edge | the Chromium offer, with consent and its size said |
| Untested on real hardware | the CI smoke test, the per-platform fake tests, and an honest label in the README |

## Open questions

1. Does the first Mac release include file access? Recommended: no (above).
2. Is there a Mac and a phone to test on? If not, the README label stays until there is.
