import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

// The app against a fake WebSocket and a fake fetch: the same frames and bodies the mock sends.
const C = 'c'.repeat(32)
const R = 'a'.repeat(32)
const R2 = 'b'.repeat(32)
const NEW = 'e'.repeat(32) // the id the backend makes for a new chat
const t = (s: number) => `2026-10-01T09:00:${String(s).padStart(2, '0')}.000Z`

class FakeWS {
  static all: FakeWS[] = []
  sent: string[] = []
  onopen: (() => void) | null = null
  onmessage: ((e: { data: string }) => void) | null = null
  onclose: (() => void) | null = null
  url: string
  constructor(url: string) {
    this.url = url
    FakeWS.all.push(this)
  }
  send(data: string) {
    this.sent.push(data)
  }
  close() {
    this.onclose?.()
  }
  push(frame: unknown) {
    act(() => this.onmessage?.({ data: typeof frame === 'string' ? frame : JSON.stringify(frame) }))
  }
}

const events = [
  { id: 'e1', conversation_id: C, run_id: R, parent: null, kind: 'plan', role: 'orchestrator', data: { summary: 'plan updated', steps: [{ role: 'browser', goal: 'Open the page', status: 'done' }] }, cost_usd: 0, at: t(2) },
  { id: 'e2', conversation_id: C, run_id: R, parent: null, kind: 'step', role: 'browser', data: { summary: 'browse open https://example.com', verdict: 'allow' }, cost_usd: 0.0124, at: t(3) },
]
const API: Record<string, unknown> = {
  '/api/conversations': [{ id: C, title: 'Which events are free?', updated_at: t(5), preview: 'Two of them.', state: 'idle' }],
  [`/api/conversations/${C}`]: {
    id: C,
    title: 'Which events are free?',
    messages: [
      { type: 'message', id: 'm1', conversation_id: C, role: 'user', text: 'Which events are free?', run_id: null, cost_usd: null, at: t(1) },
      { type: 'message', id: 'm2', conversation_id: C, role: 'assistant', text: 'Two of them.', run_id: R, cost_usd: 0.05, at: t(5) },
    ],
    runs: [{ run_id: R, state: 'done', cost_usd: 0.05, cap_usd: 1, steps: 1, started_at: t(2), ended_at: t(5) }],
  },
  [`/api/runs/${R}/events`]: events,
}

beforeEach(() => {
  FakeWS.all = []
  vi.stubGlobal('WebSocket', FakeWS)
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => (init?.method === 'POST' ? Response.json({ id: NEW }, { status: 201 }) : url in API ? Response.json(API[url]) : new Response('', { status: 404 }))),
  )
})
afterEach(() => vi.unstubAllGlobals())

async function connected() {
  render(<App />)
  const ws = FakeWS.all[0]
  act(() => ws.onopen?.())
  await screen.findByText('Two of them.', { selector: '.reply p' })
  return ws
}

describe('App', () => {
  it('connects, then shows the chat list and the open chat with its run', async () => {
    render(<App />)
    expect(screen.getByRole('status').textContent).toContain('Connecting')
    const ws = FakeWS.all[0]
    expect(ws.url).toMatch(/^wss?:\/\/.+\/ws$/)
    act(() => ws.onopen?.())
    expect(await screen.findByRole('heading', { name: 'Which events are free?' })).toBeTruthy()
    expect(await screen.findByText('Two of them.', { selector: '.reply p' })).toBeTruthy()
    expect(screen.getByText('$0.05')).toBeTruthy() // the reply's cost
    expect(screen.getByText('1 step · $0.01 · 1 s')).toBeTruthy() // the run's summary: steps · cost · elapsed, from its events
    expect(screen.getByRole('button', { name: 'New chat' })).toBeTruthy()
    const row = screen.getByRole('button', { name: /Which events are free\?/ }) // the sidebar row is a named button
    expect(row.getAttribute('aria-current')).toBe('true')
    expect(screen.queryByRole('status')).toBeNull() // connected: no banner
  })

  it('New chat is instant: what you type next goes to a brand new chat, never the one you were in', async () => {
    const ws = await connected() // a chat is open
    fireEvent.click(screen.getByRole('button', { name: 'New chat' }))
    expect(screen.getByRole('heading', { name: 'New chat' })).toBeTruthy() // at once, with no wait for the backend
    const box = screen.getByLabelText('Message')
    fireEvent.change(box, { target: { value: 'a fresh start' } })
    fireEvent.keyDown(box, { key: 'Enter' }) // immediately: this used to race the chat being made and land in the old chat
    await waitFor(() => expect(JSON.parse(ws.sent.at(-1)!)).toEqual({ type: 'send', conversation_id: NEW, text: 'a fresh start' }))
    expect(ws.sent.every((f) => !f.includes(C))).toBe(true) // nothing was sent to the old chat
  })

  describe('asking for a Run\'s events', () => {
    // Asking for the events of a Run that has none yet is a 404, and Chrome logs every 404 as a console error.
    const withRun = (extra: object) => {
      const calls: string[] = []
      const detail = { ...(API[`/api/conversations/${C}`] as { runs: object[] }) }
      detail.runs = [...detail.runs, extra]
      vi.stubGlobal(
        'fetch',
        vi.fn(async (url: string, init?: RequestInit) => {
          calls.push(url)
          if (init?.method === 'POST') return Response.json({ id: NEW }, { status: 201 })
          if (url === `/api/conversations/${C}`) return Response.json(detail)
          if (url === `/api/runs/${R2}/events`) return Response.json([{ ...events[0], id: 'x1', run_id: R2 }])
          return url in API ? Response.json(API[url]) : new Response('', { status: 404 })
        }),
      )
      return calls
    }

    it('does not ask for the events of a Run that has just started: it has none yet, and they arrive live', async () => {
      const calls = withRun({ run_id: R2, state: 'running', cost_usd: 0, cap_usd: 1, steps: 0, started_at: t(9), ended_at: null })
      await connected()
      expect(calls).toContain(`/api/runs/${R}/events`) // a finished Run's events are read
      expect(calls.filter((u) => u.includes(R2))).toEqual([]) // the one that has just started is not asked for
    })

    it('does ask for a running Run that already has events (the page was opened mid-run)', async () => {
      const calls = withRun({ run_id: R2, state: 'running', cost_usd: 0.01, cap_usd: 1, steps: 2, started_at: t(9), ended_at: null })
      await connected()
      expect(calls).toContain(`/api/runs/${R2}/events`)
    })
  })

  it('two messages sent at once from a draft go to the same new chat: it is made once', async () => {
    const posts = vi.fn()
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (init?.method === 'POST') {
          posts()
          await new Promise((r) => setTimeout(r, 30)) // the backend takes a moment to make the chat
          return Response.json({ id: NEW }, { status: 201 })
        }
        return url in API ? Response.json(API[url]) : new Response('', { status: 404 })
      }),
    )
    const ws = await connected()
    fireEvent.click(screen.getByRole('button', { name: 'New chat' }))
    const box = screen.getByLabelText('Message')
    fireEvent.change(box, { target: { value: 'first' } })
    fireEvent.keyDown(box, { key: 'Enter' })
    fireEvent.change(box, { target: { value: 'second' } })
    fireEvent.keyDown(box, { key: 'Enter' }) // before the first message's chat exists
    await waitFor(() => expect(ws.sent).toHaveLength(2))
    expect(posts).toHaveBeenCalledTimes(1) // one chat, not two
    expect(ws.sent.map((f) => JSON.parse(f))).toEqual([
      { type: 'send', conversation_id: NEW, text: 'first' },
      { type: 'send', conversation_id: NEW, text: 'second' }, // in order, in the same chat
    ])
  })

  it('sends a message as a v1 `send` frame for the open chat', async () => {
    const ws = await connected()
    const box = screen.getByLabelText('Message')
    fireEvent.change(box, { target: { value: 'And the cheapest?' } })
    fireEvent.keyDown(box, { key: 'Enter' })
    expect(JSON.parse(ws.sent.at(-1)!)).toEqual({ type: 'send', conversation_id: C, text: 'And the cheapest?' })
  })

  it('shows a live run, lets you stop it, and drops Stop when it ends', async () => {
    const ws = await connected()
    ws.push({ type: 'message', id: 'm3', conversation_id: C, role: 'user', text: 'And the cheapest?', run_id: null, cost_usd: null, at: t(10) })
    ws.push({ type: 'status', state: 'running', active: { conversation_id: C, run_id: R2, cap_usd: 1 }, queued: [], at: t(10) })
    ws.push({ type: 'trace', id: 'e9', conversation_id: C, run_id: R2, parent: null, kind: 'step', role: 'orchestrator', data: { summary: 'plan: browser: Look it up', verdict: 'allow' }, cost_usd: 0.0141, at: t(11) })
    expect(await screen.findByText(/^Working…/)).toBeTruthy()
    expect(screen.getAllByRole('progressbar', { name: 'Budget' }).at(-1)!.getAttribute('aria-valuetext')).toBe('$0.01 of $1.00') // the live Run's spend against cap_usd from the status frame
    expect(screen.getByText('plan: browser: Look it up')).toBeTruthy()
    expect(screen.getAllByText('Running').length).toBeGreaterThan(0) // the header pill
    fireEvent.click(screen.getByRole('button', { name: 'Stop' }))
    expect(JSON.parse(ws.sent.at(-1)!)).toEqual({ type: 'stop' })

    ws.push({ type: 'trace', id: 'e10', conversation_id: C, run_id: R2, parent: null, kind: 'stop', role: 'orchestrator', data: { summary: 'Stopped by you.' }, cost_usd: 0, at: t(12) })
    ws.push({ type: 'status', state: 'idle', active: null, queued: [], at: t(12) })
    expect(screen.queryByRole('button', { name: 'Stop' })).toBeNull()
    expect(screen.getByText(/^Stopped by you · 1 step · /)).toBeTruthy()
  })

  it('marks a chat that is waiting behind a run as queued', async () => {
    const ws = await connected()
    const D = 'd'.repeat(32)
    ws.push({ type: 'message', id: 'q1', conversation_id: D, role: 'user', text: 'Count my PDFs', run_id: null, cost_usd: null, at: t(20) })
    ws.push({ type: 'status', state: 'running', active: { conversation_id: C, run_id: R2, cap_usd: 1 }, queued: [{ conversation_id: D }], at: t(20) })
    expect(await screen.findByRole('img', { name: 'queued' })).toBeTruthy()
    expect(screen.getByRole('img', { name: 'running' })).toBeTruthy()
  })

  it('ignores frames it does not understand', async () => {
    const ws = await connected()
    ws.push({ type: 'approval', id: 'x' })
    ws.push({ role: 'assistant', text: 'old v0 frame' })
    ws.push('not json at all')
    ws.push({ type: 'message', id: 5 })
    expect(screen.getByText('Two of them.', { selector: '.reply p' })).toBeTruthy()
    expect(screen.queryByText('old v0 frame')).toBeNull()
  })

  it('says so when the connection drops, blocks sending, and Retry now reconnects at once', async () => {
    const ws = await connected()
    act(() => ws.close())
    expect(screen.getByRole('status').textContent).toContain('Disconnected')
    fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'hi' } })
    expect((screen.getByLabelText('Send') as HTMLButtonElement).disabled).toBe(true)
    expect(FakeWS.all).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: 'Retry now' }))
    expect(FakeWS.all).toHaveLength(2)
    expect(screen.getByRole('status').textContent).toContain('Connecting')
  })

  it('shows an error with a retry when the chat list cannot be loaded', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 500 })))
    render(<App />)
    act(() => FakeWS.all[0].onopen?.())
    expect((await screen.findByRole('status')).textContent).toContain('Could not load your chats')
    expect(screen.getByRole('button', { name: 'Retry now' })).toBeTruthy()
  })
})
