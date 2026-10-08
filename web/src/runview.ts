// The numbers and wording of the run view. Real numbers only: everything here is computed from a Run's own events
// (and its cap), never estimated. Pure functions, so they can be checked against the fixtures.
import type { PlanStep } from './protocol'
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

export const planProgress = (plan: PlanStep[]) => ({ done: plan.filter((p) => p.status === 'done').length, total: plan.length })

// ---- the browser's pages: saved screenshots (`shot` events) and the live view -------------------------------------------

export type Shot = { path: string; url: string | null; title: string | null }

/** A Run's saved screenshots, in the order they were taken. */
export const shotsOf = (run: Run): Shot[] =>
  run.events.filter((e) => e.kind === 'shot' && e.data.shot).map((e) => ({ path: e.data.shot!, url: e.data.url ?? null, title: e.data.title ?? null }))

/** Has the Browser agent done anything in this Run? Only then is there a page to watch. */
export const hasBrowserStep = (run: Run) => run.events.some((e) => e.kind === 'step' && e.role === 'browser')

/** The address of a saved screenshot, or null if the path is not the `<run>/<n>.jpg` the backend writes: never built from anything else. */
export const shotSrc = (path: string): string | null => (/^[0-9a-f]{32}\/\d+\.jpg$/.test(path) ? `/shots/${path}` : null)

/** A page's address as a link target: http(s) only. A model-driven page can say anything in a `url`; only a real web address becomes a link. */
export function safeHref(url: string | null): string | null {
  try {
    const u = new URL(url ?? '')
    return u.protocol === 'http:' || u.protocol === 'https:' ? u.href : null
  } catch {
    return null
  }
}
