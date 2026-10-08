// Page state: one reducer fed by WebSocket frames and API responses. No state library (U2 rule).
import type { Chat, Frame, Message, RunInfo, Status, Trace } from './protocol'

export type Run = {
  id: string
  conversationId: string
  startedAt: string
  hint: RunInfo['state'] | null // what the API said when the chat was loaded; live state comes from `status`
  events: Trace[]
}

export type State = {
  conn: 'connecting' | 'open' | 'closed'
  attempt: number // reconnect attempts since the last open connection
  chats: Record<string, Chat>
  selected: string | null
  messages: Record<string, Message[]> // by conversation id, oldest first
  runs: Record<string, Run>
  status: Status
  error: string | null
}

export const initial: State = {
  conn: 'connecting',
  attempt: 0,
  chats: {},
  selected: null,
  messages: {},
  runs: {},
  status: { state: 'idle', active: null, queued: [] },
  error: null,
}

export type Action =
  | { type: 'conn'; conn: State['conn']; attempt?: number }
  | { type: 'frame'; frame: Frame }
  | { type: 'chats'; chats: Chat[] }
  | { type: 'detail'; id: string; title: string; messages: Message[]; runs: RunInfo[] }
  | { type: 'events'; runId: string; events: Trace[] }
  | { type: 'select'; id: string | null }
  | { type: 'created'; id: string; at: string }
  | { type: 'error'; error: string | null }

const ms = (iso: string) => Date.parse(iso) || 0

function mergeById<T extends { id: string; at: string }>(list: T[], items: T[]): T[] {
  const byId = new Map(list.map((x) => [x.id, x]))
  for (const x of items) byId.set(x.id, x)
  return [...byId.values()].sort((a, b) => ms(a.at) - ms(b.at)) // stable: ties keep arrival order
}

const cut = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1) + '…' : s)

/** A one-line plain-text version of a reply for the chat list: no **bold**, `code`, [links](…) or list markers. */
export const plain = (md: string) =>
  md
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/^\s*(?:[#>]+|\d+\.|[-*])\s+/gm, '')
    .replace(/[*`]+/g, '')
    .replace(/\s+/g, ' ')
    .trim()

/** A chat the page has not listed yet (it just arrived on the wire): make an entry for it. */
function touch(chats: State['chats'], id: string, at: string, message?: Message): State['chats'] {
  const old = chats[id] ?? { id, title: '', updated_at: at, preview: '' }
  const newer = ms(at) >= ms(old.updated_at)
  return {
    ...chats,
    [id]: {
      ...old,
      title: old.title || (message?.role === 'user' ? cut(message.text, 60) : ''),
      updated_at: newer ? at : old.updated_at,
      preview: message && newer ? cut(message.text, 80) : old.preview,
    },
  }
}

function addEvents(runs: State['runs'], events: Trace[]): State['runs'] {
  const out = { ...runs }
  for (const e of events) {
    const run = out[e.run_id] ?? { id: e.run_id, conversationId: e.conversation_id, startedAt: e.at, hint: null, events: [] }
    const merged = mergeById(run.events, [e])
    out[e.run_id] = { ...run, events: merged, startedAt: merged[0].at }
  }
  return out
}

export function reducer(s: State, a: Action): State {
  switch (a.type) {
    case 'conn':
      return { ...s, conn: a.conn, attempt: a.attempt ?? (a.conn === 'open' ? 0 : s.attempt) }
    case 'frame': {
      const f = a.frame
      if (f.type === 'message') {
        const { type: _type, ...m } = f
        return {
          ...s,
          chats: touch(s.chats, m.conversation_id, m.at, m),
          messages: { ...s.messages, [m.conversation_id]: mergeById(s.messages[m.conversation_id] ?? [], [m]) },
        }
      }
      if (f.type === 'trace') {
        const { type: _type, ...e } = f
        return { ...s, chats: touch(s.chats, e.conversation_id, e.at), runs: addEvents(s.runs, [e]) }
      }
      if (f.type === 'status') return { ...s, status: { state: f.state, active: f.active, queued: f.queued } }
      return s
    }
    case 'chats': {
      // Keep a chat that only exists locally (just created, or learned from a live frame) if the list lacks it.
      const listed = Object.fromEntries(a.chats.map((c) => [c.id, c]))
      const kept = Object.fromEntries(Object.entries(s.chats).filter(([id]) => !(id in listed)))
      const selected = s.selected && (s.selected in listed || s.selected in kept) ? s.selected : (a.chats[0]?.id ?? null)
      return { ...s, chats: { ...kept, ...listed }, selected }
    }
    case 'detail': {
      const runs = { ...s.runs }
      for (const r of a.runs) {
        const old = runs[r.run_id]
        runs[r.run_id] = { id: r.run_id, conversationId: a.id, startedAt: old?.events[0]?.at ?? r.started_at, hint: r.state, events: old?.events ?? [] }
      }
      return {
        ...s,
        runs,
        chats: { ...s.chats, [a.id]: { ...(s.chats[a.id] ?? { id: a.id, updated_at: '', preview: '' }), title: a.title || s.chats[a.id]?.title || '' } },
        messages: { ...s.messages, [a.id]: mergeById(s.messages[a.id] ?? [], a.messages) },
      }
    }
    case 'events':
      return { ...s, runs: addEvents(s.runs, a.events) }
    case 'select':
      return { ...s, selected: a.id }
    case 'created':
      return { ...s, selected: a.id, chats: { ...s.chats, [a.id]: { id: a.id, title: '', updated_at: a.at, preview: '' } } }
    case 'error':
      return { ...s, error: a.error }
  }
}

// ---- selectors ----------------------------------------------------------------------------------------------

export type ChatState = 'idle' | 'queued' | 'running'
export type RunState = 'running' | 'done' | 'stopped' | 'failed'

/** Chats newest first, each with what it is doing now (one Run at a time across all chats). */
export function chatList(s: State): (Chat & { state: ChatState })[] {
  const queued = new Set(s.status.queued.map((q) => q.conversation_id))
  return Object.values(s.chats)
    .sort((x, y) => ms(y.updated_at) - ms(x.updated_at))
    .map((c) => ({ ...c, state: s.status.active?.conversation_id === c.id ? 'running' : queued.has(c.id) ? 'queued' : 'idle' }))
}

export function runState(s: State, r: Run): RunState {
  if (s.status.active?.run_id === r.id) return 'running'
  if (r.events.some((e) => e.kind === 'stop')) return 'stopped'
  return r.hint === 'failed' ? 'failed' : 'done'
}

export type Item = { kind: 'message'; message: Message } | { kind: 'run'; run: Run }

/**
 * A chat in reading order: your message, then its Run, then the reply. Messages sent while a Run was busy
 * arrive early, so a reply sorts right after its own Run instead of after the next queued message.
 */
export function timeline(s: State, chatId: string): Item[] {
  const rank = { user: 0, run: 1, assistant: 2 }
  const rows: { key: number; rank: number; item: Item }[] = []
  for (const message of s.messages[chatId] ?? []) {
    const run = message.run_id ? s.runs[message.run_id] : undefined
    const key = message.role === 'assistant' && run?.events.length ? ms(run.startedAt) + 0.5 : ms(message.at)
    rows.push({ key, rank: rank[message.role], item: { kind: 'message', message } })
  }
  for (const run of Object.values(s.runs)) {
    if (run.conversationId === chatId && run.events.length) rows.push({ key: ms(run.startedAt), rank: rank.run, item: { kind: 'run', run } })
  }
  return rows.sort((x, y) => x.key - y.key || x.rank - y.rank).map((r) => r.item)
}
