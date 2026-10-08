import { describe, expect, it } from 'vitest'
import { elapsedMs, elapsedText, money, plainLine, planProgress, stepCost } from './runview'
import type { Run } from './store'

const ev = (at: string) => ({ id: at, conversation_id: 'c', run_id: 'r', parent: null, kind: 'step', role: 'x', data: {}, cost_usd: 0, at })
const run = (...ats: string[]): Run => ({ id: 'r', conversationId: 'c', startedAt: ats[0], hint: null, cap: null, events: ats.map(ev) })

describe('run view numbers', () => {
  it('money: two decimals from a cent up, four below, so a cheap step is not "$0.00"', () => {
    expect([0.0932, 1, 1.0028, 0.01, 0.0098, 0.0004, 0].map(money)).toEqual(['$0.09', '$1.00', '$1.00', '$0.01', '$0.0098', '$0.0004', '$0.0000'])
    expect(stepCost(0.0124)).toBe('$0.0124')
  })

  it('elapsed time: seconds, minutes, hours, never negative', () => {
    expect([0, 999, 32_000, 59_999, 60_000, 125_000, 3_600_000, 3_780_000, -5000].map(elapsedText)).toEqual(['0 s', '0 s', '32 s', '59 s', '1 m 00 s', '2 m 05 s', '1 h 00 m', '1 h 03 m', '0 s'])
  })

  it('elapsed is first event to last, or to now while the Run runs; unreadable times give 0', () => {
    const r = run('2026-10-01T09:00:00.000Z', '2026-10-01T09:00:10.000Z', '2026-10-01T09:00:32.500Z')
    expect(elapsedMs(r, false, Date.parse('2030-01-01'))).toBe(32_500)
    expect(elapsedMs(r, true, Date.parse('2026-10-01T09:00:45.000Z'))).toBe(45_000)
    expect(elapsedMs(run('nonsense'), false, 0)).toBe(0)
  })

  it('a step line drops the scheme so it reads like a command', () => {
    expect(plainLine('browse open https://luma.com/discover')).toBe('browse open luma.com/discover')
    expect(plainLine('refused fetch: a fetch action is not available to this role')).toBe('refused fetch: a fetch action is not available to this role')
    expect(plainLine('delegate 1 → browser: Read http://a.example and https://b.example')).toBe('delegate 1 → browser: Read a.example and b.example')
  })

  it('plan progress counts done steps out of all, nothing else', () => {
    const s = (status: 'pending' | 'running' | 'done' | 'failed') => ({ role: 'browser', goal: 'g', status })
    expect(planProgress([s('done'), s('running'), s('pending'), s('failed')])).toEqual({ done: 1, total: 4 })
    expect(planProgress([])).toEqual({ done: 0, total: 0 })
  })
})
