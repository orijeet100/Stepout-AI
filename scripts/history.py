"""Iteration history: docs/history/*.toml + git + docs/log -> docs/history.html (target -> achieved, in order).

    python scripts/history.py            # write docs/history.html (git-ignored; regenerate any time)
    python scripts/history.py --check    # structure and commit hashes only; exit 1 on a problem

One TOML file per iteration (see docs/history/README.md). Commits that no iteration lists yet, and log entries whose
commit is not in a finished iteration, show up under the active iteration, so the page never silently falls behind.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import re
import subprocess
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import log  # noqa: E402  (scripts/log.py: reuse its frontmatter parser and the log folder)

ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / "docs" / "history"
OUT = ROOT / "docs" / "history.html"
STATUSES = ("done", "active", "planned")
LANES = ("trunk", "main", "ui")
REQUIRED = ("id", "title", "lane", "status", "aimed_at")


# ---- loading ---------------------------------------------------------------------------------------------------


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True).stdout


def load(hist: Path = HIST) -> tuple[list[dict], dict]:
    its = []
    for p in sorted(hist.glob("*.toml")):
        if p.name == "targets.toml":
            continue
        d = tomllib.loads(p.read_text(encoding="utf-8"))
        d["id"], d["_file"] = str(d.get("id", "")), p.name
        its.append(d)
    t = hist / "targets.toml"
    return its, (tomllib.loads(t.read_text(encoding="utf-8")) if t.exists() else {})


def load_commits() -> dict[str, dict]:
    """Full hash -> time, subject and size, in the order git prints them (newest first)."""
    out = {}
    for rec in git("log", "--format=%x1e%H%x1f%aI%x1f%s", "--shortstat").split("\x1e")[1:]:
        head, _, stat = rec.partition("\n")
        h, t, s = head.split("\x1f")
        n = lambda word: int(m.group(1)) if (m := re.search(rf"(\d+) {word}", stat)) else 0  # noqa: E731
        out[h] = {"t": t, "subject": s, "files": n("file"), "add": n("insertion"), "rm": n("deletion")}
    return out


def section(text: str, name: str) -> str:
    m = re.search(rf"\*\*{name}\.\*\*\s*(.*?)(?=\n\*\*[A-Z]|\Z)", text, re.S)
    return " ".join(m.group(1).split()) if m else ""


def load_entries() -> list[dict]:
    """Every docs/log entry, with the commit that added it (None while it is still uncommitted)."""
    added = {}
    for rec in git("log", "--diff-filter=A", "--name-only", "--format=%x1e%H", "--", "docs/log").split("\x1e")[1:]:
        h, *files = rec.split()
        for f in files:
            added[Path(f).name] = h
    out = []
    for p in sorted(log.LOG.glob("*.md")):
        if p.name != "README.md":
            text = p.read_text(encoding="utf-8")
            out.append({**log.parse(p), "what": section(text, "What"), "why": section(text, "Why"), "commit": added.get(p.name)})
    return out


def resolve(h: str, commits: dict) -> str | None:
    hits = [k for k in commits if k.startswith(h)]
    return hits[0] if len(hits) == 1 else None


def problems(its: list[dict], commits: dict) -> list[str]:
    bad, ids, seen = [], set(), {}
    for it in its:
        name = it["_file"]
        bad += [f"{name}: missing '{k}'" for k in REQUIRED if not it.get(k)]
        if it.get("status") not in STATUSES:
            bad.append(f"{name}: status must be one of {STATUSES}")
        if it.get("lane") not in LANES:
            bad.append(f"{name}: lane must be one of {LANES}")
        if it["id"] in ids:
            bad.append(f"{name}: id '{it['id']}' used twice")
        ids.add(it["id"])
        it["_full"] = []
        for h in it.get("commits", []):
            full = resolve(h, commits)
            if not full:
                bad.append(f"{name}: commit {h} not found in git")
            elif full in seen:
                bad.append(f"{name}: commit {h} is also listed in {seen[full]}")
            else:
                seen[full] = name
                it["_full"].append(full)
    return bad


# ---- rendering -------------------------------------------------------------------------------------------------


def e(s) -> str:
    return html.escape(str(s), quote=True)


def md(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)


def ref(r: str) -> str:
    """Refs are written relative to docs/ (or repo-rooted for code); anything odd is shown, not linked."""
    if not re.fullmatch(r"https://[^\s\"<>]+|[\w./#%-]+", r):
        return e(r)
    url = r if r.startswith("https://") else ("../" if re.match(r"(src|web|tests|scripts)/", r) else "") + r
    return f'<a href="{e(url)}">{e(r)}</a>'


def label(it: dict) -> str:
    return f"Iteration {it['id']}" if it["id"].isdigit() else it["id"]


def ul(items, cls="") -> str:
    return f'<ul class="{cls}">' + "".join(f"<li>{md(x)}</li>" for x in items) + "</ul>"


def block(title: str, body: str, n: int, open_: bool = False) -> str:
    if not n:
        return ""
    return f'<details{" open" if open_ else ""}><summary>{title} <span class="n">{n}</span></summary>{body}</details>'


def decision(d: dict) -> str:
    r = f' <span class="ref">{ref(d["ref"])}</span>' if d.get("ref") else ""
    why = f'<span class="why">Why: {md(d["why"])}</span>' if d.get("why") else ""
    return f'<li><strong>{md(d["what"])}</strong>{why}{r}</li>'


def entry(en: dict) -> str:
    status = f' <span class="chip">{e(en["status"])}</span>' if en.get("status", "accepted") != "accepted" else ""
    return (
        f'<li><span class="chip k-{e(en.get("kind"))}">{e(en.get("kind"))}</span> <strong>{e(en.get("title"))}</strong> '
        f'<span class="chip lane-{e(en.get("lane"))}">{e(en.get("lane"))}</span>{status}'
        f'<span class="why">{md(en["what"])}</span>'
        + (f'<span class="why">Why: {md(en["why"])}</span>' if en["why"] else "")
        + f'<span class="ref"><a href="log/{e(en["file"])}">{e(en["file"])}</a></span></li>'
    )


def commit_li(h: str, c: dict, unrecorded: bool = False) -> str:
    flag = ' <span class="chip warn">not in any iteration yet</span>' if unrecorded else ""
    return (
        f'<li><code>{h[:7]}</code> <span class="t">{c["t"][11:16]}</span> {e(c["subject"])} '
        f'<span class="diff">+{c["add"]} −{c["rm"]}</span>{flag}</li>'
    )


def when_line(it: dict, cs: list[dict]) -> str:
    bits = []
    ts = sorted(c["t"] for c in cs)
    if ts:
        a, b = ts[0], ts[-1]
        bits.append(a[:10])
        bits.append(a[11:16] if a[:16] == b[:16] else f"{a[11:16]} → {b[11:16]}" if a[:10] == b[:10] else f"{a[11:16]} → {b[:10]} {b[11:16]}")
        bits.append(f"{len(cs)} commit{'s' * (len(cs) != 1)}")
        bits.append(f'+{sum(c["add"] for c in cs)} −{sum(c["rm"] for c in cs)}')
    elif it.get("date"):
        bits.append(str(it["date"]))
    if it.get("tests"):
        bits.append(f'{it["tests"]} offline tests')
    return " · ".join(bits)


def done_card(it: dict, commits: dict, entries: list[dict], extra: list[str]) -> str:
    cs = [commits[h] for h in it["_full"]]
    rows = [commit_li(h, commits[h]) for h in it["_full"]] + [commit_li(h, commits[h], True) for h in extra]
    status = "In progress" if it["status"] == "active" else "Achieved"
    got = it.get("achieved", "")
    return f"""
<article class="it {it['status']}" id="it-{e(it['id'])}">
  <div class="meta"><span class="idn">{e(label(it))}</span><span class="chip lane-{e(it['lane'])}">{e(it['lane'])}</span>{'<span class="chip warn">active</span>' if it['status'] == 'active' else ''}</div>
  <h3>{e(it['title'])}</h3>
  <p class="when">{e(when_line(it, cs + [commits[h] for h in extra]))}</p>
  <div class="goal"><b>Aimed at</b><p>{md(it['aimed_at'])}</p></div>
  {f'<div class="got"><b>{status}</b><p>{md(got)}</p></div>' if got else ''}
  {block('Decided', '<ul class="dec">' + ''.join(decision(d) for d in it.get('decision', [])) + '</ul>', len(it.get('decision', [])), True)}
  {block('Logged as it happened', '<ul class="dec">' + ''.join(entry(x) for x in entries) + '</ul>', len(entries), True)}
  {block('Built and changed', ul(it.get('changes', [])), len(it.get('changes', [])))}
  {block('Found along the way', ul(it.get('found', [])), len(it.get('found', [])))}
  {block('Left open', ul(it.get('open', [])), len(it.get('open', [])))}
  {block('Commits', '<ul class="commits">' + ''.join(rows) + '</ul>', len(rows))}
</article>"""


def planned_card(it: dict) -> str:
    plan = f' · <a href="{e(it["plan"])}">plan</a>' if it.get("plan") and ref(it["plan"]).startswith("<a") else ""
    needs = f' · needs {e(it["needs"])}' if it.get("needs") else ""
    return f"""
<article class="it planned" id="it-{e(it['id'])}">
  <div class="meta"><span class="idn">{e(label(it))}</span><span class="chip lane-{e(it['lane'])}">{e(it['lane'])}</span></div>
  <h3>{e(it['title'])}</h3>
  <p class="when">planned{needs}{plan}</p>
  <div class="goal"><b>Aims at</b><p>{md(it['aimed_at'])}</p></div>
  {block('Done when', ul(it.get('done_when', [])), len(it.get('done_when', [])))}
</article>"""


def ladder(targets: dict, its: list[dict]) -> str:
    rungs = []
    for r in targets.get("rung", []):
        pills = "".join(
            f'<a class="pill {e(it["status"])}" href="#it-{e(it["id"])}" title="{e(it["title"])}">{e(it["id"])}</a>'
            for it in its
            if it.get("serves") == r["key"]
        )
        needs = "".join(f'<span class="chip">{e(n)}</span>' for n in r.get("needs", []))
        rungs.append(
            f'<li class="rung"><div class="rh"><strong>{e(r["name"])}</strong><span class="chip st-{e(r["state"].replace(" ", "-"))}">{e(r["state"])}</span></div>'
            f'<p>{md(r["text"])}</p><div class="rf">{pills}{needs}</div></li>'
        )
    return '<ol class="ladder">' + "".join(rungs) + "</ol>"


CSS = """
:root{--bg:#fafaf9;--fg:#1c1917;--muted:#6b6560;--line:#e4e0da;--card:#fff;--code:#f1efec;--done:#2f6f4e;--active:#b45309;--planned:#8a8580;--main:#1d4ed8;--ui:#7c3aed;--trunk:#57534e;--warn:#b45309}
@media (prefers-color-scheme:dark){:root{--bg:#141311;--fg:#ece8e3;--muted:#9a948d;--line:#2d2a27;--card:#1c1a18;--code:#262320;--done:#6fcf9a;--active:#f59e0b;--planned:#7d776f;--main:#7aa2ff;--ui:#b79bff;--trunk:#b5aea6;--warn:#f59e0b}}
*{box-sizing:border-box}[hidden]{display:none!important}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:56rem;margin:0 auto;padding:32px 16px 64px}
h1{font-size:1.9rem;margin:0 0 4px}h2{font-size:1.25rem;margin:44px 0 12px}h3{font-size:1.15rem;margin:4px 0}
p{margin:6px 0}.sub,.when,.foot{color:var(--muted)}.when{font-size:.88rem;margin:0 0 8px}
a{color:inherit}code{background:var(--code);padding:1px 5px;border-radius:4px;font-size:.88em}
.stats{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0}.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 14px}
.stat b{display:block;font-size:1.4rem;line-height:1.2}.stat span{color:var(--muted);font-size:.82rem}
.chip{display:inline-block;font-size:.72rem;padding:1px 8px;border-radius:99px;border:1px solid var(--line);color:var(--muted);vertical-align:middle;margin-right:4px}
.lane-main{color:var(--main);border-color:currentColor}.lane-ui{color:var(--ui);border-color:currentColor}.lane-trunk,.lane-both,.lane-docs{color:var(--trunk)}
.warn,.st-in-progress{color:var(--warn);border-color:currentColor}.st-reached{color:var(--done);border-color:currentColor}.st-open{color:var(--planned)}
.ladder{list-style:none;padding:0;margin:0;display:grid;gap:0}.rung{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px;position:relative;margin-bottom:22px}
.rung:not(:last-child)::after{content:"▼ needs";position:absolute;left:50%;bottom:-20px;transform:translateX(-50%);font-size:.7rem;color:var(--muted)}
.rh{display:flex;gap:10px;align-items:center;justify-content:space-between}.rf{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.pill{font-size:.78rem;text-decoration:none;padding:1px 9px;border-radius:99px;border:1px solid var(--line)}
.pill.done{color:var(--done);border-color:currentColor}.pill.active{color:var(--active);border-color:currentColor}.pill.planned{color:var(--planned);border-style:dashed}
.tl{margin:8px 0 0 10px;padding-left:26px;border-left:2px solid var(--line)}
.it{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 18px;margin:0 0 18px;position:relative}
.it::before{content:"";position:absolute;left:-36px;top:20px;width:14px;height:14px;border-radius:50%;background:var(--done);border:3px solid var(--bg)}
.it.active::before{background:var(--active)}.it.planned::before{background:var(--bg);border:2px dashed var(--planned);left:-35px}
.it.planned{border-style:dashed;opacity:.92}.it.active{border-color:var(--active)}
.meta{display:flex;gap:8px;align-items:center}.idn{font-weight:700;font-size:.85rem;letter-spacing:.02em}
.goal,.got{margin:8px 0;padding:6px 12px;border-left:3px solid var(--line)}.got{border-color:var(--done)}.it.active .got{border-color:var(--active)}
.goal b,.got b{font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
details{margin:6px 0}summary{cursor:pointer;font-weight:600;font-size:.92rem}.n{color:var(--muted);font-weight:400}
ul{margin:6px 0 6px 0;padding-left:20px}li{margin:3px 0}.dec{list-style:none;padding-left:0}.dec li{padding:6px 0;border-top:1px solid var(--line)}.dec li:first-child{border-top:0}
.why,.ref{display:block;color:var(--muted);font-size:.9rem}.ref{font-size:.8rem}
.commits{list-style:none;padding-left:0;font-size:.88rem}.t,.diff{color:var(--muted);font-size:.8rem}
.lanes{display:grid;grid-template-columns:repeat(auto-fit,minmax(20rem,1fr));gap:0 24px}.lanes h3{margin:0 0 10px}.lanes .it::before{display:none}
.bar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:10px 0}button,input{font:inherit;color:inherit;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:5px 12px}
input{flex:1;min-width:12rem}#ledger{list-style:none;padding:0}#ledger li{padding:8px 0;border-top:1px solid var(--line)}
.k-decision{color:var(--done)}.k-contract{color:var(--ui)}.k-change{color:var(--main)}.foot{margin-top:40px;font-size:.82rem}
@media (max-width:560px){.it{padding:12px 12px}.tl{margin-left:6px;padding-left:20px}.it::before{left:-30px}}
"""

JS = """
const all=document.getElementById('all');
all.onclick=()=>{const d=[...document.querySelectorAll('.it details')],o=d.some(x=>!x.open);d.forEach(x=>x.open=o);all.textContent=o?'Collapse all':'Expand all'};
document.getElementById('q').oninput=ev=>{const q=ev.target.value.toLowerCase();document.querySelectorAll('#ledger li').forEach(li=>li.hidden=!li.dataset.t.includes(q))};
"""


def build(its: list[dict], targets: dict, commits: dict, entries: list[dict]) -> str:
    for it in its:  # callers that skipped problems() still get resolved hashes
        it.setdefault("_full", [f for h in it.get("commits", []) if (f := resolve(h, commits))])
    owner = {h: it for it in its for h in it["_full"]}
    active = next((it for it in its if it["status"] == "active"), None)
    extra = [h for h in commits if h not in owner]
    mine: dict[int, list] = {id(it): [] for it in its}
    loose = []
    for en in entries:
        it = owner.get(en["commit"]) or active
        (mine[id(it)] if it else loose).append(en)

    def first(it):
        return min((commits[h]["t"] for h in it["_full"]), default=str(it.get("date", "9999")) + "T99")

    timeline = sorted((it for it in its if it["status"] != "planned"), key=lambda it: (it["status"] == "active", first(it)))
    planned = [it for it in its if it["status"] == "planned"]

    cards = "".join(done_card(it, commits, mine[id(it)], extra if it is active else []) for it in timeline)
    lanes = ""
    for lane in LANES:
        group = [it for it in planned if it["lane"] == lane]
        if group:
            lanes += f'<div><h3><span class="chip lane-{lane}">{lane}</span> lane</h3>{"".join(planned_card(it) for it in group)}</div>'
    later = targets.get("later", [])

    ledger = []
    for it in timeline:
        rows = [(f"{label(it)}", decision(d), f'{d["what"]} {d.get("why", "")}') for d in it.get("decision", [])]
        rows += [(f"{label(it)}", entry(x), f'{x.get("title")} {x["what"]} {x["why"]}') for x in mine[id(it)]]
        ledger += [f'<li data-t="{e((it["title"] + " " + text).lower())}"><span class="chip">{e(tag)}</span>{body[4:]}' for tag, body, text in rows]
    ledger += [f'<li data-t="{e((x.get("title", "") + " " + x["what"]).lower())}">{entry(x)[4:]}' for x in loose]

    n_dec = len(ledger)
    done = [it for it in its if it["status"] == "done"]
    tests = next((it["tests"] for it in sorted(done, key=first, reverse=True) if it.get("tests")), "–")
    banner = ""
    if extra and not active:
        banner = '<p class="chip warn">Commits in no iteration: ' + e(", ".join(h[:7] for h in extra)) + "</p>"
    stats = [(len(done), "iterations done"), (len(planned), "planned"), (len(commits), "commits"), (n_dec, "decisions & changes logged"), (tests, "offline tests")]
    head = commits and next(iter(commits))[:7]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stepout AI — iteration history</title><style>{CSS}</style></head>
<body><main>
<h1>How Stepout AI got built</h1>
<p class="sub">Every iteration in order: the target it aimed at, what was decided and changed, and what was achieved. Built from <code>docs/history/</code>, <code>git log</code> and <code>docs/log/</code>.</p>
<div class="stats">{"".join(f'<div class="stat"><b>{e(n)}</b><span>{e(t)}</span></div>' for n, t in stats)}</div>
{banner}
<h2>Working backwards from the target</h2>
<p class="sub">Top is where this is going; each step needs the one below it. The pills are the iterations that serve it.</p>
{ladder(targets, its)}
<h2>The iterations, oldest first</h2>
<div class="bar"><button id="all">Expand all</button></div>
<div class="tl">{cards}</div>
<h2>Next</h2>
<div class="lanes">{lanes}</div>
{'<p class="sub"><b>Later:</b> ' + ' · '.join(md(x) for x in later) + '</p>' if later else ''}
<h2>Every decision and change</h2>
<div class="bar"><input id="q" type="search" placeholder="Filter decisions and changes…" aria-label="Filter"></div>
<ul id="ledger">{"".join(ledger)}</ul>
<p class="foot">Generated {dt.datetime.now():%Y-%m-%d %H:%M} from git {e(head or "?")} · regenerate: <code>python scripts/history.py</code> · how to add an iteration: <a href="history/README.md">docs/history/README.md</a></p>
</main><script>{JS}</script></body></html>"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="validate only; write nothing")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    its, targets = load()
    commits = load_commits()
    bad = problems(its, commits)
    for b in bad:
        print(b, file=sys.stderr)
    if bad:
        return 1
    owned = {h for it in its for h in it["_full"]}
    if (n := len([h for h in commits if h not in owned])):
        print(f"note: {n} commit(s) are in no iteration yet; the page shows them under the active one", file=sys.stderr)
    if not a.check:
        a.out.write_text(build(its, targets, commits, load_entries()), encoding="utf-8")
        print(a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
