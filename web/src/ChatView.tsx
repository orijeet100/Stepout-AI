import { useEffect, useRef } from 'react'
import Reply from './Reply'
import RunBlock from './RunBlock'
import { money } from './runview'
import type { Item, Run, RunState } from './store'
import { useNow } from './useNow'

type Props = { items: Item[]; empty?: 'new' | 'loading' | 'failed'; runState: (run: Run) => RunState; runCap: (run: Run) => number | null; onStop: () => void; onOpenShot?: (runId: string, index: number) => void }

const NEAR_END = 48 // px from the end that still counts as "reading the end"

export default function ChatView({ items, empty = 'new', runState, runCap, onStop, onOpenShot }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const thread = useRef<HTMLDivElement>(null)
  const atEnd = useRef(true)
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
      <div className="scroll">
        {empty === 'loading' ? (
          <p className="empty">Loading…</p>
        ) : empty === 'failed' ? (
          <p className="empty">Nothing to show yet. Use “Retry now” above.</p>
        ) : (
          <p className="empty">Ask something. It plans the steps, shows each one as it happens, and tells you what it cost.</p>
        )}
      </div>
    )
  }
  return (
    <div
      className="scroll"
      ref={box}
      onScroll={(e) => {
        const el = e.currentTarget
        atEnd.current = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_END
      }}
      // opening or closing a run is the reader steering the view: do not pull them to the end
      onClickCapture={(e) => {
        if ((e.target as Element).closest('summary')) atEnd.current = false
      }}
    >
      <div className="col" ref={thread}>
        {items.map((item) => {
          if (item.kind === 'run') return <RunBlock key={item.run.id} run={item.run} state={runState(item.run)} cap={runCap(item.run)} now={now} onStop={onStop} onOpenShot={onOpenShot && ((i) => onOpenShot(item.run.id, i))} />
          const { message } = item
          if (message.role === 'user') {
            return (
              <p key={message.id} className="user">
                {message.text}
                {item.queued && <span className="tag">Queued</span>}
              </p>
            )
          }
          return (
            <div key={message.id} className={`reply${item.note ? ' reply--note' : ''}`}>
              {item.note && <small className="note__cap">No run was started</small>}
              <Reply text={message.text} />
              {message.cost_usd !== null && <small className="muted">{money(message.cost_usd)}</small>}
            </div>
          )
        })}
      </div>
    </div>
  )
}
