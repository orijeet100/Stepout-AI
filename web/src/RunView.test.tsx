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
    expect(summary(container)).toBe(`${steps} action${steps === 1 ? '' : 's'} · ${dollars(cost)} · ${seconds} s`)
    expect(container.querySelector('details')!.open).toBe(false) // collapsed once finished; the body is still there to expand
    const tasks = screen.getByRole('region', { name: 'Tasks' })
    expect([...tasks.querySelectorAll('.task__goal')].map((g) => g.textContent)).toEqual(['Open the Luma discover page for New York', 'Read the three most popular weekend events'])
    expect(within(tasks).getAllByText('done')).toHaveLength(2) // each task says how it ended, for a screen reader too
    expect(tasks.textContent).toContain('2 tasks')
  })

  it('a finished task is closed on its result; opened, its tool calls read in plain words, and a call opens onto its request and cost', () => {
    show(stateOf('web-run', { hint: 'done', cap: 1 }), 'web-run')
    const [first] = screen.getByRole('region', { name: 'Tasks' }).querySelectorAll<HTMLElement>('.task')
    expect(first.textContent).toContain('The discover page is open; the New York list is behind link 3.') // the result, without opening
    expect(within(first).queryByText('Opened a page')).toBeNull()
    fireEvent.click(within(first).getByRole('button', { name: /Open the Luma discover page/ }))
    const call = within(first).getByRole('button', { name: /Opened a page/ })
    expect(call.textContent).toContain('luma.com/discover') // the argument, in its chip
    fireEvent.click(call)
    expect(within(first).getByText('{"op": "open", "url": "https://luma.com/discover"}')).toBeTruthy()
    expect(within(first).getByText('$0.0124')).toBeTruthy() // the model call that asked for it
  })

  it('shows the saved pages as thumbnails under the closed summary, outside the details, and each one opens its page', () => {
    const s = stateOf('web-run', { hint: 'done', cap: 1 })
    const open = vi.fn()
    const { container } = render(<ChatView items={timeline(s, chatOf('web-run'))} runState={(r) => runState(s, r)} runCap={(r) => runCap(s, r)} onStop={() => {}} onOpenShot={open} />)
    const details = container.querySelector('details')!
    expect(details.open).toBe(false)
    const thumbs = screen.getAllByRole('button', { name: /^Open screenshot \d of \d/ })
    expect(thumbs).toHaveLength(2) // the fixture's two saved pages
    for (const t of thumbs) expect(details.contains(t)).toBe(false) // reachable without opening the summary, and not twice
    fireEvent.click(thumbs[1])
    expect(open).toHaveBeenCalledWith(expect.any(String), 1)
  })

  it('has the plan checklist with every step done, and each task names its agent', () => {
    show(stateOf('web-run', { hint: 'done', cap: 1 }), 'web-run')
    const plan = screen.getByRole('list', { name: 'Plan' })
    expect(within(plan).getAllByRole('img', { name: 'done' })).toHaveLength(2)
    expect(within(screen.getByRole('region', { name: 'Tasks' })).getAllByText('web browsing')).toHaveLength(2)
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
    fireEvent.click(screen.getByRole('button', { name: /Count the PDF files/ }))
    expect(screen.getByRole('button', { name: /Counted files/ }).textContent).toContain('D:\\Example\\Projects *.pdf')
    const { steps, cost, seconds } = expected('files-run')
    expect(summary(document.body)).toBe(`${steps} action${steps === 1 ? '' : 's'} · ${dollars(cost)} · ${seconds} s`)
  })

  it('a refused action shows as Refused, with its reason, and the Run is still done', () => {
    const s = stateOf('refused-action', { hint: 'done', cap: 1 })
    show(s, 'refused-action')
    fireEvent.click(screen.getByRole('button', { name: /Open a forecast page/ }))
    const refused = screen.getByRole('button', { name: /Not allowed to read a page/ })
    expect(refused.textContent).toContain('refused') // said, not only drawn as a cross
    fireEvent.click(refused)
    expect(screen.getByText('Refused: a fetch action is not available to this role')).toBeTruthy()
    expect(summary(document.body)).toMatch(/^\d+ actions · /) // not labelled stopped or failed
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
  it('stopped by you: labelled, with the stop line on its task, which says stopped', () => {
    const { steps, cost, seconds } = expected('stopped')
    const { container } = show(stateOf('stopped', { hint: 'stopped', cap: 1 }), 'stopped')
    expect(summary(container)).toBe(`Stopped by you · ${steps} action${steps === 1 ? '' : 's'} · ${dollars(cost)} · ${seconds} s`)
    expect(screen.getAllByText('Stopped by you.').length).toBeGreaterThan(0)
    expect(container.querySelector('.task')!.getAttribute('data-state')).toBe('stopped') // a one-step plan is its task card alone
    expect(screen.queryByRole('list', { name: 'Plan' })).toBeNull()
    expect(container.querySelector('.run')!.className).toContain('run--stopped')
  })

  it('over budget: its own label, and a budget meter that is full and says so in numbers', () => {
    const { steps, cost, seconds } = expected('over-budget')
    const { container } = show(stateOf('over-budget', { hint: 'stopped', cap: 1 }), 'over-budget')
    expect(summary(container)).toBe(`Over budget · ${steps} action${steps === 1 ? '' : 's'} · ${dollars(cost)} · ${seconds} s`)
    expect(cost).toBeGreaterThanOrEqual(1) // the fixture really crosses its cap
    expect(bar('Budget').getAttribute('aria-valuetext')).toBe(`${dollars(cost)} of $1.00`)
    expect(bar('Budget').querySelector('span')!.className).toContain('is-full')
    expect(bar('Budget').querySelector('span')!.getAttribute('style')).toContain('width: 100%') // clamped, but the text keeps the true figure
    expect(container.querySelector('.run')!.className).toContain('run--overbudget')
  })

  it('the budget bar turns amber at 80% of the cap and red at 100%, from the real numbers (never before)', () => {
    const { cost } = expected('web-run') // 0.1388
    const bar = (cap: number) => {
      const s = stateOf('web-run', { hint: 'done', cap })
      const { container } = show(s, 'web-run')
      const tone = container.querySelector('[role=progressbar][aria-label=Budget] > span')!.className
      container.remove()
      return tone
    }
    expect(bar(cost / 0.5)).toBe('') // 50% spent: the accent
    expect(bar(cost / 0.8)).toBe('is-warn') // exactly 80%
    expect(bar(cost / 0.95)).toBe('is-warn')
    expect(bar(cost)).toBe('is-full') // the cap itself
    expect(bar(cost / 1.4)).toBe('is-full') // beyond it
  })

  it('failed (the API says so; no stop event): labelled Failed', () => {
    const { container } = show(stateOf('files-run', { hint: 'failed', cap: 1 }), 'files-run')
    expect(summary(container)).toMatch(/^Failed · \d+ actions? · /)
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

describe('retries and Memory are lines of the Run, not steps', () => {
  const event = (id: string, kind: string, role: string, data: Record<string, unknown>, cost = 0) => ({
    id, conversation_id: 'c'.repeat(32), run_id: 'r'.repeat(32), parent: null, kind, role, data, cost_usd: cost, at: `2026-10-12T09:00:0${id}.000Z`,
  })

  it('shows a wait for the provider and a Memory miss, not Memory doing its job, and counts only tool calls', () => {
    const run = {
      id: 'r'.repeat(32), conversationId: 'c'.repeat(32), startedAt: '2026-10-12T09:00:00.000Z', hint: 'done' as const, cap: 1,
      events: [
        event('1', 'memory', 'orchestrator', { summary: 'Memory handed over 2 item(s), 180 characters', op: 'recall', ok: true }),
        event('2', 'retry', 'web_research', { summary: 'The provider is busy; trying again in 2 s (2 of 3)' }, 0.0003),
        event('3', 'step', 'orchestrator', { summary: 'fetch https://example.com', verdict: 'allow', action: { kind: 'fetch', url: 'https://example.com' } }, 0.01),
        event('4', 'memory', 'orchestrator', { summary: 'This task was not kept in Memory', op: 'record', ok: false }),
      ],
    }
    const { container } = render(<RunBlock run={run} state="done" cap={1} now={0} onStop={() => {}} />)
    expect(screen.queryByText('Memory handed over 2 item(s), 180 characters')).toBeNull() // Memory doing its job is bookkeeping; the Memory panel shows what it keeps
    expect(screen.getByText('The provider is busy; trying again in 2 s (2 of 3)')).toBeTruthy()
    expect(container.querySelector('.run__sum')?.textContent).toContain('1 action ') // the retry and the Memory lines are not actions
    const missed = screen.getByText('This task was not kept in Memory').closest('.tool')!
    expect(missed.className).toContain('tool--note')
    expect(missed.getAttribute('data-state')).toBe('failed') // a cross, and "failed" for a screen reader
    expect(missed.textContent).toContain('failed')
  })
})
