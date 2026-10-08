import { useEffect, useRef, type KeyboardEvent } from 'react'
import Icon from './Icon'
import type { Shot } from './runview'
import { PageAddress, ShotImage } from './Shots'

type Props = { shots: Shot[]; index: number | null; onIndex: (i: number) => void; onClose: () => void }

/**
 * A saved screenshot, large: its title and address, previous and next across the Run's pages, a close button.
 * A native modal <dialog>, so the browser traps focus inside it, closes it on Esc, and puts focus back on whatever
 * opened it. Arrow keys step through the pages. View-only, like everything that shows the browser.
 */
export default function ShotViewer({ shots, index, onIndex, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const d = dialog.current
    if (!d) return
    if (index !== null && !d.open) {
      d.showModal()
      d.querySelector<HTMLButtonElement>('button[data-close]')?.focus() // start on Close, not on the page address link the browser would pick
    }
    if (index === null && d.open) d.close()
  }, [index])
  const shot = index === null ? null : (shots[index] ?? null)
  const go = (by: number) => index !== null && shots.length > 1 && onIndex((index + by + shots.length) % shots.length)
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'ArrowLeft') go(-1)
    if (e.key === 'ArrowRight') go(1)
  }
  return (
    <dialog ref={dialog} className="viewer" aria-label="Screenshot viewer" onClose={onClose} onKeyDown={onKeyDown} onClick={(e) => e.target === dialog.current && onClose()}>
      {shot && index !== null && (
        <div className="viewer__panel">
          <header>
            <div className="viewer__what">
              <h2>{shot.title ?? 'Untitled page'}</h2>
              <PageAddress url={shot.url} />
            </div>
            <button className="btn btn--icon" type="button" data-close onClick={onClose} aria-label="Close viewer">
              <Icon name="x" />
            </button>
          </header>
          <ShotImage key={shot.path} shot={shot} className="viewer__img" />
          <footer>
            <button className="btn" type="button" onClick={() => go(-1)} disabled={shots.length < 2}>
              <Icon name="left" /> Previous
            </button>
            <span className="muted" aria-live="polite">{index + 1} of {shots.length}</span>
            <button className="btn" type="button" onClick={() => go(1)} disabled={shots.length < 2}>
              Next <Icon name="right" />
            </button>
          </footer>
        </div>
      )}
    </dialog>
  )
}
