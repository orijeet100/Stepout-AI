import Icon from './Icon'
import type { Trace, Verdict } from './protocol'
import type { Run, RunState } from './store'

// U2: the minimum that lets you watch a run (plan, steps, Stop). U3 adds the meters, elapsed time and every state.
const money = (n: number) => `$${n.toFixed(4)}`
const VERDICT: Record<Verdict, { label: string; icon: 'check' | 'ban' | 'ask' }> = {
  allow: { label: 'Allowed', icon: 'check' },
  refuse: { label: 'Refused', icon: 'ban' },
  ask: { label: 'Asks you', icon: 'ask' },
}

function summary(run: Run, state: RunState): string {
  const steps = run.events.filter((e) => e.kind === 'step').length
  const cost = run.events.reduce((sum, e) => sum + e.cost_usd, 0)
  if (state === 'running') return `Working… ${steps} step${steps === 1 ? '' : 's'} · ${money(cost)}`
  const label = state === 'stopped' ? 'Stopped · ' : state === 'failed' ? 'Failed · ' : ''
  return `${label}${steps} step${steps === 1 ? '' : 's'} · ${money(cost)}`
}

function Line({ e }: { e: Trace }) {
  const v = e.data.verdict ? VERDICT[e.data.verdict] : null
  return (
    <li className={e.kind === 'stop' ? 'is-stop' : undefined}>
      <span className="chip">{e.role}</span>
      <span className="steps__line">{e.data.summary}</span>
      {v ? (
        <span className={`verdict verdict--${e.data.verdict}`}>
          <Icon name={v.icon} size={13} /> {v.label}
        </span>
      ) : (
        <span />
      )}
      <span className="steps__cost">{e.cost_usd > 0 ? money(e.cost_usd) : ''}</span>
    </li>
  )
}

export default function RunBlock({ run, state, onStop }: { run: Run; state: RunState; onStop: () => void }) {
  const plan = run.events.findLast((e) => e.kind === 'plan')?.data.steps
  const lines = run.events.filter((e) => e.kind === 'step' || e.kind === 'return' || e.kind === 'stop')
  return (
    <details className="run" open={state === 'running'}>
      <summary>
        <span className={`dot dot--${state}`} aria-hidden="true" />
        <span className="run__sum">{summary(run, state)}</span>
        <span className="run__chev"><Icon name="down" /></span>
      </summary>
      <div className="run__body">
        {state === 'running' && (
          <button className="btn btn--stop" type="button" onClick={onStop}>
            <Icon name="stop" size={14} /> Stop
          </button>
        )}
        {plan && (
          <ol className="plan" aria-label="Plan">
            {plan.map((s, i) => (
              <li key={i} className={`plan__${s.status}`}>
                <span className={`glyph glyph--${s.status}`} role="img" aria-label={s.status}>
                  {s.status === 'done' && <Icon name="check" size={12} />}
                  {s.status === 'failed' && <Icon name="x" size={12} />}
                </span>
                <span className="chip">{s.role}</span> {s.goal}
              </li>
            ))}
          </ol>
        )}
        <ul className="steps" aria-label="Steps">
          {lines.map((e) => <Line key={e.id} e={e} />)}
        </ul>
      </div>
    </details>
  )
}
