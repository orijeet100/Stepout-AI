// The page's one connection to the backend: a WebSocket for live frames, fetch() for history, state in one reducer.
import { useCallback, useEffect, useReducer, useRef } from 'react'
import { parseChats, parseDetail, parseEvents, parseFrame } from './protocol'
import { initial, reducer, type State } from './store'

/** Reconnect wait after the nth failed attempt (0-based): 1 s, 2 s, 4 s … never more than 15 s. */
export const nextDelay = (attempt: number) => Math.min(1000 * 2 ** attempt, 15_000)

export type Backend = {
  state: State
  send: (text: string) => void
  stop: () => void
  newChat: () => void
  select: (id: string) => void
  retry: () => void
}

async function getJSON(path: string): Promise<unknown> {
  const r = await fetch(path)
  if (r.status === 404) return null // a chat the backend has not stored yet (just created, still empty)
  if (!r.ok) throw new Error(`${path}: ${r.status}`)
  return r.json()
}

export function useBackend(): Backend {
  const [state, dispatch] = useReducer(reducer, initial)
  const socket = useRef<WebSocket | null>(null)
  const selected = useRef<string | null>(null)
  const haveEvents = useRef<Set<string>>(new Set()) // runs whose events are already in state
  const reconnect = useRef<() => void>(() => {})
  const creating = useRef<Promise<string | null> | null>(null) // a chat being made: messages sent meanwhile wait for it instead of making their own
  useEffect(() => {
    selected.current = state.selected
    haveEvents.current = new Set(Object.values(state.runs).filter((r) => r.events.length > 0).map((r) => r.id))
  })

  // `all`: read every run's events again (after a reconnect, frames may have been missed). Otherwise only runs we have none of.
  const loadChat = useCallback(async (id: string, all = false) => {
    try {
      const d = parseDetail(await getJSON(`/api/conversations/${encodeURIComponent(id)}`))
      if (!d) return void dispatch({ type: 'detail', id, title: '', messages: [], runs: [] }) // the backend has nothing stored for it: an empty chat, now known to be
      dispatch({ type: 'detail', id, title: d.title, messages: d.messages, runs: d.runs })
      await Promise.all(
        d.runs
          .filter((r) => all || !haveEvents.current.has(r.run_id))
          .filter((r) => !(r.state === 'running' && r.steps === 0)) // just started: it has no events to read yet (asking is a 404, which Chrome logs as an error); they arrive live
          .map(async (r) => dispatch({ type: 'events', runId: r.run_id, events: parseEvents(await getJSON(`/api/runs/${encodeURIComponent(r.run_id)}/events`)) })),
      )
    } catch {
      dispatch({ type: 'error', error: 'Could not load this chat.' })
    }
  }, [])

  const loadChats = useCallback(async () => {
    try {
      dispatch({ type: 'chats', chats: parseChats(await getJSON('/api/conversations')) })
      dispatch({ type: 'error', error: null })
    } catch {
      dispatch({ type: 'error', error: 'Could not load your chats.' })
    }
  }, [])

  // (Re)connect: frames sent while the page was away are gone, so every open re-reads the list and the open chat.
  useEffect(() => {
    let disposed = false
    let attempt = 0
    let timer: number | undefined
    const connect = () => {
      window.clearTimeout(timer)
      dispatch({ type: 'conn', conn: 'connecting', attempt })
      const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`)
      socket.current = ws
      ws.onopen = () => {
        attempt = 0
        dispatch({ type: 'conn', conn: 'open', attempt: 0 })
        void loadChats().then(() => {
          if (selected.current) return loadChat(selected.current, true)
        })
      }
      ws.onmessage = (e) => {
        try {
          const frame = parseFrame(JSON.parse(String(e.data)))
          if (frame) dispatch({ type: 'frame', frame })
        } catch {
          // not JSON: ignore
        }
      }
      ws.onclose = () => {
        if (disposed || socket.current !== ws) return
        dispatch({ type: 'conn', conn: 'closed', attempt: attempt + 1 })
        timer = window.setTimeout(connect, nextDelay(attempt++) * (0.75 + Math.random() * 0.5)) // jitter: no thundering herd
      }
    }
    reconnect.current = () => {
      socket.current?.close()
      attempt = 0
      connect()
    }
    connect()
    return () => {
      disposed = true
      window.clearTimeout(timer)
      socket.current?.close()
    }
  }, [loadChats, loadChat])

  useEffect(() => {
    if (state.selected) void loadChat(state.selected)
  }, [state.selected, loadChat])

  // When a Run ends, read its chat again: the API then knows how it ended (failed, stopped) and its budget.
  const wasActive = useRef<{ conversation_id: string; run_id: string } | null>(null)
  const active = state.status.active
  useEffect(() => {
    const before = wasActive.current
    if (before && before.run_id !== active?.run_id) void loadChat(before.conversation_id)
    wasActive.current = active
  }, [active, loadChat])

  const createChat = useCallback(async (): Promise<string | null> => {
    try {
      const r = await fetch('/api/conversations', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
      if (!r.ok) throw new Error(String(r.status))
      const { id } = (await r.json()) as { id: string }
      dispatch({ type: 'created', id, at: new Date().toISOString() })
      selected.current = id // at once: the next message must not wait for a render to learn which chat it is in
      return id
    } catch {
      dispatch({ type: 'error', error: 'Could not start a new chat.' })
      return null
    }
  }, [])

  const send = useCallback(
    (text: string) => {
      void (async () => {
        const id = selected.current ?? (await (creating.current ??= createChat().finally(() => (creating.current = null))))
        if (id) socket.current?.send(JSON.stringify({ type: 'send', conversation_id: id, text }))
      })()
    },
    [createChat],
  )

  return {
    state,
    send,
    stop: () => socket.current?.send(JSON.stringify({ type: 'stop' })),
    newChat: () => dispatch({ type: 'select', id: null }), // instant: the chat is made when its first message is sent, so typing at once cannot land in the old chat
    select: (id) => dispatch({ type: 'select', id }),
    retry: () => {
      if (!state.error) return reconnect.current()
      void loadChats()
      if (selected.current) void loadChat(selected.current, true) // the open chat too: its own error is the one that may be showing
    },
  }
}
