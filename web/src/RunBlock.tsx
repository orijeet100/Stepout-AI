import { useMemo } from 'react'
import AgentPlan from './AgentPlan'
import Icon from './Icon'
import { elapsedMs, elapsedText, hasBrowserStep, money, planOf, planProgress, shotsOf, spent, workOf } from './runview'
import { BrowserPanel, ThumbStrip } from './Shots'
import type { Run, RunState } from './store'
import TaskCard from './TaskCard'
import ToolCall, { StateIcon } from './ToolCall'

const STATE_LABEL: Record<RunState, string> = { running: 'Working…', done: '', stopped: 'Stopped by you', overbudget: 'Over budget', failed: 'Failed' }

const stepsOf = (done: number, total: number) => `${done} of ${total} step${total === 1 ? '' : 's'}`

/** Spend against the Run's cap, drawn like the plan's header and bar: a real number against its real limit, so no bar without both. */
function Budget({ cost, cap }: { cost: number; cap: number }) {
  const text = `${money(cost)} of ${money(cap)}`
  const tone = cost >= cap ? 'is-full' : cost >= cap * 0.8 ? 'is-warn' : undefined
  return (
    <div className="meter">
      <div className="aplan__head"><span className="aplan__title">Budget</span><span className="mono">{text}</span></div>
      <div className="bar" role="progressbar" aria-label="Budget" aria-valuemin={0} aria-valuemax={cap} aria-valuenow={Math.min(cost, cap)} aria-valuetext={text}>
        <span className={tone} style={{ width: `${Math.min(100, (cost / cap) * 100)}%` }} />
      </div>
    </div>
  )
}

type Props = { run: Run; state: RunState; cap: number | null; now: number; onStop: () => void; onOpenShot?: (index: number) => void }

/** A Run as assistant-ui draws agent work: one line that opens onto the plan, the budget, and a card for each task the Orchestrator handed
 *  to a specialist, whose tool calls are inside it. The pages its browser saved sit under the line. */
export default function RunBlock({ run, state, cap, now, onStop, onOpenShot }: Props) {
  const running = state === 'running'
  const plan = planOf(run)
  const { done, total } = planProgress(plan)
  const cost = spent(run)
  const time = elapsedText(elapsedMs(run, running, now))
  const shots = shotsOf(run)
  const { calls, tasks } = useMemo(() => workOf(run, running), [run, running])
  const steps = [...calls, ...tasks.flatMap((t) => t.calls)].filter((c) => !c.note).length // the tool calls you can see, not every model call behind them
  const summary = running
    ? ['Working…', total ? stepsOf(done, total) : '', time].filter(Boolean).join(' · ')
    : [STATE_LABEL[state], `${steps} action${steps === 1 ? '' : 's'}`, money(cost), time].filter(Boolean).join(' · ')
  const busy = tasks.filter((t) => t.state === 'running').length
  return (
    <div className="runblock">
      <details className={`run run--${state}`} open={running}>
        <summary>
          <span className="run__chev" aria-hidden="true"><Icon name="right" size={14} /></span>
          <span className="run__sum">{summary}</span>
          <span className={`run__state run__state--${state}`} aria-hidden="true">
            <StateIcon state={running ? 'running' : state === 'done' ? 'done' : state === 'stopped' ? 'stopped' : 'failed'} />
          </span>
        </summary>
        <div className="run__body">
          {running && (
            <button className="btn btn--stop" type="button" onClick={onStop}>
              <Icon name="stop" size={14} /> Stop
            </button>
          )}
          {plan.length > 1 && <AgentPlan steps={plan} />}{/* one step is just its task card: no checklist of one */}
          {tasks.length > 0 && (
            <section className="tasks" aria-label="Tasks">
              {tasks.length > 1 && <p className="tasks__sum mono">{tasks.length} tasks{busy ? ` · ${busy} running` : ''}</p>}
              {tasks.map((t) => <TaskCard key={t.id} task={t} now={now} />)}
            </section>
          )}
          {calls.length > 0 && (
            <div className="run__calls">
              {calls.map((c) => <ToolCall key={c.id} call={c} />)}
            </div>
          )}
          {cap ? <Budget cost={cost} cap={cap} /> : null}
          <BrowserPanel runId={run.id} live={running && hasBrowserStep(run)} shots={shots} onOpen={onOpenShot} />
        </div>
      </details>
      {/* under the line, not in it: a finished run's pages are reachable without opening it */}
      {onOpenShot && <ThumbStrip shots={shots} onOpen={onOpenShot} />}
    </div>
  )
}
