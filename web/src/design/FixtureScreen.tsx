import { useEffect, useRef, type KeyboardEvent } from 'react'
import Markdown from 'react-markdown'
import Icon from './Icon.tsx'
import { allShots, chats, finished, running, type PlanItem, type Run, type Shot, type StepLine, type Verdict } from './fixture.ts'
import './fixture.css'

const money = (n: number, digits = 4) => `$${n.toFixed(digits)}`

/** A stand-in for a 1000×700 page screenshot: three fixed layouts, always light like a real page. */
function ShotArt({ shot }: { shot: Shot }) {
  const body = [
    <>
      <rect x="60" y="150" width="880" height="190" rx="16" fill="#e8ecf8" />
      {[0, 1, 2].map((i) => <rect key={i} x={60 + i * 300} y="380" width="280" height="220" rx="12" fill="#f1f3f7" />)}
    </>,
    <>
      {[0, 1, 2, 3].map((i) => (
        <g key={i}>
          <rect x="60" y={140 + i * 130} width="150" height="100" rx="10" fill="#e9eef3" />
          <rect x="240" y={150 + i * 130} width="420" height="22" rx="6" fill="#cfd6df" />
          <rect x="240" y={190 + i * 130} width="260" height="16" rx="6" fill="#e3e8ee" />
        </g>
      ))}
    </>,
    <>
      <rect x="60" y="140" width="520" height="440" rx="14" fill="#eef0f4" />
      <rect x="620" y="140" width="320" height="30" rx="8" fill="#cfd6df" />
      {[0, 1, 2, 3, 4].map((i) => <rect key={i} x="620" y={196 + i * 48} width={300 - i * 24} height="16" rx="6" fill="#e3e8ee" />)}
    </>,
  ][shot.art]
  return (
    <svg viewBox="0 0 1000 700" role="img" aria-label={`Screenshot: ${shot.title}`} className="fx-art">
      <rect width="1000" height="700" fill="#ffffff" />
      <rect width="1000" height="70" fill="#f5f6f8" />
      <rect x="60" y="24" width="120" height="22" rx="6" fill="#c3cad6" />
      {body}
    </svg>
  )
}

function VerdictBadge({ v }: { v: Verdict }) {
  const label = { allow: 'Allowed', refuse: 'Refused', ask: 'Asks you' }[v]
  const icon = { allow: 'check', refuse: 'ban', ask: 'ask' }[v] as 'check' | 'ban' | 'ask'
  return (
    <span className={`fx-verdict fx-verdict--${v}`}>
      <Icon name={icon} size={13} /> {label}
    </span>
  )
}

function PlanGlyph({ status }: { status: PlanItem['status'] }) {
  return (
    <span className={`fx-glyph fx-glyph--${status}`} role="img" aria-label={status}>
      {status === 'done' && <Icon name="check" size={12} />}
      {status === 'failed' && <Icon name="x" size={12} />}
    </span>
  )
}

function Meter({ label, now, max, text }: { label: string; now: number; max: number; text: string }) {
  return (
    <div className="fx-meter">
      <div className="fx-meter__head"><span>{label}</span><span>{text}</span></div>
      <div className="fx-meter__bar" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={max} aria-valuenow={now}>
        <span style={{ width: `${Math.min(100, (now / max) * 100)}%` }} />
      </div>
    </div>
  )
}

function RunView({ run, shotBase, onShot }: { run: Run; shotBase: number; onShot: (i: number) => void }) {
  const live = run.state === 'running'
  const done = run.plan.filter((p) => p.status === 'done').length
  const summary = live
    ? `Working… step ${Math.min(done + 1, run.plan.length)} of ${run.plan.length}`
    : `${run.steps.length} steps · ${money(run.cost)} · ${run.elapsed}`
  return (
    <details className={`fx-run${live ? ' fx-run--live' : ''}`} open>
      <summary>
        <span className={`fx-state fx-state--${run.state}`} aria-hidden="true" />
        <span className="fx-run__sum">{summary}</span>
        <span className="fx-run__chev"><Icon name="down" size={16} /></span>
      </summary>
      <div className="fx-run__body">
        {live && (
          <div className="fx-progress">
            <Meter label="Plan" now={done} max={run.plan.length} text={`${done} of ${run.plan.length} steps`} />
            <Meter label="Budget" now={run.cost} max={run.cap} text={`${money(run.cost)} of ${money(run.cap, 2)}`} />
            <div className="fx-progress__row">
              <span className="fx-muted">Elapsed {run.elapsed}</span>
              <button className="fx-btn fx-btn--stop" type="button"><Icon name="stop" size={14} /> Stop</button>
            </div>
          </div>
        )}
        <ol className="fx-plan" aria-label="Plan">
          {run.plan.map((p, i) => (
            <li key={i} className={`fx-plan__${p.status}`}>
              <PlanGlyph status={p.status} />
              <span className="fx-chip">{p.role}</span> {p.goal}
            </li>
          ))}
        </ol>
        <ul className="fx-steps" aria-label="Steps">
          {run.steps.map((s: StepLine, i) => (
            <li key={i}>
              <span className="fx-chip">{s.role}</span>
              <span className="fx-steps__line">{s.line}{s.running && <span className="fx-ellipsis" aria-label="in progress" />}</span>
              <VerdictBadge v={s.verdict} />
              <span className="fx-steps__cost">{s.cost > 0 ? money(s.cost) : ''}</span>
              {s.note && <span className="fx-steps__note">{s.note}</span>}
            </li>
          ))}
        </ul>
        {run.shots.length > 0 && (
          <div className="fx-shots">
            {run.shots.map((s, i) => (
              <button key={i} type="button" className="fx-shot" onClick={() => onShot(shotBase + i)} aria-label={`Open screenshot: ${s.title}`}>
                <ShotArt shot={s} />
                <span className="fx-shot__cap">{s.title}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </details>
  )
}

function Viewer({ index, onIndex, onClose }: { index: number | null; onIndex: (i: number) => void; onClose: () => void }) {
  const dlg = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const d = dlg.current
    if (!d) return
    if (index !== null && !d.open) {
      d.showModal()
      d.querySelector('button')?.focus() // the close button, not the URL link the browser would pick
    }
    if (index === null && d.open) d.close()
  }, [index])
  const shot = index === null ? null : allShots[index]
  const step = (by: number) => index !== null && onIndex((index + by + allShots.length) % allShots.length)
  const keys = (e: KeyboardEvent) => {
    if (e.key === 'ArrowLeft') step(-1)
    if (e.key === 'ArrowRight') step(1)
  }
  return (
    <dialog ref={dlg} className="fx-viewer" aria-label="Screenshot viewer" onClose={onClose} onKeyDown={keys} onClick={(e) => e.target === dlg.current && onClose()}>
      {shot && (
        <div className="fx-viewer__panel">
          <header>
            <div>
              <h2>{shot.title}</h2>
              <a href={shot.url} target="_blank" rel="noopener noreferrer">{shot.url}</a>
            </div>
            <button className="fx-btn fx-btn--icon" type="button" onClick={onClose} aria-label="Close viewer"><Icon name="x" /></button>
          </header>
          <ShotArt shot={shot} />
          <footer>
            <button className="fx-btn" type="button" onClick={() => step(-1)}><Icon name="left" /> Previous</button>
            <span className="fx-muted">{index! + 1} of {allShots.length}</span>
            <button className="fx-btn" type="button" onClick={() => step(1)}>Next <Icon name="right" /></button>
          </footer>
        </div>
      )}
    </dialog>
  )
}

export default function FixtureScreen({ viewer, onViewer }: { viewer: number | null; onViewer: (i: number | null) => void }) {
  return (
    <div className="fx">
      <aside className="fx-side" aria-label="Chats">
        <div className="fx-brand">
          <strong>Stepout</strong>
          <button className="fx-btn fx-btn--icon" type="button" aria-label="New chat"><Icon name="plus" /></button>
        </div>
        <nav>
          <ul className="fx-chats">
            {chats.map((c, i) => (
              <li key={c.id}>
                <button type="button" className="fx-chat" aria-current={i === 0 ? 'true' : undefined}>
                  <span className="fx-chat__title">{c.title}</span>
                  <span className="fx-chat__prev">{c.preview}</span>
                  {c.state === 'running' && <span className="fx-state fx-state--running" role="img" aria-label="running" />}
                  {c.state === 'queued' && <span className="fx-chat__queued"><Icon name="clock" size={14} /><span className="fx-sr">queued</span></span>}
                </button>
              </li>
            ))}
          </ul>
        </nav>
      </aside>

      <main className="fx-main">
        <header className="fx-head">
          <h1>Top events on Luma this weekend</h1>
          <span className="fx-pill"><span className="fx-state fx-state--running" aria-hidden="true" /> Running</span>
        </header>
        <div className="fx-scroll">
          <div className="fx-col">
            <p className="fx-user">{finished.request}</p>
            <RunView run={finished} shotBase={0} onShot={onViewer} />
            <div className="fx-reply">
              <Markdown components={{ a: (p) => <a href={p.href} target="_blank" rel="noopener noreferrer">{p.children}</a> }}>{finished.reply}</Markdown>
              <small className="fx-muted">{money(finished.cost)}</small>
            </div>
            <p className="fx-user">{running.request}</p>
            <RunView run={running} shotBase={finished.shots.length} onShot={onViewer} />
          </div>
        </div>
        <form className="fx-composer" onSubmit={(e) => e.preventDefault()}>
          <textarea aria-label="Message" rows={1} placeholder="Message — queued while a run is active" />
          <button className="fx-btn fx-btn--primary fx-btn--icon" type="submit" aria-label="Send"><Icon name="send" /></button>
        </form>
      </main>

      <Viewer index={viewer} onIndex={onViewer} onClose={() => onViewer(null)} />
    </div>
  )
}
