// Test helper: the invented fixtures in web/fixtures as page state, and the numbers they must show.
import { parseFrame, type Frame, type RunInfo } from './protocol'
import { initial, reducer, type Action, type State } from './store'

const files = import.meta.glob('../fixtures/*.json', { eager: true, import: 'default' }) as Record<string, Record<string, unknown>[]>

export const raw = (name: string) => files[`../fixtures/${name}.json`]
export const chatOf = (name: string) => raw(name)[0].conversation_id as string
export const runOf = (name: string) => raw(name).find((f) => f.type === 'trace')?.run_id as string | undefined
const frames = (name: string, upTo?: number): Frame[] => raw(name).slice(0, upTo).map(parseFrame).filter((f): f is Frame => f !== null)

type Options = {
  upTo?: number // only the first n frames: a Run caught half way
  active?: number // this Run is live, with this budget
  hint?: RunInfo['state'] // what the API says about the Run
  cap?: number // the Run's budget from the API
  extra?: Action[]
}

/** A fixture run through the reducer exactly as the live frames and the API would feed it. */
export function stateOf(name: string, { upTo, active, hint, cap, extra = [] }: Options = {}): State {
  const actions: Action[] = frames(name, upTo).map((frame) => ({ type: 'frame', frame }))
  const run = runOf(name)
  if (run && (hint || cap)) actions.push({ type: 'detail', id: chatOf(name), title: '', messages: [], runs: [{ run_id: run, state: hint ?? 'done', cost_usd: 0, cap_usd: cap ?? 0, steps: null, started_at: '' }] })
  if (run && active !== undefined) {
    actions.push({ type: 'frame', frame: { type: 'status', state: 'running', active: { conversation_id: chatOf(name), run_id: run, cap_usd: active }, queued: [] } })
  }
  return [...actions, ...extra].reduce(reducer, initial)
}

/** What a Run's own events add up to, read straight from the raw JSON (not through the page's code). */
export function expected(name: string) {
  const traces = raw(name).filter((f) => f.type === 'trace')
  const at = (f: Record<string, unknown>) => Date.parse(f.at as string)
  return {
    steps: traces.filter((f) => f.kind === 'step').length,
    cost: traces.reduce((sum, f) => sum + (f.cost_usd as number), 0),
    seconds: Math.floor((at(traces.at(-1)!) - at(traces[0])) / 1000),
  }
}

/** Two decimals from a cent up, four below: how the page writes a total. */
export const dollars = (n: number) => `$${n >= 0.01 ? n.toFixed(2) : n.toFixed(4)}`

/**
 * The same fixture as the page has it after a restart: nothing arrived on the wire; the chat list, the chat's detail and the Run's
 * events were fetched from the API (GET /api/conversations, /api/conversations/{id}, /api/runs/{id}/events).
 */
export function historyOf(name: string, hint: RunInfo['state'] = 'done', cap = 1): State {
  const all = frames(name)
  const messages = all.flatMap((f) => (f.type === 'message' ? [(({ type: _type, ...m }) => m)(f)] : []))
  const traces = all.flatMap((f) => (f.type === 'trace' ? [(({ type: _type, ...e }) => e)(f)] : []))
  const chat = chatOf(name)
  const first = messages[0]
  const run = runOf(name)
  const runs: RunInfo[] = run
    ? [{ run_id: run, state: hint, cost_usd: traces.reduce((n, t) => n + t.cost_usd, 0), cap_usd: cap, steps: traces.filter((t) => t.kind === 'step').length, started_at: traces[0].at }]
    : []
  const actions: Action[] = [
    { type: 'chats', chats: [{ id: chat, title: first.text, updated_at: messages.at(-1)!.at, preview: messages.at(-1)!.text }] },
    { type: 'select', id: chat },
    { type: 'detail', id: chat, title: first.text, messages, runs },
    ...(run ? [{ type: 'events', runId: run, events: traces } as const] : []),
  ]
  return actions.reduce(reducer, initial)
}
