import { useEffect, useRef } from 'react'
import Reply from './Reply'
import RunBlock from './RunBlock'
import type { Item, Run, RunState } from './store'

type Props = { items: Item[]; runState: (run: Run) => RunState; onStop: () => void }

export default function ChatView({ items, runState, onStop }: Props) {
  const end = useRef<HTMLDivElement>(null)
  const last = items.at(-1)
  const growth = last?.kind === 'run' ? last.run.events.length : items.length
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
        {items.map((item) =>
          item.kind === 'run' ? (
            <RunBlock key={item.run.id} run={item.run} state={runState(item.run)} onStop={onStop} />
          ) : item.message.role === 'user' ? (
            <p key={item.message.id} className="user">{item.message.text}</p>
          ) : (
            <div key={item.message.id} className="reply">
              <Reply text={item.message.text} />
              {item.message.cost_usd !== null && <small className="muted">${item.message.cost_usd.toFixed(4)}</small>}
            </div>
          ),
        )}
        <div ref={end} />
      </div>
    </div>
  )
}
