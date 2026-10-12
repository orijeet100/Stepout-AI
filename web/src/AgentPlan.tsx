import Icon from './Icon'
import type { PlanStep } from './protocol'
import { agentName, planProgress } from './runview'

const SAID: Record<PlanStep['status'], string> = { done: 'done', running: 'running', pending: 'pending', failed: 'failed' }

/** assistant-ui's Agent plan: a title and "n of m", a thin progress bar, and the checklist; only the step in progress names its agent. */
export default function AgentPlan({ title = 'Plan', steps }: { title?: string; steps: PlanStep[] }) {
  const { done, total } = planProgress(steps)
  const text = `${done} of ${total} step${total === 1 ? '' : 's'}`
  return (
    <div className="aplan">
      <div className="aplan__head">
        <span className="aplan__title">{title}</span>
        <span className="mono">{done} of {total}</span>
      </div>
      <div className="bar" role="progressbar" aria-label={title} aria-valuemin={0} aria-valuemax={total} aria-valuenow={done} aria-valuetext={text}>
        <span style={{ width: `${total ? (done / total) * 100 : 0}%` }} />
      </div>
      <ul className="aplan__list" aria-label={title}>
        {steps.map((s, i) => (
          <li key={i} className={`aplan__step is-${s.status}`}>
            <span className="aplan__icon" role="img" aria-label={SAID[s.status]}>
              {s.status === 'done' && <Icon name="check" size={14} />}
              {s.status === 'running' && <span className="spin"><Icon name="loader" size={14} /></span>}
              {s.status === 'failed' && <Icon name="x" size={14} />}
              {s.status === 'pending' && <span className="aplan__dot" />}
            </span>
            <span className="aplan__text">
              {s.goal}
              {s.status === 'running' && <span className="aplan__desc">{agentName(s.role)}</span>}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
