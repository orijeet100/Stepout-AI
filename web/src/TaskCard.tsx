import { useState } from 'react'
import Icon from './Icon'
import { agentName, elapsedText, type Task } from './runview'
import ToolCall, { StateIcon } from './ToolCall'

const SAID: Record<Task['state'], string> = { running: 'working', done: 'done', failed: 'failed', stopped: 'stopped' }

/** A delegated task: assistant-ui's Task card (state, goal, agent, time, the transcript of its tool calls, the result) with the Subagent
 *  list's model tag and progress bar. A tool call has no percentage, so the bar is honest: a sweep while it works, full once it ends. */
export default function TaskCard({ task, now }: { task: Task; now: number }) {
  const [toggled, setToggled] = useState<boolean | null>(null) // until the reader chooses, it is open while it works
  const open = toggled ?? task.state === 'running'
  const working = task.state === 'running'
  const end = task.endedAt ? Date.parse(task.endedAt) : working ? now : NaN
  const time = elapsedText(end - Date.parse(task.startedAt) || 0)
  return (
    <div className="task" data-state={task.state}>
      <button className="task__head" type="button" aria-expanded={open} disabled={task.calls.length === 0} onClick={() => setToggled(!open)}>
        <span className="task__state" aria-hidden="true"><StateIcon state={task.state === 'done' ? 'done' : task.state} /></span>
        <span className="sr-only">{SAID[task.state]}</span>
        <span className="task__goal">{task.goal}</span>
        <span className="mono task__agent">{agentName(task.role).toLowerCase()}</span>
        {task.model && <span className="mono">{task.model}</span>}
        <span className="mono tabular">{time}</span>
        <span className="task__chev" aria-hidden="true">{task.calls.length > 0 && <Icon name="right" size={12} />}</span>
      </button>
      {/* keyed by state: a bar that stops being indeterminate is drawn anew, so its markup is the same live and after a reload */}
      <span key={task.state} className="bar task__bar" role="progressbar" aria-label={`${task.goal} progress`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={working ? undefined : 100} aria-valuetext={SAID[task.state]}>
        <span />
      </span>
      {open && task.calls.length > 0 && (
        <div className="task__transcript">
          {task.calls.map((c) => <ToolCall key={c.id} call={c} />)}
        </div>
      )}
      {task.result && <div className="task__result">{task.result}</div>}
    </div>
  )
}
