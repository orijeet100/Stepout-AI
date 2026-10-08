import { useEffect, useRef } from 'react'
import Reply from './Reply'
import RunBlock from './RunBlock'
import { money } from './runview'
import type { Item, Run, RunState } from './store'
import { useNow } from './useNow'

type Props = { items: Item[]; runState: (run: Run) => RunState; runCap: (run: Run) => number | null; onStop: () => void; onOpenShot?: (runId: string, index: number) => void }

export default function ChatView({ items, runState, runCap, onStop, onOpenShot }: Props) {
  const end = useRef<HTMLDivElement>(null)
  const last = items.at(-1)
  const growth = last?.kind === 'run' ? last.run.events.length : items.length
  const now = useNow(items.some((i) => i.kind === 'run' && runState(i.run) === 'running'))
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: 'end' }) // jsdom has no scrollIntoView
  }, [items.length, growth])

  if (items.length === 0) {
    return (
      <div className="scroll">
        <p className="empty">Ask something. It plans the steps, shows each one as it happens, and tells you what it cost.</p>
      </div>
    )
  }
  return (
    <div className="scroll">
      <div className="col">
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
        <div ref={end} />
      </div>
    </div>
  )
}
