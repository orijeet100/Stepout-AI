import { useState } from 'react'
import Icon from './Icon'
import { stepCost, type ToolCall as Call } from './runview'

/** The state at the end of a tool call's line: a spinner while it runs, a tick when it ran, a cross when it was refused or failed. */
export function StateIcon({ state }: { state: Call['state'] | 'stopped' }) {
  if (state === 'running') return <span className="spin"><Icon name="loader" size={14} /></span>
  if (state === 'refused' || state === 'failed') return <span className="is-err"><Icon name="x" size={14} /></span>
  if (state === 'stopped') return <span className="is-warn"><Icon name="ban" size={14} /></span>
  return <span className="is-ok"><Icon name="check" size={14} /></span>
}

const SAID: Record<Call['state'], string> = { running: 'running', done: 'done', repeat: 'not run again', refused: 'refused', failed: 'failed' }

/** assistant-ui's Agent Tool: a quiet line (chevron, what it did, the argument in a chip, its state) that opens onto the request and the result. */
export default function ToolCall({ call }: { call: Call }) {
  const [open, setOpen] = useState(false)
  const more = !!(call.request || call.result)
  const label = call.state === 'running' ? call.doing : call.label
  return (
    <div className={`tool${call.note ? ' tool--note' : ''}`} data-state={call.state}>
      <button className="tool__trigger" type="button" aria-expanded={more ? open : undefined} disabled={!more} onClick={() => setOpen(!open)}>
        <span className="tool__chev" aria-hidden="true">{more && <Icon name="right" size={14} />}</span>
        <span className={`tool__label${call.state === 'running' ? ' shimmer' : ''}`}>{label}</span>
        {call.arg && <span className="tool__arg" title={call.arg}>{call.arg}</span>}
        <span className="sr-only">{SAID[call.state]}</span>
        <span className="tool__state" aria-hidden="true"><StateIcon state={call.state} /></span>
      </button>
      {open && (
        <div className="tool__panel">
          {call.request && (
            <div className="tool__part">
              <p className="tool__cap">Request{call.cost > 0 && <span title="What the model call that asked for this cost">{stepCost(call.cost)}</span>}</p>
              <p className="tool__req">{call.request}</p>
            </div>
          )}
          {call.request && call.result && <div className="tool__rule" />}
          {call.result && (
            <div className="tool__part">
              <p className="tool__cap">Result</p>
              <p className="tool__res">{call.result}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
