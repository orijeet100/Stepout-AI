# 0021 — Start repairs itself: one copy per port, a status check, and the phone link only once it answers

Status: accepted · 2026-10-14 · built; amends 0019 and 0020.

**Decision.** Running `stepout` again is always safe, and each run repairs what has drifted. Three choices make that true:

1. **One copy per port.** Before it starts, `stepout` asks the port for `GET /api/health`. A Stepout answering there (`{"app": "stepout", "v": 1}`) means one is already running: `stepout` prints its address, opens it, and starts no second copy. `stepout stop` ends the running chat through a pid file, `<Home>/stepout-<port>.pid`, and only after the same health check confirms that the process on the port is Stepout.
2. **Status names each fault with its fix.** `stepout status` prints one line per part, marked `ok`, `FIX`, or `--` for information: the chat, the API key, the folders, and for the phone Tailscale, the laptop's name, Serve, the phone's online state and the phone address. It exits 1 when anything needs fixing.
3. **The phone link is repaired at every start and announced last.** When phone access is set up, a start checks Tailscale and turns Serve back on if it is off, quietly. Then it fetches its own phone address from this laptop, and prints "From your phone" (and the QR code, when phone access was just set up) only once that answers as Stepout. Otherwise it prints the problem and says to run `stepout status`.

`stepout remote` no longer asks for a name. A laptop that still has its computer's name is renamed to `stepout-xxxx`; a name already chosen is kept, so the phone link does not change. It waits for the new name to take effect before it keys Serve to it. It installs Tailscale with winget after a yes (otherwise it shows the download page), and it never resets Serve settings it did not make. The first run asks once, after setup, whether to use the phone too.

**Why.** The first real phone run (2026-10-12, one Windows laptop) failed in this order:

- A copy started before phone access was set up had no phone settings and answered the phone 403.
- After the laptop was renamed, Serve stayed keyed to the old name, so the phone link did not answer.
- The link was announced before it answered.
- The laptop's name was the User's to choose, and HTTPS names go into a public certificate log, so a real name was published.
- A port that was already in use gave no way to tell whose it was.

**Found by the clean-room run.** A `grants.toml` saved with a byte-order mark (PowerShell's `Set-Content`, older Notepad) ended the start with a traceback after the server was already up. It is now read as `utf-8-sig`, and a file that still cannot be read allows no folders, says so and names `stepout grant`, which rewrites it. `stepout status` and `stepout grant` survive it too. The light commands (`status`, `stop`, `--help`) also no longer import the model SDKs, which took about 5 seconds.

**Limits.** Windows only; macOS is a separate plan. The Tailscale sign-in and the one-time Serve consent page cannot be automated: `stepout` waits and says what to do. A recycled process id is guarded only by the health check before `stepout stop` kills it. Tailscale's CLI output (`status --json`, `serve status --json`) was checked against a real tailnet on one machine only. The phone address check runs on this laptop, so it proves Serve and the guard, not the phone's own connection; `stepout status` shows the phone's state separately.
