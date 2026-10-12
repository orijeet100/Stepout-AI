import { useEffect, useRef, useState } from 'react'
import Greeting from './Greeting'
import Icon from './Icon'
import Reply from './Reply'
import RunBlock from './RunBlock'
import { money } from './runview'
import type { Item, Run, RunState } from './store'
import { useNow } from './useNow'

type Props = { items: Item[]; empty?: 'new' | 'loading' | 'failed'; starting?: boolean; runState: (run: Run) => RunState; runCap: (run: Run) => number | null; onStop: () => void; onOpenShot?: (runId: string, index: number) => void }

const NEAR_END = 48 // px from the end that still counts as "reading the end"
const FRESH_MS = 5000 // a message that is newer than the thread's own opening (less this) slides in; one read back from history does not

type YourMessage = Extract<Item, { kind: 'message' }>
type Row = { key: string; yours: YourMessage } | { key: string; parts: Item[]; working?: boolean }

/** The thread: each of your messages is a row; everything the assistant says in answer (its run, the words as they are written, the reply) is one row. */
function rowsOf(items: Item[], starting: boolean): Row[] {
  const rows: Row[] = []
  let anchor = 'start' // the key of an answer is the message it answers, so the row survives the words becoming the finished reply
  for (const item of items) {
    if (item.kind === 'message' && item.message.role === 'user') {
      anchor = item.message.id
      rows.push({ key: anchor, yours: item })
      continue
    }
    const last = rows.at(-1)
    if (last && 'parts' in last) last.parts.push(item)
    else rows.push({ key: `answer-${anchor}`, parts: [item] })
  }
  if (starting && rows.at(-1) && !('parts' in rows.at(-1)!)) rows.push({ key: `answer-${anchor}`, parts: [], working: true })
  return rows
}

/** ChatGPT's copy button under a reply: the icon turns to a tick for a moment once the text is on the clipboard. */
function Copy({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () =>
    navigator.clipboard?.writeText(text).then(() => {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    })
  return (
    <button className="btn btn--icon btn--ghost" type="button" aria-label={copied ? 'Copied' : 'Copy reply'} title={copied ? 'Copied' : 'Copy'} onClick={copy}>
      <Icon name={copied ? 'check' : 'copy'} />
    </button>
  )
}

export default function ChatView({ items, empty = 'new', starting = false, runState, runCap, onStop, onOpenShot }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const thread = useRef<HTMLDivElement>(null)
  const atEnd = useRef(true)
  const [opened] = useState(() => Date.now())
  const [away, setAway] = useState(false) // scrolled up from the end: show the way back down
  const now = useNow(items.some((i) => i.kind === 'run' && runState(i.run) === 'running'))
  const toEnd = () => {
    if (box.current) box.current.scrollTop = box.current.scrollHeight
  }
  const hasItems = items.length > 0
  // A new message or reply: show it, unless the reader is up in the thread reading (their own message always counts as "go to the end").
  const newest = items.at(-1)
  const mine = newest?.kind === 'message' && newest.message.role === 'user'
  useEffect(() => {
    if (atEnd.current || mine) {
      atEnd.current = true
      toEnd()
    }
  }, [items.length, mine])
  // Anything that changes the height after that (a step arriving, a page loading, the composer getting taller, the window resizing)
  // must not push the last lines out of view, so while the reader is at the end the view stays at the end.
  useEffect(() => {
    if (!box.current || !thread.current || typeof ResizeObserver === 'undefined') return // jsdom has none
    const watch = new ResizeObserver(() => atEnd.current && toEnd())
    watch.observe(box.current)
    watch.observe(thread.current)
    return () => watch.disconnect()
  }, [hasItems])

  if (!hasItems) {
    return (
      <div className="thread">
        {empty === 'new' ? (
          <Greeting />
        ) : (
          <div className="scroll">
            <p className="empty">{empty === 'loading' ? 'Loading…' : 'Nothing to show yet. Use “Retry now” above.'}</p>
          </div>
        )}
      </div>
    )
  }
  const jump = () => {
    const el = box.current
    if (!el) return
    const calm = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? true
    if (el.scrollTo) el.scrollTo({ top: el.scrollHeight, behavior: calm ? 'auto' : 'smooth' })
    else el.scrollTop = el.scrollHeight
  }
  return (
    <div className="thread">
      <div
        className="scroll"
        ref={box}
        onScroll={(e) => {
          const el = e.currentTarget
          atEnd.current = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_END
          setAway(!atEnd.current)
        }}
        // opening or closing a run is the reader steering the view: do not pull them to the end
        onClickCapture={(e) => {
          if ((e.target as Element).closest('summary')) atEnd.current = false
        }}
      >
        <div className="col" ref={thread}>
          {rowsOf(items, starting).map((row) => {
            if ('yours' in row) {
              const { message } = row.yours
              return (
                <p key={row.key} className={`user${Date.parse(message.at) > opened - FRESH_MS ? ' user--new' : ''}`}>
                  {message.text}
                  {row.yours.queued && <span className="tag">Queued</span>}
                </p>
              )
            }
            return (
              <div key={row.key} className="turn">
                  {row.working && (
                    <p className="working">
                      <span className="shimmer">Working…</span>
                    </p>
                  )}
                  {row.parts.map((item) => {
                    if (item.kind === 'run') return <RunBlock key={item.run.id} run={item.run} state={runState(item.run)} cap={runCap(item.run)} now={now} onStop={onStop} onOpenShot={onOpenShot && ((i) => onOpenShot(item.run.id, i))} />
                    if (item.kind === 'stream') {
                      return (
                        <div key={`stream-${item.runId}`} className="reply">
                          <Reply text={item.text} />
                        </div>
                      )
                    }
                    const { message } = item
                    return (
                      <div key={message.id} className="reply">
                        <Reply text={message.text} />
                        <div className="actions">
                          <Copy text={message.text} />
                          {message.cost_usd !== null && <small className="muted">{money(message.cost_usd)}</small>}
                        </div>
                      </div>
                    )
                  })}
              </div>
            )
          })}
        </div>
      </div>
      <button className={`jump${away ? ' is-on' : ''}`} type="button" aria-label="Scroll to the end" tabIndex={away ? 0 : -1} aria-hidden={!away} onClick={jump}>
        <Icon name="arrowdown" size={12} />
      </button>
    </div>
  )
}
