import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import Markdown from 'react-markdown'
import './App.css'

type Chat = { role: 'user' | 'assistant'; text: string }
type PlanStep = { role: string; goal: string; status: 'pending' | 'running' | 'done' | 'failed' }
type TraceItem = {
  type: 'trace'
  kind: 'plan' | 'step' | 'return' | 'stop'
  role: string
  data: { summary: string; steps?: PlanStep[] }
  cost_usd: number
}
type Item = Chat | TraceItem

const isTrace = (i: Item): i is TraceItem => 'type' in i

function Trace({ items, live }: { items: TraceItem[]; live?: boolean }) {
  const steps = items.findLast((i) => i.kind === 'plan')?.data.steps
  const lines = items.filter((i) => i.kind !== 'plan')
  const cost = items.reduce((sum, i) => sum + i.cost_usd, 0)
  return (
    <details className="trace" open={live}>
      <summary>{live ? 'Working…' : `${lines.length} step${lines.length === 1 ? '' : 's'} · $${cost.toFixed(4)}`}</summary>
      {steps && (
        <ol className="plan">
          {steps.map((s, n) => (
            <li key={n} className={s.status}>{s.role}: {s.goal}</li>
          ))}
        </ol>
      )}
      <ul className="events">
        {lines.map((e, n) => (
          <li key={n} className={e.kind === 'return' ? 'ret' : undefined}>
            <b>{e.role}</b> {e.data.summary}
            {e.cost_usd > 0 && <small> ${e.cost_usd.toFixed(4)}</small>}
          </li>
        ))}
      </ul>
    </details>
  )
}

export default function App() {
  const [items, setItems] = useState<Item[]>([])
  const [text, setText] = useState('')
  const [online, setOnline] = useState(false)
  const [stopping, setStopping] = useState(false)
  const socket = useRef<WebSocket | null>(null)
  const bottom = useRef<HTMLDivElement>(null)

  // Every user message gets exactly one reply, so "working" = the last chat message is ours.
  const working = items.findLast((i) => !isTrace(i))?.role === 'user'

  useEffect(() => {
    let closed = false
    let retry: number
    const connect = () => {
      const ws = new WebSocket(`ws://${location.host}/ws`)
      socket.current = ws
      // The server replays the whole chat (and traces) on connect, so start from empty.
      ws.onopen = () => { setItems([]); setOnline(true) }
      ws.onmessage = (e) => setItems((cur) => [...cur, JSON.parse(e.data) as Item])
      ws.onclose = () => {
        setOnline(false)
        if (!closed) retry = window.setTimeout(connect, 1500)
      }
    }
    connect()
    return () => { closed = true; clearTimeout(retry); socket.current?.close() }
  }, [])

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [items])
  useEffect(() => { if (!working) setStopping(false) }, [working])

  const send = (e: FormEvent) => {
    e.preventDefault()
    const t = text.trim()
    if (!t || !online) return
    socket.current?.send(JSON.stringify({ text: t }))
    setText('')
  }

  const stop = () => {
    socket.current?.send(JSON.stringify({ stop: true }))
    setStopping(true)
  }

  // Trace events arrive before the reply they belong to: show them folded above it, or live while working.
  const blocks: ReactNode[] = []
  let pending: TraceItem[] = []
  items.forEach((item, i) => {
    if (isTrace(item)) {
      pending.push(item)
      return
    }
    if (item.role === 'assistant' && pending.length) blocks.push(<Trace key={`t${i}`} items={pending} />)
    pending = []
    blocks.push(
      <div key={i} className={`msg ${item.role}`}>
        <Markdown
          components={{
            a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer noopener">{children}</a>,
          }}
        >
          {item.text}
        </Markdown>
      </div>,
    )
  })

  return (
    <div className="chat">
      <header>
        <h1>Stepout</h1>
        <span className={online ? 'dot on' : 'dot'} title={online ? 'connected' : 'reconnecting…'} />
      </header>

      <main>
        {items.length === 0 && online && <p className="hint">Ask something. Try “what’s the news in New York today?”</p>}
        {blocks}
        {working && (
          <div className="live">
            <Trace items={pending} live />
            <button type="button" className="stop" onClick={stop} disabled={stopping}>
              {stopping ? 'Stopping…' : 'Stop'}
            </button>
          </div>
        )}
        <div ref={bottom} />
      </main>

      <form onSubmit={send}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={online ? 'Message Stepout…' : 'Connecting…'}
          autoFocus
        />
        <button type="submit" disabled={!online || !text.trim()}>Send</button>
      </form>
    </div>
  )
}
