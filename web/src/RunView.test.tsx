import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ChatView from './ChatView'
import RunBlock from './RunBlock'
import { runCap, runState, timeline, type State } from './store'
import { chatOf, dollars, expected, raw, runOf, stateOf } from './testFixtures'

// Every state of the run view, from the invented fixtures. Expected numbers are read from the raw JSON, not from the page's code.
const show = (s: State, name: string, onStop = () => {}) =>
  render(<ChatView items={timeline(s, chatOf(name))} runState={(r) => runState(s, r)} runCap={(r) => runCap(s, r)} onStop={onStop} />)
const summary = (c: HTMLElement) => c.querySelector('.run__sum')?.textContent
const bar = (label: string) => screen.getByRole('progressbar', { name: label })

describe('done: a collapsed summary with the numbers of the Run', () => {
  it('shows steps · cost · elapsed that match the fixture, collapsed, and the details inside', () => {
    const { steps, cost, seconds } = expected('web-run')
    const { container } = show(stateOf('web-run', { hint: 'done', cap: 1 }), 'web-run')
    expect(summary(container)).toBe(`${steps} steps · ${dollars(cost)} · ${seconds} s`)
    expect(container.querySelector('details')!.open).toBe(false) // collapsed once finished; the body is still there to expand
    expect(screen.getByText('browse open luma.com/discover')).toBeTruthy() // a plain-language line
    expect(screen.getByText('browse open luma.com/discover').getAttribute('title')).toBe('browse open https://luma.com/discover') // the full text is one hover away
  })

  it('has the plan checklist with every step done, and a step list with role chip, verdict and the step cost', () => {
    show(stateOf('web-run', { hint: 'done', cap: 1 }), 'web-run')
    const plan = screen.getByRole('list', { name: 'Plan' })
    expect(within(plan).getAllByRole('img', { name: 'done' })).toHaveLength(2)
    const steps = screen.getByRole('list', { name: 'Steps' })
    const open = within(steps).getByText('browse open luma.com/discover').closest('li')!
    expect(open.textContent).toContain('browser')
    expect(open.textContent).toContain('Allowed')
    expect(open.textContent).toContain('$0.0124') // that step's own cost
  })

  it('shows the plan and budget as real numbers against real limits, in the body', () => {
    const { cost } = expected('web-run')
    show(stateOf('web-run', { hint: 'done', cap: 1 }), 'web-run')
    expect(bar('Plan').getAttribute('aria-valuetext')).toBe('2 of 2 steps')
    expect(bar('Budget').getAttribute('aria-valuetext')).toBe(`${dollars(cost)} of $1.00`)
    expect(Number(bar('Budget').getAttribute('aria-valuenow'))).toBeCloseTo(cost, 6)
    expect(bar('Budget').getAttribute('aria-valuemax')).toBe('1')
  })

  it('a Files run and a chat reply read the same way', () => {
    show(stateOf('files-run', { hint: 'done', cap: 1 }), 'files-run')
    expect(screen.getByText('files count D:\\Example\\Projects *.pdf')).toBeTruthy()
    const { steps, cost, seconds } = expected('files-run')
    expect(summary(document.body)).toBe(`${steps} steps · ${dollars(cost)} · ${seconds} s`)
  })

  it('a refused action shows as Refused, with its reason, and the Run is still done', () => {
    const s = stateOf('refused-action', { hint: 'done', cap: 1 })
    show(s, 'refused-action')
    const line = screen.getByText(/refused fetch: a fetch action is not available to this role/).closest('li')!
    expect(line.textContent).toContain('Refused')
    expect(summary(document.body)).toMatch(/^\d+ steps · /) // not labelled stopped or failed
  })
})

describe('running: progress, elapsed, Stop', () => {
  const UP_TO = 11 // the web run caught after its first plan step is done and its second is running
  const s = stateOf('web-run', { upTo: UP_TO, active: 1 })
  const run = s.runs[runOf('web-run')!]
  const partial = raw('web-run').slice(0, UP_TO).filter((f) => f.type === 'trace')
  const spent = partial.reduce((sum, f) => sum + (f.cost_usd as number), 0)
  const now = Date.parse(partial[0].at as string) + 17_000

  it('is open, says "Working…" with done-of-total and elapsed from the event times', () => {
    const { container } = render(<RunBlock run={run} state={runState(s, run)} cap={runCap(s, run)} now={now} onStop={() => {}} />)
    expect(runState(s, run)).toBe('running')
    expect(summary(container)).toBe('Working… · 1 of 2 steps · 17 s') // elapsed = now − the first event
    expect(container.querySelector('details')!.open).toBe(true)
  })

  it('shows the meters: steps done of total, spend against the Run’s cap (cap_usd from status)', () => {
    render(<RunBlock run={run} state="running" cap={runCap(s, run)} now={now} onStop={() => {}} />)
    expect(bar('Plan').getAttribute('aria-valuetext')).toBe('1 of 2 steps')
    expect(bar('Budget').getAttribute('aria-valuetext')).toBe(`${dollars(spent)} of $1.00`)
    expect(Number(bar('Budget').getAttribute('aria-valuenow'))).toBeCloseTo(spent, 6)
    const plan = screen.getByRole('list', { name: 'Plan' })
    expect(within(plan).getAllByRole('img').map((g) => g.getAttribute('aria-label'))).toEqual(['done', 'running'])
  })

  it('has a Stop button that calls back', () => {
    const onStop = vi.fn()
    render(<RunBlock run={run} state="running" cap={1} now={now} onStop={onStop} />)
    fireEvent.click(screen.getByRole('button', { name: 'Stop' }))
    expect(onStop).toHaveBeenCalledOnce()
  })

  it('has no budget meter when the cap is unknown, and no plan meter before there is a plan: no invented numbers', () => {
    const early = stateOf('web-run', { upTo: 3, active: 0 }) // the plan step only; status says no cap
    const r = early.runs[runOf('web-run')!]
    render(<RunBlock run={r} state="running" cap={runCap(early, r)} now={now} onStop={() => {}} />)
    expect(screen.queryByRole('progressbar')).toBeNull()
    expect(runCap(early, r)).toBeNull()
  })

  it('has no Stop button once it is not running', () => {
    show(stateOf('web-run', { hint: 'done', cap: 1 }), 'web-run')
    expect(screen.queryByRole('button', { name: 'Stop' })).toBeNull()
  })
})

describe('stopped, over budget, failed', () => {
  it('stopped by you: labelled, with the stop line and a failed plan step', () => {
    const { steps, cost, seconds } = expected('stopped')
    const { container } = show(stateOf('stopped', { hint: 'stopped', cap: 1 }), 'stopped')
    expect(summary(container)).toBe(`Stopped by you · ${steps} steps · ${dollars(cost)} · ${seconds} s`)
    expect(screen.getAllByText('Stopped by you.').length).toBeGreaterThan(0)
    expect(within(screen.getByRole('list', { name: 'Plan' })).getByRole('img', { name: 'failed' })).toBeTruthy()
    expect(container.querySelector('.run')!.className).toContain('run--stopped')
  })

  it('over budget: its own label, and a budget meter that is full and says so in numbers', () => {
    const { steps, cost, seconds } = expected('over-budget')
    const { container } = show(stateOf('over-budget', { hint: 'stopped', cap: 1 }), 'over-budget')
    expect(summary(container)).toBe(`Over budget · ${steps} steps · ${dollars(cost)} · ${seconds} s`)
    expect(cost).toBeGreaterThanOrEqual(1) // the fixture really crosses its cap
    expect(bar('Budget').getAttribute('aria-valuetext')).toBe(`${dollars(cost)} of $1.00`)
    expect(bar('Budget').querySelector('span')!.className).toContain('is-full')
    expect(bar('Budget').querySelector('span')!.getAttribute('style')).toContain('width: 100%') // clamped, but the text keeps the true figure
    expect(container.querySelector('.run')!.className).toContain('run--overbudget')
  })

  it('failed (the API says so; no stop event): labelled Failed', () => {
    const { container } = show(stateOf('files-run', { hint: 'failed', cap: 1 }), 'files-run')
    expect(summary(container)).toMatch(/^Failed · \d+ steps · /)
    expect(container.querySelector('.run')!.className).toContain('run--failed')
  })

  it('a stopped Run whose events are not loaded yet is still stopped (from the API)', () => {
    const s = stateOf('stopped', { hint: 'stopped' })
    const run = { ...s.runs[runOf('stopped')!], events: s.runs[runOf('stopped')!].events.filter((e) => e.kind !== 'stop') }
    expect(runState(s, run)).toBe('stopped')
  })
})

describe('declined and queued', () => {
  it('a decline is a reply with no Run: a note saying no run was started, no run block, no cost', () => {
    const { container } = show(stateOf('declined'), 'declined')
    expect(container.querySelector('.run')).toBeNull()
    expect(screen.getByText('No run was started')).toBeTruthy()
    expect(screen.getByText(/payments and transfers, which I won't do/).closest('.reply')!.className).toContain('reply--note')
    expect(container.querySelector('.reply small.muted')).toBeNull() // no cost: nothing was spent on a Run
  })

  it('a message waiting its turn is tagged Queued; the one before it is not', () => {
    const chat = chatOf('chat-reply')
    const extra = [
      { type: 'frame', frame: { type: 'message', id: 'q1', conversation_id: chat, role: 'user', text: 'and another thing', run_id: null, cost_usd: null, at: '2026-10-09T10:00:00.000Z' } },
      { type: 'frame', frame: { type: 'status', state: 'running', active: null, queued: [{ conversation_id: chat }] } },
    ] as const
    const s = stateOf('chat-reply', { extra: [...extra] })
    const { container } = show(s, 'chat-reply')
    const users = [...container.querySelectorAll('.user')]
    expect(users.map((u) => u.textContent)).toEqual(['What is 2 + 3?', 'and another thing' + 'Queued'])
    expect(screen.getAllByText('Queued')).toHaveLength(1)
  })
})
