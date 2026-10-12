// The numbers and wording of the run view. Real numbers only: everything here is computed from a Run's own events
// (and its cap), never estimated. Pure functions, so they can be checked against the fixtures.
import type { PlanStep, Trace } from './protocol'
import type { Run } from './store'

/** Spend: two decimals from a cent up ("$0.14"), four below it so a cheap step does not read as "$0.00". */
export const money = (n: number) => `$${n >= 0.01 ? n.toFixed(2) : n.toFixed(4)}`

/** One step's cost, always four decimals (small numbers line up in a column). */
export const stepCost = (n: number) => `$${n.toFixed(4)}`

/** "32 s", "2 m 05 s", "1 h 03 m". Never negative. */
export function elapsedText(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000))
  if (s < 60) return `${s} s`
  if (s < 3600) return `${Math.floor(s / 60)} m ${String(s % 60).padStart(2, '0')} s`
  return `${Math.floor(s / 3600)} h ${String(Math.floor((s % 3600) / 60)).padStart(2, '0')} m`
}

/** A step line in plain words: no scheme on URLs ("browse open luma.com/discover"). */
export const plainLine = (summary: string) => summary.replace(/\bhttps?:\/\//g, '')

export const planOf = (run: Run): PlanStep[] => run.events.findLast((e) => e.kind === 'plan')?.data.steps ?? []
export const stepCount = (run: Run) => run.events.filter((e) => e.kind === 'step').length
export const spent = (run: Run) => run.events.reduce((sum, e) => sum + e.cost_usd, 0)

/** From the Run's first event to its last, or to `now` while it runs. */
export function elapsedMs(run: Run, running: boolean, now: number): number {
  const first = Date.parse(run.events[0]?.at ?? '')
  const last = Date.parse(run.events.at(-1)?.at ?? '')
  return (running ? now : last) - first || 0
}

// Chats saved before the Roles were renamed carry the first ids: they still read as the new names.
const LEGACY_ROLE: Record<string, string> = { direct: 'web_research', files: 'local_file_finder', browser: 'web_browsing', reader: 'local_file_reader' }
const roleId = (role: string) => LEGACY_ROLE[role] ?? role

/** An agent as the User sees it: "local_file_finder" -> "Local File Finder" (the backend's agent_name does the same). */
export const agentName = (role: string) => roleId(role).split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')

export const planProgress = (plan: PlanStep[]) => ({ done: plan.filter((p) => p.status === 'done').length, total: plan.length })

// ---- the browser's pages: saved screenshots (`shot` events) and the live view -------------------------------------------

export type Shot = { path: string; url: string | null; title: string | null }

/** A Run's saved screenshots, in the order they were taken. */
export const shotsOf = (run: Run): Shot[] =>
  run.events.filter((e) => e.kind === 'shot' && e.data.shot).map((e) => ({ path: e.data.shot!, url: e.data.url ?? null, title: e.data.title ?? null }))

/** Has the Web Browsing agent done anything in this Run? Only then is there a page to watch. */
export const hasBrowserStep = (run: Run) => run.events.some((e) => e.kind === 'step' && roleId(e.role) === 'web_browsing')

/** The address of a saved screenshot, or null if the path is not the `<run>/<n>.jpg` the backend writes: never built from anything else. */
export const shotSrc = (path: string): string | null => (/^[0-9a-f]{32}\/\d+\.jpg$/.test(path) ? `/shots/${path}` : null)

/** The live stream of a Run, or null if the id is not the 32 hex characters the backend makes. */
export const liveSrc = (runId: string): string | null => (/^[0-9a-f]{32}$/.test(runId) ? `/live/${runId}` : null)

/** A page's address as a link target: http(s) only. A model-driven page can say anything in a `url`; only a real web address becomes a link. */
export function safeHref(url: string | null): string | null {
  try {
    const u = new URL(url ?? '')
    return u.protocol === 'http:' || u.protocol === 'https:' ? u.href : null
  } catch {
    return null
  }
}

// ---- the work of a Run, as the page draws it: the Orchestrator's delegations are tasks, and every hand action is a tool call ----

export type CallState = 'running' | 'done' | 'refused' | 'repeat' | 'failed'
/** One thing a Role asked a tool to do; or, with `note`, a line about the Run (a retry, what Memory did, a stop). */
export type ToolCall = { id: string; label: string; doing: string; arg: string; request: string | null; result: string | null; state: CallState; cost: number; note: boolean }
export type TaskState = 'running' | 'done' | 'failed' | 'stopped'
/** One plan step handed to a specialist: its goal, who did it on which model, its tool calls, and what it reported back. */
export type Task = { id: string; role: string; goal: string; state: TaskState; model: string | null; startedAt: string; endedAt: string | null; calls: ToolCall[]; result: string | null }

// [while it runs, once it has, what it is] for each kind of hand action
const VERBS: Record<string, [string, string, string]> = {
  web_search: ['Searching the web', 'Searched the web', 'search the web'],
  fetch: ['Reading a page', 'Read a page', 'read a page'],
  'browse.open': ['Opening a page', 'Opened a page', 'open a page'],
  'browse.click': ['Following a link', 'Followed a link', 'follow a link'],
  'browse.more': ['Scrolling the page', 'Scrolled the page', 'scroll the page'],
  'files.list': ['Listing files', 'Listed files', 'list files'],
  'files.count': ['Counting files', 'Counted files', 'count files'],
  'files.find': ['Finding files', 'Found files', 'find files'],
  read_text: ['Reading a file', 'Read a file', 'read a file'],
}

/** "claude-haiku-5-5" -> "haiku"; another provider's "openai/gpt-5-mini" -> "gpt-5-mini". */
export const shortModel = (model: string) => /haiku|sonnet|opus|fable/.exec(model)?.[0] ?? model.split('/').at(-1)!

const after = (text: string, sep: string) => (text.includes(sep) ? text.slice(text.indexOf(sep) + sep.length) : text)
type Act = NonNullable<Trace['data']['action']>
const actKind = (a: Act | undefined) => (a ? (a.kind === 'browse' || a.kind === 'files' ? `${a.kind}.${a.op}` : String(a.kind)) : '')

function argOf(a: Act): string {
  if (a.kind === 'web_search') return String(a.query ?? '')
  if (a.kind === 'browse' && a.op === 'click') return a.link == null ? '' : `link ${a.link}`
  if (a.kind === 'files') return [a.path, a.pattern].filter(Boolean).join(' ')
  return plainLine(String(a.url ?? a.path ?? ''))
}

function callOf(e: Trace): ToolCall {
  const a = e.data.action
  const kind = actKind(a)
  const [doing, did, what] = VERBS[kind] ?? [kind || 'Working', kind || 'Worked', kind || 'act']
  const refused = e.data.verdict === 'refuse' || e.data.verdict === 'ask'
  const fields = a ? Object.fromEntries(Object.entries(a).filter(([k, v]) => k !== 'kind' && v !== null)) : {}
  return {
    id: e.id,
    label: refused ? `Not allowed to ${what}` : did,
    doing,
    arg: a ? argOf(a) : plainLine(e.data.summary ?? ''),
    request: Object.keys(fields).length ? `{${Object.entries(fields).map(([k, v]) => `"${k}": ${JSON.stringify(v)}`).join(", ")}}` : null, // spaced, as assistant-ui shows it
    result: refused ? `Refused: ${after(e.data.summary ?? '', ': ')}` : e.data.repeat ? 'Already done in this task, so not run again.' : null,
    state: refused ? 'refused' : e.data.repeat ? 'repeat' : 'done',
    cost: e.cost_usd,
    note: false,
  }
}

const noteOf = (e: Trace): ToolCall => {
  const label = e.data.summary ?? e.kind
  const failed = e.data.ok === false || e.kind === 'stop' || e.kind === 'error'
  return { id: e.id, label, doing: label, arg: '', request: null, result: null, state: failed ? 'failed' : 'done', cost: e.cost_usd, note: true }
}

/** A Run's events as tasks and tool calls. `running`: the Run is still going, so its newest unanswered call is under way. */
export function workOf(run: Run, running: boolean): { calls: ToolCall[]; tasks: Task[] } {
  const calls: ToolCall[] = [] // the Run's own lines, and any tool the Orchestrator called itself
  const tasks = new Map<string, Task>() // by the Orchestrator step that started each one (a plan starts its first step itself)
  const byId = new Map<string, ToolCall>()
  let opener: Trace | null = null // the Orchestrator's newest plan or delegation
  let last = null as Task | null // the newest task (set in taskFor, so typed by hand: TS does not see the closure assign it)
  const taskFor = (parent: string, role: string, goal?: string) => {
    let t = tasks.get(parent)
    if (!t) {
      const at = run.events.find((x) => x.id === parent)?.at ?? ''
      t = { id: parent, role, goal: goal ?? agentName(role), state: 'running', model: null, startedAt: at, endedAt: null, calls: [], result: null }
      tasks.set(parent, t)
    }
    return (last = t)
  }
  for (const e of run.events) {
    const orchestrating = e.role === 'orchestrator' || e.role === ''
    const kind = actKind(e.data.action)
    if (e.kind === 'step' && e.parent === null && orchestrating) {
      if (kind === 'plan' || kind === 'delegate') opener = e
      else if (kind && kind !== 'answer') calls.push(callOf(e)) // a tool the Orchestrator asked for itself (refused: it has none)
    } else if (e.kind === 'plan' && opener) {
      const step = e.data.steps?.find((s) => s.status === 'running') // only one step runs at a time: the one just started
      if (step && !tasks.has(opener.id)) taskFor(opener.id, step.role, step.goal)
    } else if (e.kind === 'step' && e.parent) {
      const t = taskFor(e.parent, e.role)
      t.model ??= e.data.model ? shortModel(e.data.model) : null
      if (kind === 'answer' || e.data.summary === 'answer') continue // what it found comes back as the task's result
      const c = callOf(e)
      t.calls.push(c)
      byId.set(c.id, c)
    } else if (e.kind === 'result' && e.parent && byId.has(e.parent)) {
      byId.get(e.parent)!.result = after(e.data.summary ?? '', ': ')
    } else if ((e.kind === 'return' || e.kind === 'stop') && e.parent && tasks.has(e.parent)) {
      const t = tasks.get(e.parent)!
      if (t.state === 'stopped') continue // its "failed: Stopped by you." return adds nothing to the stop
      t.state = e.kind === 'stop' ? 'stopped' : e.data.ok === false ? 'failed' : 'done'
      t.result = e.kind === 'stop' ? (e.data.summary ?? '') : after(e.data.summary ?? '', ': ')
      t.endedAt = e.at
    } else if (e.kind === 'stop' && last?.state === 'stopped') {
      continue // the Orchestrator passing on the stop its task already shows
    } else if (e.kind === 'retry' || e.kind === 'memory' || e.kind === 'stop' || e.kind === 'error') {
      ;(!orchestrating && last?.state === 'running' ? last.calls : calls).push(noteOf(e)) // a specialist's wait belongs to its task
    }
  }
  const list = [...tasks.values()]
  for (const t of list) {
    if (t.state === 'running' && !running) t.state = 'stopped' // the Run ended before this task reported back
    const newest = t.calls.findLast((c) => !c.note)
    if (running && t.state === 'running' && newest?.state === 'done' && newest.result === null) newest.state = 'running'
  }
  return { calls, tasks: list }
}
