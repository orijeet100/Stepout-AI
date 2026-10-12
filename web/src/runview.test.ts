import { describe, expect, it } from 'vitest'
import { agentName, elapsedMs, elapsedText, hasBrowserStep, liveSrc, money, plainLine, planProgress, safeHref, shortModel, shotSrc, shotsOf, stepCost, workOf } from './runview'
import type { Run } from './store'
import { runOf, stateOf } from './testFixtures'

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
    const s = (status: 'pending' | 'running' | 'done' | 'failed') => ({ role: 'web_browsing', goal: 'g', status })
    expect(planProgress([s('done'), s('running'), s('pending'), s('failed')])).toEqual({ done: 1, total: 4 })
    expect(planProgress([])).toEqual({ done: 0, total: 0 })
  })
})

describe("the browser's pages", () => {
  const RUN = 'ab'.repeat(16)
  const withEvents = (events: object[]): Run => ({ id: RUN, conversationId: 'c', startedAt: 't', hint: null, cap: null, events: events as Run['events'] })
  const shot = (n: number, data: object = {}) => ({ id: `s${n}`, kind: 'shot', role: 'web_browsing', data: { shot: `${RUN}/${n}.jpg`, url: `https://example.com/${n}`, title: `Page ${n}`, ...data } })

  it("lists a Run's screenshots in order, with their page address and title", () => {
    const run = withEvents([{ id: 'p', kind: 'plan', data: {} }, shot(1), { id: 'x', kind: 'step', role: 'web_browsing', data: {} }, shot(2, { title: undefined })])
    expect(shotsOf(run)).toEqual([
      { path: `${RUN}/1.jpg`, url: 'https://example.com/1', title: 'Page 1' },
      { path: `${RUN}/2.jpg`, url: 'https://example.com/2', title: null },
    ])
    expect(shotsOf(withEvents([{ id: 's', kind: 'shot', role: 'web_browsing', data: {} }]))).toEqual([]) // a shot event with no file names nothing to show
  })

  it('there is a page to watch only once the Web Browsing agent has acted', () => {
    expect(hasBrowserStep(withEvents([{ id: 'a', kind: 'step', role: 'orchestrator', data: {} }]))).toBe(false)
    expect(hasBrowserStep(withEvents([{ id: 'a', kind: 'step', role: 'local_file_finder', data: {} }]))).toBe(false)
    expect(hasBrowserStep(withEvents([{ id: 'a', kind: 'step', role: 'web_browsing', data: {} }]))).toBe(true)
    expect(hasBrowserStep(withEvents([{ id: 'a', kind: 'step', role: 'browser', data: {} }]))).toBe(true) // a chat saved before the rename
  })

  it('a screenshot address is only ever the <run>/<n>.jpg the backend writes', () => {
    expect(shotSrc(`${RUN}/3.jpg`)).toBe(`/shots/${RUN}/3.jpg`)
    for (const bad of ['', '../secret.txt', `${RUN}/../x.jpg`, `${RUN}/3.png`, `${RUN}/3.jpg?x=1`, `${RUN.toUpperCase()}/3.jpg`, `${RUN}/3.jpg/extra`, 'https://evil.example/a.jpg', `//${RUN}/3.jpg`, `${RUN}%2f3.jpg`]) {
      expect(shotSrc(bad), bad).toBeNull()
    }
  })

  it('an agent reads as its use-case name; a chat saved with the first role ids reads the same', () => {
    expect(agentName('local_file_finder')).toBe('Local File Finder')
    expect(agentName('direct')).toBe('Web Research')
    expect(agentName('orchestrator')).toBe('Orchestrator')
  })

  it('the live address is built only from a 32-hex run id', () => {
    expect(liveSrc(RUN)).toBe(`/live/${RUN}`)
    for (const bad of ['', 'nope', '../x', RUN.toUpperCase(), RUN + '0', `${RUN}?x=1`, `${RUN}/../..`]) expect(liveSrc(bad), bad).toBeNull()
  })

  it('a page address becomes a link only if it is http or https', () => {
    expect(safeHref('https://luma.com/discover?x=1#top')).toBe('https://luma.com/discover?x=1#top')
    expect(safeHref('http://localhost:8080/a')).toBe('http://localhost:8080/a')
    for (const bad of [null, '', 'luma.com', 'javascript:alert(1)', 'data:text/html,<script>', 'file:///etc/passwd', 'ftp://x.example', '//evil.example', 'vbscript:x']) expect(safeHref(bad), String(bad)).toBeNull()
  })
})

describe('the work of a Run: the Orchestrator’s delegations are tasks, and each hand action is a tool call', () => {
  const work = (name: string, opts: Parameters<typeof stateOf>[1] = { hint: 'done' }, running = false) => workOf(stateOf(name, opts).runs[runOf(name)!], running)

  it('a web run: two tasks, in plan order, each with its own tool calls and what it reported back', () => {
    const { tasks, calls } = work('web-run')
    expect(calls).toEqual([]) // the Orchestrator only planned, delegated and answered
    expect(tasks.map((t) => [t.goal, t.role, t.state])).toEqual([
      ['Open the Luma discover page for New York', 'web_browsing', 'done'],
      ['Read the three most popular weekend events', 'web_browsing', 'done'],
    ])
    expect(tasks.map((t) => t.calls.map((c) => [c.label, c.arg]))).toEqual([
      [['Opened a page', 'luma.com/discover']],
      [['Followed a link', 'link 3'], ['Scrolled the page', '']],
    ])
    expect(tasks[0].result).toBe('The discover page is open; the New York list is behind link 3.') // "done: " is the state, not the words
    expect(tasks[0].calls[0].request).toBe('{"op": "open", "url": "https://luma.com/discover"}')
    expect(tasks[0].calls[0].cost).toBe(0.0124)
  })

  it('while it runs: the task under way is running, and so is its newest call that has no result yet', () => {
    const { tasks } = work('web-run', { upTo: 12, active: 1 }, true) // the second task has just followed a link
    expect(tasks.map((t) => t.state)).toEqual(['done', 'running'])
    expect(tasks[1].calls.map((c) => [c.state, c.doing])).toEqual([['running', 'Following a link']])
  })

  it('a refused action is a call that did not run, with the Gate’s reason as its result', () => {
    const [task] = work('refused-action').tasks
    const [refused, opened] = task.calls
    expect([refused.label, refused.state, refused.result]).toEqual(['Not allowed to read a page', 'refused', 'Refused: a fetch action is not available to this role'])
    expect([opened.label, opened.state]).toEqual(['Opened a page', 'done'])
  })

  it('a stop: the task says stopped, once, and is not relabelled failed by the return that follows', () => {
    const { tasks, calls } = work('stopped', { hint: 'stopped' })
    expect(tasks.map((t) => [t.state, t.result])).toEqual([['stopped', 'Stopped by you.']])
    expect(calls).toEqual([]) // the Orchestrator's own "Stopped by you." is not a second line
    expect(work('over-budget', { hint: 'stopped' }).tasks[0].result).toBe('Stopped: the $1.00 budget for this run is used up.')
  })

  it('a Run that ended before its task reported back leaves the task stopped, not spinning', () => {
    const { tasks } = work('web-run', { upTo: 12, hint: 'failed' }, false)
    expect(tasks[1].state).toBe('stopped')
    expect(tasks[1].calls.every((c) => c.state !== 'running')).toBe(true)
  })

  it('a model id reads as its family; another provider keeps its own name', () => {
    expect(['claude-haiku-5-5', 'claude-sonnet-5-5', 'anthropic/claude-opus-5-5', 'openai/gpt-5-mini', 'qwen3'].map(shortModel)).toEqual(['haiku', 'sonnet', 'opus', 'gpt-5-mini', 'qwen3'])
  })
})
