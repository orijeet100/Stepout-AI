// The wire shapes of docs/ui-contract.md (v1). Frames and API bodies cross a trust boundary (their text is model
// output), so everything is checked field by field here and nothing downstream sees an unchecked value.
// Unknown frame types and unknown fields are ignored on purpose: additive changes to the contract are free.

export type Verdict = 'allow' | 'refuse' | 'ask'
export type PlanStatus = 'pending' | 'running' | 'done' | 'failed'
export type PlanStep = { role: string; goal: string; status: PlanStatus }

export type TraceData = {
  summary?: string
  steps?: PlanStep[]
  verdict?: Verdict
  ok?: boolean
  shot?: string
  url?: string
  title?: string
  text?: string // `delta`: the next words of the reply
  reset?: boolean // `delta`: drop what came so far
  action?: Record<string, string | number | boolean | null> // `step`: what the Role asked for (`kind` and its plain fields; nested values are dropped)
  model?: string // `step`: the model that made the call
  repeat?: boolean // `step`: asked again for something it already had, so not run again
}

export type Message = {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  text: string
  run_id: string | null
  cost_usd: number | null
  at: string
}

export type Trace = {
  id: string
  conversation_id: string
  run_id: string
  parent: string | null
  kind: string
  role: string
  data: TraceData
  cost_usd: number
  at: string
}

export type Status = {
  state: 'idle' | 'running'
  active: { conversation_id: string; run_id: string; cap_usd: number } | null
  queued: { conversation_id: string }[]
}

export type Frame =
  | { type: 'hello'; v: number; machine: string }
  | ({ type: 'message' } & Message)
  | ({ type: 'trace' } & Trace)
  | ({ type: 'status' } & Status)

export type Chat = { id: string; title: string; updated_at: string; preview: string }
export type MemoryEntry = { id: string; kind: 'persona' | 'fact' | 'history'; text: string; source: string }
export type RunInfo = {
  run_id: string
  state: 'running' | 'done' | 'stopped' | 'failed'
  cost_usd: number
  cap_usd: number
  steps: number | null // `step` events so far; 0 for a Run that has just started and has no events at all (null: the backend did not say)
  started_at: string
}
export type Detail = { id: string; title: string; messages: Message[]; runs: RunInfo[] }

const isStr = (v: unknown): v is string => typeof v === 'string'
const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const isRec = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)
const optStr = (v: unknown) => (isStr(v) ? v : undefined)

// Replies saved before the cost footer was dropped still end with "\n\n(cost: $0.0932)": the page strips it and reads the cost from it.
const FOOTER = /\n\n\(cost: \$(\d+(?:\.\d+)?)\)\s*$/
export function splitCostFooter(text: string): { text: string; cost: number | null } {
  const m = FOOTER.exec(text)
  return m ? { text: text.slice(0, m.index), cost: Number(m[1]) } : { text, cost: null }
}

export function parseMessage(v: unknown): Message | null {
  if (!isRec(v) || !isStr(v.id) || !isStr(v.conversation_id) || !isStr(v.text) || !isStr(v.at)) return null
  if (v.role !== 'user' && v.role !== 'assistant') return null
  const { text, cost } = v.role === 'assistant' ? splitCostFooter(v.text) : { text: v.text, cost: null }
  return {
    id: v.id,
    conversation_id: v.conversation_id,
    role: v.role,
    text,
    run_id: isStr(v.run_id) ? v.run_id : null,
    cost_usd: isNum(v.cost_usd) ? v.cost_usd : cost,
    at: v.at,
  }
}

function parseSteps(v: unknown): PlanStep[] | undefined {
  if (!Array.isArray(v)) return undefined
  const ok = (s: unknown): s is Record<string, unknown> & { role: string; goal: string } => isRec(s) && isStr(s.role) && isStr(s.goal)
  return v.filter(ok).map((s) => ({
    role: s.role,
    goal: s.goal,
    status: s.status === 'running' || s.status === 'done' || s.status === 'failed' ? s.status : 'pending',
  }))
}

type Plain = string | number | boolean | null
const isPlain = (v: unknown): v is Plain => v === null || isStr(v) || isNum(v) || typeof v === 'boolean'
const parseAction = (v: unknown) => (isRec(v) && isStr(v.kind) ? Object.fromEntries(Object.entries(v).filter(([, x]) => isPlain(x))) as Record<string, Plain> : undefined)

function parseData(v: unknown): TraceData {
  if (!isRec(v)) return {}
  return {
    summary: optStr(v.summary),
    steps: parseSteps(v.steps),
    verdict: v.verdict === 'allow' || v.verdict === 'refuse' || v.verdict === 'ask' ? v.verdict : undefined,
    ok: typeof v.ok === 'boolean' ? v.ok : undefined,
    shot: optStr(v.shot),
    url: optStr(v.url),
    title: optStr(v.title),
    text: optStr(v.text),
    reset: v.reset === true ? true : undefined,
    action: parseAction(v.action),
    model: optStr(v.model),
    repeat: v.repeat === true ? true : undefined,
  }
}

export function parseTrace(v: unknown): Trace | null {
  if (!isRec(v) || !isStr(v.id) || !isStr(v.conversation_id) || !isStr(v.run_id) || !isStr(v.kind) || !isStr(v.at)) return null
  return {
    id: v.id,
    conversation_id: v.conversation_id,
    run_id: v.run_id,
    parent: isStr(v.parent) ? v.parent : null,
    kind: v.kind,
    role: isStr(v.role) ? v.role : '',
    data: parseData(v.data),
    cost_usd: isNum(v.cost_usd) ? v.cost_usd : 0,
    at: v.at,
  }
}

export function parseStatus(v: unknown): Status | null {
  if (!isRec(v) || (v.state !== 'idle' && v.state !== 'running')) return null
  const a = v.active
  const active =
    isRec(a) && isStr(a.conversation_id) && isStr(a.run_id)
      ? { conversation_id: a.conversation_id, run_id: a.run_id, cap_usd: isNum(a.cap_usd) ? a.cap_usd : 0 }
      : null
  const queued = Array.isArray(v.queued)
    ? v.queued.filter((q): q is { conversation_id: string } => isRec(q) && isStr(q.conversation_id)).map((q) => ({ conversation_id: q.conversation_id }))
    : []
  return { state: v.state, active, queued }
}

/** One WebSocket text frame (already JSON-parsed) to a typed frame, or null if it is malformed or not ours. */
export function parseFrame(v: unknown): Frame | null {
  if (!isRec(v)) return null
  switch (v.type) {
    case 'hello':
      return isNum(v.v) ? { type: 'hello', v: v.v, machine: isStr(v.machine) ? v.machine : '' } : null
    case 'message': {
      const m = parseMessage(v)
      return m && { type: 'message', ...m }
    }
    case 'trace': {
      const t = parseTrace(v)
      return t && { type: 'trace', ...t }
    }
    case 'status': {
      const s = parseStatus(v)
      return s && { type: 'status', ...s }
    }
    default:
      return null // v0 frames, placeholders (question, approval) and anything newer: ignored
  }
}

export function parseChats(v: unknown): Chat[] {
  if (!Array.isArray(v)) return []
  return v
    .filter((c): c is Record<string, unknown> => isRec(c) && isStr(c.id))
    .map((c) => ({ id: c.id as string, title: optStr(c.title) ?? '', updated_at: optStr(c.updated_at) ?? '', preview: optStr(c.preview) ?? '' }))
}

export function parseDetail(v: unknown): Detail | null {
  if (!isRec(v) || !isStr(v.id)) return null
  const runs = Array.isArray(v.runs) ? v.runs : []
  return {
    id: v.id,
    title: optStr(v.title) ?? '',
    messages: (Array.isArray(v.messages) ? v.messages : []).map(parseMessage).filter((m): m is Message => m !== null),
    runs: runs
      .filter((r): r is Record<string, unknown> => isRec(r) && isStr(r.run_id))
      .map((r) => ({
        run_id: r.run_id as string,
        state: r.state === 'running' || r.state === 'stopped' || r.state === 'failed' ? r.state : 'done',
        cost_usd: isNum(r.cost_usd) ? r.cost_usd : 0,
        cap_usd: isNum(r.cap_usd) ? r.cap_usd : 0,
        steps: isNum(r.steps) ? r.steps : null,
        started_at: optStr(r.started_at) ?? '',
      })),
  }
}

/** GET /api/memory: what the assistant keeps about the User. Anything that is not a well-formed entry is left out. */
export const parseMemory = (v: unknown): MemoryEntry[] =>
  Array.isArray(v)
    ? v
        .filter((e): e is Record<string, unknown> => isRec(e) && isStr(e.id) && isStr(e.text) && (e.kind === 'persona' || e.kind === 'fact' || e.kind === 'history'))
        .map((e) => ({ id: e.id as string, kind: e.kind as MemoryEntry['kind'], text: e.text as string, source: optStr(e.source) ?? '' }))
    : []

export const parseEvents = (v: unknown): Trace[] => (Array.isArray(v) ? v.map(parseTrace).filter((t): t is Trace => t !== null) : [])
