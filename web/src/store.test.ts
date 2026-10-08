import { describe, expect, it } from 'vitest'
import type { Frame, Message, Trace } from './protocol'
import { chatList, initial, plain, reducer, runCap, runState, timeline, type Action, type State } from './store'

const C = 'c'.repeat(32)
const t = (s: number) => `2026-10-01T09:00:${String(s).padStart(2, '0')}.000Z`
const msg = (id: string, role: Message['role'], text: string, s: number, run_id: string | null = null, conv = C): Frame => ({
  type: 'message', id, conversation_id: conv, role, text, run_id, cost_usd: null, at: t(s),
})
const trace = (id: string, run: string, kind: string, s: number, data: Trace['data'] = {}, conv = C): Frame => ({
  type: 'trace', id, conversation_id: conv, run_id: run, parent: null, kind, role: 'browser', data, cost_usd: 0, at: t(s),
})
const run = (state: State, ...actions: Action[]) => actions.reduce(reducer, state)
const frames = (...fs: Frame[]): Action[] => fs.map((frame) => ({ type: 'frame', frame }))

describe('frames', () => {
  it('a message for an unknown chat creates it, titled by the first request cut to 60 characters', () => {
    const s = run(initial, ...frames(msg('m1', 'user', 'x'.repeat(100), 1)))
    expect(s.chats[C].title).toHaveLength(60)
    expect(s.chats[C].preview).toHaveLength(80)
    expect(s.messages[C]).toHaveLength(1)
  })

  it('the same frame twice changes nothing (reconnects replay)', () => {
    const once = run(initial, ...frames(msg('m1', 'user', 'hi', 1), trace('e1', 'r1', 'step', 2)))
    const twice = run(once, ...frames(msg('m1', 'user', 'hi', 1), trace('e1', 'r1', 'step', 2)))
    expect(twice.messages).toEqual(once.messages)
    expect(twice.runs.r1.events).toHaveLength(1)
  })

  it('events keep their time order even when they arrive out of order', () => {
    const s = run(initial, ...frames(trace('e2', 'r1', 'step', 5), trace('e1', 'r1', 'plan', 2)))
    expect(s.runs.r1.events.map((e) => e.id)).toEqual(['e1', 'e2'])
    expect(s.runs.r1.startedAt).toBe(t(2))
  })
})

describe('what each chat is doing', () => {
  it('shows running and queued from the status frame, newest chat first', () => {
    const D = 'd'.repeat(32)
    const s = run(
      initial,
      ...frames(msg('m1', 'user', 'first', 1), msg('m2', 'user', 'second', 9, null, D)),
      { type: 'frame', frame: { type: 'status', state: 'running', active: { conversation_id: C, run_id: 'r1', cap_usd: 1 }, queued: [{ conversation_id: D }] } },
    )
    expect(chatList(s).map((c) => [c.id === C ? 'C' : 'D', c.state])).toEqual([['D', 'queued'], ['C', 'running']])
  })

  it('run state: running while active, stopped after a stop event, done otherwise', () => {
    const base = run(initial, ...frames(trace('e1', 'r1', 'step', 1)))
    expect(runState(base, base.runs.r1)).toBe('done')
    const live = run(base, { type: 'frame', frame: { type: 'status', state: 'running', active: { conversation_id: C, run_id: 'r1', cap_usd: 1 }, queued: [] } })
    expect(runState(live, live.runs.r1)).toBe('running')
    const stopped = run(base, ...frames(trace('e2', 'r1', 'stop', 3, { summary: 'Stopped by you.' })))
    expect(runState(stopped, stopped.runs.r1)).toBe('stopped')
  })
})

describe('run state and cap', () => {
  const live = (run: string, cap: number): Action => ({ type: 'frame', frame: { type: 'status', state: 'running', active: { conversation_id: C, run_id: run, cap_usd: cap }, queued: [] } })
  const detail = (state: 'running' | 'done' | 'stopped' | 'failed', cap: number): Action => ({ type: 'detail', id: C, title: '', messages: [], runs: [{ run_id: 'r1', state, cost_usd: 0, cap_usd: cap, started_at: t(1) }] })

  it('the two stop texts of the Runner: by you, or the budget used up', () => {
    const stopped = (text: string) => run(initial, ...frames(trace('e1', 'r1', 'stop', 3, { summary: text })))
    const byYou = stopped('Stopped by you.')
    const budget = stopped('Stopped: the $1.00 budget for this run is used up.')
    expect(runState(byYou, byYou.runs.r1)).toBe('stopped')
    expect(runState(budget, budget.runs.r1)).toBe('overbudget')
  })

  it('failed and stopped come from the API when the events do not say', () => {
    const failed = run(initial, ...frames(trace('e1', 'r1', 'step', 2)), detail('failed', 1))
    expect(runState(failed, failed.runs.r1)).toBe('failed')
    const stopped = run(initial, ...frames(trace('e1', 'r1', 'step', 2)), detail('stopped', 1))
    expect(runState(stopped, stopped.runs.r1)).toBe('stopped')
  })

  it('the cap is the status frame while the Run runs, the API after, and null when there is none (never a guess)', () => {
    const s = run(initial, ...frames(trace('e1', 'r1', 'step', 2)))
    expect(runCap(s, s.runs.r1)).toBeNull()
    const running = run(s, live('r1', 1))
    expect(runCap(running, running.runs.r1)).toBe(1)
    const ended = run(s, detail('done', 2.5))
    expect(runCap(ended, ended.runs.r1)).toBe(2.5)
    const noBudget = run(s, detail('done', 0)) // a cap of 0 is "no budget": nothing to draw a meter against
    expect(runCap(noBudget, noBudget.runs.r1)).toBeNull()
  })
})

describe('timeline', () => {
  it('reads your message, its run, then the reply', () => {
    const s = run(initial, ...frames(msg('u1', 'user', 'q', 1), trace('e1', 'r1', 'plan', 2), trace('e2', 'r1', 'step', 3), msg('a1', 'assistant', 'answer', 4, 'r1')))
    expect(timeline(s, C).map((i) => (i.kind === 'run' ? 'run' : i.message.id))).toEqual(['u1', 'run', 'a1'])
  })

  it('a message queued behind a busy run sits after the first reply, not before it', () => {
    const s = run(
      initial,
      ...frames(
        msg('u1', 'user', 'first', 1),
        trace('e1', 'r1', 'plan', 2),
        msg('u2', 'user', 'queued while r1 runs', 5), // arrives early
        trace('e2', 'r1', 'step', 6),
        msg('a1', 'assistant', 'first answer', 8, 'r1'),
        trace('e3', 'r2', 'plan', 9),
        msg('a2', 'assistant', 'second answer', 11, 'r2'),
      ),
    )
    expect(timeline(s, C).map((i) => (i.kind === 'run' ? i.run.id : i.message.id))).toEqual(['u1', 'r1', 'a1', 'u2', 'r2', 'a2'])
  })

  it('a reply with no run (a decline) is just a message', () => {
    const s = run(initial, ...frames(msg('u1', 'user', 'order a pizza', 1), msg('a1', 'assistant', 'I cannot order food.', 2)))
    expect(timeline(s, C).map((i) => (i.kind === 'message' ? i.message.role : 'run'))).toEqual(['user', 'assistant'])
  })
})

describe('plain', () => {
  it('turns a markdown reply into one plain line for the chat list', () => {
    expect(plain('There are **42** PDFs in `D:\\x`, see [the list](https://a.example).')).toBe('There are 42 PDFs in D:\\x, see the list.')
    expect(plain('Here are three:\n\n1. **A** — one\n2. B — two\n- c')).toBe('Here are three: A — one B — two c')
    expect(plain('# Title\n> quoted')).toBe('Title quoted')
    expect(plain('keeps snake_case_names')).toBe('keeps snake_case_names')
  })
})

describe('api responses', () => {
  it('a chat list keeps a chat that only exists locally and selects the first one when nothing is selected', () => {
    const local = run(initial, { type: 'created', id: 'new'.padEnd(32, '0'), at: t(30) })
    const s = reducer(local, { type: 'chats', chats: [{ id: C, title: 'Old', updated_at: t(1), preview: '' }] })
    expect(Object.keys(s.chats)).toHaveLength(2)
    expect(s.selected).toBe(local.selected) // still the new one
    const fresh = reducer(initial, { type: 'chats', chats: [{ id: C, title: 'Old', updated_at: t(1), preview: '' }] })
    expect(fresh.selected).toBe(C)
  })

  it('a message that arrived live and is then read back from history is one message (they share an id)', () => {
    const live = run(initial, ...frames(msg('m1', 'user', 'hello', 5), msg('m2', 'assistant', 'hi', 7)))
    const saved = (id: string, role: Message['role'], text: string, s: number): Message => ({ id, conversation_id: C, role, text, run_id: null, cost_usd: null, at: t(s) })
    const loaded = reducer(live, { type: 'detail', id: C, title: 'T', messages: [saved('m1', 'user', 'hello', 5), saved('m2', 'assistant', 'hi', 7)], runs: [] })
    expect(loaded.messages[C].map((m) => m.id)).toEqual(['m1', 'm2'])
  })

  it('loading a chat merges with what arrived live instead of replacing it', () => {
    const live = run(initial, ...frames(msg('m2', 'user', 'live', 5)))
    const loaded = reducer(live, { type: 'detail', id: C, title: 'T', messages: [{ id: 'm1', conversation_id: C, role: 'user', text: 'old', run_id: null, cost_usd: null, at: t(1) }], runs: [] })
    expect(loaded.messages[C].map((m) => m.id)).toEqual(['m1', 'm2'])
    expect(loaded.chats[C].title).toBe('T')
  })
})
