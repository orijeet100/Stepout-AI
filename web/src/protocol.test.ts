import { describe, expect, it } from 'vitest'
import { parseDetail, parseFrame, parseMessage, splitCostFooter } from './protocol'

const base = { id: 'a'.repeat(32), conversation_id: 'c'.repeat(32), at: '2026-10-01T09:00:00.000Z' }

describe('parseFrame', () => {
  it('reads each v1 frame', () => {
    expect(parseFrame({ type: 'hello', v: 1 })).toEqual({ type: 'hello', v: 1 })
    expect(parseFrame({ type: 'message', ...base, role: 'user', text: 'hi', run_id: null, cost_usd: null })?.type).toBe('message')
    const trace = parseFrame({ type: 'trace', ...base, run_id: 'r'.repeat(32), parent: null, kind: 'plan', role: 'orchestrator', cost_usd: 0, data: { steps: [{ role: 'browser', goal: 'g', status: 'running' }] } })
    expect(trace).toMatchObject({ type: 'trace', kind: 'plan', data: { steps: [{ status: 'running' }] } })
    expect(parseFrame({ type: 'status', state: 'running', active: { conversation_id: 'c', run_id: 'r', cap_usd: 1 }, queued: [{ conversation_id: 'd' }] })).toMatchObject({
      state: 'running',
      queued: [{ conversation_id: 'd' }],
    })
  })

  it('ignores what it does not know and what is malformed', () => {
    expect(parseFrame({ type: 'approval', id: 1 })).toBeNull() // placeholder frames, newer kinds, v0 frames
    expect(parseFrame({ role: 'assistant', text: 'v0 frame' })).toBeNull()
    expect(parseFrame({ type: 'message', ...base, role: 'robot', text: 'x' })).toBeNull()
    expect(parseFrame({ type: 'message', id: 5, text: 'x' })).toBeNull()
    expect(parseFrame({ type: 'status', state: 'sleeping' })).toBeNull()
    expect(parseFrame('text')).toBeNull()
    expect(parseFrame(null)).toBeNull()
  })

  it('drops unknown fields and coerces bad optional ones instead of trusting them', () => {
    const t = parseFrame({ type: 'trace', ...base, run_id: 'r', kind: 'step', role: 7, cost_usd: 'free', data: { summary: 3, verdict: 'maybe', extra: { x: 1 } }, surprise: true })
    expect(t).toMatchObject({ role: '', cost_usd: 0, parent: null, data: { summary: undefined, verdict: undefined } })
    expect(t).not.toHaveProperty('surprise')
  })
})

describe('cost footer shim', () => {
  it('strips the footer and keeps the cost until the backend drops it', () => {
    expect(splitCostFooter('Done.\n\n(cost: $0.0932)')).toEqual({ text: 'Done.', cost: 0.0932 })
    expect(splitCostFooter('No footer')).toEqual({ text: 'No footer', cost: null })
    const m = parseMessage({ ...base, role: 'assistant', text: 'Hi\n\n(cost: $0.02)', run_id: 'r' })
    expect(m).toMatchObject({ text: 'Hi', cost_usd: 0.02 })
  })

  it('prefers cost_usd from the frame, and never strips a user message', () => {
    expect(parseMessage({ ...base, role: 'assistant', text: 'Hi\n\n(cost: $0.02)', cost_usd: 0.5 })?.cost_usd).toBe(0.5)
    expect(parseMessage({ ...base, role: 'user', text: 'a\n\n(cost: $1.00)' })?.text).toBe('a\n\n(cost: $1.00)')
  })
})

describe('parseDetail', () => {
  it('keeps valid messages and runs, skips junk', () => {
    const d = parseDetail({
      id: 'c1',
      title: 'T',
      messages: [{ ...base, role: 'user', text: 'x' }, { nope: 1 }],
      runs: [{ run_id: 'r1', state: 'stopped', cost_usd: 0.1, cap_usd: 1, started_at: base.at }, { state: 'done' }],
    })
    expect(d?.messages).toHaveLength(1)
    expect(d?.runs).toEqual([{ run_id: 'r1', state: 'stopped', cost_usd: 0.1, cap_usd: 1, steps: null, started_at: base.at }])
    expect(parseDetail({ title: 'no id' })).toBeNull()
  })
})
