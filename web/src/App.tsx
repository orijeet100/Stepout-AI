import { useEffect, useRef, useState, type FormEvent } from 'react'
import Markdown from 'react-markdown'
import './App.css'

type Msg = { role: 'user' | 'assistant'; text: string }

export default function App() {
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [text, setText] = useState('')
  const [online, setOnline] = useState(false)
  const socket = useRef<WebSocket | null>(null)
  const bottom = useRef<HTMLDivElement>(null)

  // Every user message gets exactly one reply, so "working" = the last message is ours.
  const working = msgs.at(-1)?.role === 'user'

  useEffect(() => {
    let closed = false
    let retry: number
    const connect = () => {
      const ws = new WebSocket(`ws://${location.host}/ws`)
      socket.current = ws
      // The server replays the whole chat on connect, so start from empty.
      ws.onopen = () => { setMsgs([]); setOnline(true) }
      ws.onmessage = (e) => setMsgs((cur) => [...cur, JSON.parse(e.data) as Msg])
      ws.onclose = () => {
        setOnline(false)
        if (!closed) retry = window.setTimeout(connect, 1500)
      }
    }
    connect()
    return () => { closed = true; clearTimeout(retry); socket.current?.close() }
  }, [])

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs])

  const send = (e: FormEvent) => {
    e.preventDefault()
    const t = text.trim()
    if (!t || !online) return
    socket.current?.send(JSON.stringify({ text: t }))
    setText('')
  }

  return (
    <div className="chat">
      <header>
        <h1>Stepout</h1>
        <span className={online ? 'dot on' : 'dot'} title={online ? 'connected' : 'reconnecting…'} />
      </header>

      <main>
        {msgs.length === 0 && online && <p className="hint">Ask something. Try “what’s the news in New York today?”</p>}
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <Markdown
              components={{
                a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer noopener">{children}</a>,
              }}
            >
              {m.text}
            </Markdown>
          </div>
        ))}
        {working && <div className="msg assistant working">Working…</div>}
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
