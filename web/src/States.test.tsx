import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

// What the page says while it waits and when something fails: words, never a blank area or a wrong "nothing here".
const C = 'c'.repeat(32)
const t = (s: number) => `2026-10-01T09:00:${String(s).padStart(2, '0')}.000Z`
const LIST = [{ id: C, title: 'Which events are free?', updated_at: t(5), preview: 'Two of them.', state: 'idle' }]
const DETAIL = {
  id: C,
  title: 'Which events are free?',
  messages: [
    { type: 'message', id: 'm1', conversation_id: C, role: 'user', text: 'Which events are free?', run_id: null, cost_usd: null, at: t(1) },
    { type: 'message', id: 'm2', conversation_id: C, role: 'assistant', text: 'Two of them.', run_id: null, cost_usd: 0.05, at: t(5) },
  ],
  runs: [],
}

class FakeWS {
  static all: FakeWS[] = []
  onopen: (() => void) | null = null
  onmessage: ((e: { data: string }) => void) | null = null
  onclose: (() => void) | null = null
  url: string
  constructor(url: string) {
    this.url = url
    FakeWS.all.push(this)
  }
  send() {}
  close() {
    this.onclose?.()
  }
}

/** fetch answered by `routes`; a route may be a status number, a body, a promise (one that never settles: a slow answer), or a function returning any of those (so a test can change its mind). */
type Route = number | unknown | Promise<Response> | (() => number | unknown)
let routes: Record<string, Route> = {}
const answer = (path: string): Response | Promise<Response> => {
  const r = routes[path]
  const v = typeof r === 'function' ? (r as () => unknown)() : r
  if (v instanceof Promise) return v
  return typeof v === 'number' ? new Response('', { status: v }) : path in routes ? Response.json(v) : new Response('', { status: 404 })
}

beforeEach(() => {
  FakeWS.all = []
  routes = {}
  vi.stubGlobal('WebSocket', FakeWS)
  vi.stubGlobal('fetch', vi.fn(async (url: string) => answer(url)))
})
afterEach(() => vi.unstubAllGlobals())

const open = () => act(() => FakeWS.all[0].onopen?.())

describe('while it waits', () => {
  it('says it is loading, not "no chats" and not "ask something", until the list and the chat have been read', async () => {
    routes = { '/api/conversations': LIST, [`/api/conversations/${C}`]: new Promise<Response>(() => {}) } // the detail never answers
    render(<App />)
    expect(screen.getByText('Loading chats…')).toBeTruthy()
    expect(screen.getByText('Loading…')).toBeTruthy()
    expect(screen.queryByText('No chats yet.')).toBeNull()
    expect(screen.queryByText(/Ask something/)).toBeNull()
    open()
    expect(await screen.findByRole('button', { name: /Which events are free\?/ })).toBeTruthy() // the list is in; the chat is still being read
    expect(screen.getByText('Loading…')).toBeTruthy()
    expect(screen.queryByText(/Ask something/)).toBeNull()
  })

  it('a chat the backend has nothing stored for is an empty chat, not a chat that loads forever', async () => {
    routes = { '/api/conversations': LIST } // its detail is a 404
    render(<App />)
    open()
    expect(await screen.findByText(/Ask something/)).toBeTruthy()
    expect(screen.queryByText('Loading…')).toBeNull()
  })

  it('says "No chats yet." once it knows there are none', async () => {
    routes = { '/api/conversations': [] }
    render(<App />)
    open()
    expect(await screen.findByText('No chats yet.')).toBeTruthy()
    expect(screen.getByText(/Ask something/)).toBeTruthy()
  })
})

describe('when something fails', () => {
  it('the chat list: both places say so in words, and Retry now reads it again', async () => {
    let up = false
    routes = { '/api/conversations': () => (up ? LIST : 500), [`/api/conversations/${C}`]: DETAIL }
    render(<App />)
    open()
    expect(await screen.findByText('Your chats could not be loaded.')).toBeTruthy()
    expect(screen.getByText(/Nothing to show yet/)).toBeTruthy()
    expect(screen.getByRole('status').textContent).toContain('Could not load your chats')
    up = true
    fireEvent.click(screen.getByRole('button', { name: 'Retry now' }))
    expect(await screen.findByText('Two of them.', { selector: '.reply p' })).toBeTruthy()
    expect(screen.queryByText(/could not be loaded/)).toBeNull()
  })

  it('the open chat: says so, and Retry now reads that chat again (not only the list)', async () => {
    let up = false
    const detail = vi.fn(() => (up ? DETAIL : 500))
    routes = { '/api/conversations': LIST, [`/api/conversations/${C}`]: detail }
    render(<App />)
    open()
    expect(await screen.findByText(/Nothing to show yet/)).toBeTruthy()
    expect((await screen.findByRole('status')).textContent).toContain('Could not load this chat')
    expect(screen.queryByText('Loading…')).toBeNull()
    const before = detail.mock.calls.length
    up = true
    fireEvent.click(screen.getByRole('button', { name: 'Retry now' }))
    expect(await screen.findByText('Two of them.', { selector: '.reply p' })).toBeTruthy()
    expect(detail.mock.calls.length).toBeGreaterThan(before)
    await waitFor(() => expect(screen.queryByText(/Nothing to show yet/)).toBeNull())
  })
})
