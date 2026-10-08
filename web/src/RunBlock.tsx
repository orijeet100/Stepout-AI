import Icon from './Icon'
import type { Trace, Verdict } from './protocol'
import { elapsedMs, elapsedText, money, plainLine, planOf, planProgress, spent, stepCost, stepCount } from './runview'
import type { Run, RunState } from './store'

const VERDICT: Record<Verdict, { label: string; icon: 'check' | 'ban' | 'ask' }> = {
  allow: { label: 'Allowed', icon: 'check' },
  refuse: { label: 'Refused', icon: 'ban' },
  ask: { label: 'Asks you', icon: 'ask' },
}
const STATE_LABEL: Record<RunState, string> = { running: 'Working…', done: '', stopped: 'Stopped by you', overbudget: 'Over budget', failed: 'Failed' }

const stepsOf = (done: number, total: number) => `${done} of ${total} step${total === 1 ? '' : 's'}`

/** A real number against its real limit: never an estimate, so no bar without both. */
function Meter({ label, now, max, text, full }: { label: string; now: number; max: number; text: string; full?: boolean }) {
  return (
    <div className="meter">
      <div className="meter__head"><span>{label}</span><span>{text}</span></div>
      <div className="meter__bar" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={max} aria-valuenow={Math.min(now, max)} aria-valuetext={text}>
        <span className={full ? 'is-full' : undefined} style={{ width: `${Math.min(100, (now / max) * 100)}%` }} />
      </div>
    </div>
  )
}

function Line({ e }: { e: Trace }) {
  const v = e.data.verdict ? VERDICT[e.data.verdict] : null
  const text = plainLine(e.data.summary ?? '')
  return (
    <li className={e.kind === 'stop' ? 'is-stop' : undefined}>
      <span className="chip">{e.role}</span>
      <span className="steps__line" title={e.data.summary}>{text}</span>
      {v ? (
        <span className={`verdict verdict--${e.data.verdict}`}>
          <Icon name={v.icon} size={13} /> {v.label}
        </span>
      ) : (
        <span />
      )}
      <span className="steps__cost">{e.cost_usd > 0 ? stepCost(e.cost_usd) : ''}</span>
    </li>
  )
}

type Props = { run: Run; state: RunState; cap: number | null; now: number; onStop: () => void }

export default function RunBlock({ run, state, cap, now, onStop }: Props) {
  const running = state === 'running'
  const plan = planOf(run)
  const { done, total } = planProgress(plan)
  const cost = spent(run)
  const time = elapsedText(elapsedMs(run, running, now))
  const steps = stepCount(run)
  const lines = run.events.filter((e) => e.kind === 'step' || e.kind === 'return' || e.kind === 'stop')
  const summary = running
    ? ['Working…', total ? stepsOf(done, total) : '', time].filter(Boolean).join(' · ')
    : [STATE_LABEL[state], `${steps} step${steps === 1 ? '' : 's'}`, money(cost), time].filter(Boolean).join(' · ')
  return (
    <details className={`run run--${state}`} open={running}>
      <summary>
        <span className={`dot dot--${state}`} aria-hidden="true" />
        <span className="run__sum">{summary}</span>
        <span className="run__chev"><Icon name="down" /></span>
      </summary>
      <div className="run__body">
        {(total > 0 || cap) && (
          <div className="progress">
            {total > 0 && <Meter label="Plan" now={done} max={total} text={stepsOf(done, total)} />}
            {cap && <Meter label="Budget" now={cost} max={cap} text={`${money(cost)} of ${money(cap)}`} full={cost >= cap} />}
          </div>
        )}
        {running && (
          <button className="btn btn--stop" type="button" onClick={onStop}>
            <Icon name="stop" size={14} /> Stop
          </button>
        )}
        {plan.length > 0 && (
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
