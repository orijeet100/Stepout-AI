import { useState } from 'react'
import Icon from './Icon'
import { liveSrc, safeHref, shotSrc, type Shot } from './runview'

/** The address of a page as the browser reported it: a link only if it is a real web address, otherwise plain text. */
export function PageAddress({ url }: { url: string | null }) {
  if (!url) return null
  const href = safeHref(url)
  return href ? (
    <a className="page__url" href={href} target="_blank" rel="noopener noreferrer">{url}</a>
  ) : (
    <span className="page__url">{url}</span>
  )
}

/** A saved screenshot. If it cannot be shown (no such file, an address that is not ours) a placeholder says so: never a broken image. */
export function ShotImage({ shot, className }: { shot: Shot; className?: string }) {
  const [bad, setBad] = useState(false)
  const src = shotSrc(shot.path)
  if (!src || bad) {
    return (
      <div className={`shot-missing${className ? ` ${className}` : ''}`} role="img" aria-label="Screenshot unavailable">
        <Icon name="image" size={20} />
        <span>Screenshot unavailable</span>
      </div>
    )
  }
  return <img className={className} src={src} alt={`Screenshot of ${shot.title ?? 'the page'}`} loading="lazy" onError={() => setBad(true)} />
}

type PanelProps = { runId: string; live: boolean; shots: Shot[]; onOpen?: (index: number) => void }

/**
 * The Assistant's browser in a Run: live while the Run runs and has a Browser step (view only: nothing here sends input
 * back), the last saved screenshot once it has ended or the live stream is gone. The caption is the page's title and
 * address from the latest `shot` event.
 */
export function BrowserPanel({ runId, live, shots, onOpen }: PanelProps) {
  const [failed, setFailed] = useState(false) // the stream answered 404 or broke: stop asking, show the last screenshot
  const stream = live && !failed ? liveSrc(runId) : null
  const last = shots.at(-1)
  if (!stream && !last) return live ? <p className="browser__empty muted">No page to show yet.</p> : null
  return (
    <figure className="browser">
      <figcaption className="browser__bar">
        {stream ? (
          <span className="browser__badge is-live" title="View only: nothing you do here reaches the browser">
            <span className="dot dot--running" aria-hidden="true" /> Live
          </span>
        ) : (
          <span className="browser__badge">Last page</span>
        )}
        <span className="browser__title">{last?.title ?? (stream ? 'Opening page…' : '')}</span>
        <PageAddress url={last?.url ?? null} />
      </figcaption>
      <div className="browser__view">
        {stream ? (
          <img className="browser__live" src={stream} alt="Live view of the Assistant's browser. View only." onError={() => setFailed(true)} />
        ) : onOpen ? (
          <button type="button" className="browser__last" onClick={() => onOpen(shots.length - 1)} aria-label={`Open screenshot: ${last!.title ?? 'the page'}`}>
            <ShotImage key={last!.path} shot={last!} />
          </button>
        ) : (
          <ShotImage key={last!.path} shot={last!} />
        )}
      </div>
    </figure>
  )
}
