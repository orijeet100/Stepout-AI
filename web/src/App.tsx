import { useEffect, useRef, useState } from 'react'
import './App.css'
import ChatView from './ChatView'
import Composer from './Composer'
import Icon from './Icon'
import ShotViewer from './ShotViewer'
import Sidebar from './Sidebar'
import { shotsOf } from './runview'
import { chatList, runCap, runState, timeline } from './store'
import { useBackend } from './useBackend'
import { useNarrow } from './useNarrow'

export default function App() {
  const { state, send, stop, newChat, select, retry } = useBackend()
  const { selected, conn, attempt, error } = state
  const [viewer, setViewer] = useState<{ run: string; index: number } | null>(null) // which saved page is open large
  const viewerShots = viewer && state.runs[viewer.run] ? shotsOf(state.runs[viewer.run]) : []

  // Under 900 px the chat list is a drawer. Open, it behaves like a modal: the page behind it is inert, focus moves in,
  // Esc or the scrim closes it, and focus goes back to the menu button. Closed, it cannot be tabbed into.
  const narrow = useNarrow()
  const [drawer, setDrawer] = useState(false)
  const open = narrow && drawer
  const side = useRef<HTMLElement>(null)
  const menu = useRef<HTMLButtonElement>(null)
  const wasOpen = useRef(false)
  useEffect(() => {
    if (open) side.current?.querySelector<HTMLElement>('button')?.focus()
    else if (wasOpen.current) menu.current?.focus()
    wasOpen.current = open
  }, [open])

  const chats = chatList(state)
  const waiting = selected ? !state.loaded[selected] : !state.listed && !state.draft // nothing to show yet, because it has not been read yet
  const current = chats.find((c) => c.id === selected)
  // After the first failure, "connecting" is just the next attempt: keep saying "reconnecting" instead of flickering.
  const banner =
    conn === 'open'
      ? error
      : attempt === 0
        ? 'Connecting…'
        : `Disconnected. Reconnecting${attempt > 1 ? ` (attempt ${attempt})` : ''}…`
  return (
    <div className="app" data-drawer={open ? 'open' : 'closed'} onKeyDown={(e) => e.key === 'Escape' && open && setDrawer(false)}>
      <a className="skip" href="#message" inert={open}>Skip to the message box</a>
      <Sidebar
        ref={side}
        inert={narrow && !open}
        chats={chats}
        listed={state.listed}
        failed={!!error}
        selected={selected}
        onSelect={(id) => {
          select(id)
          setDrawer(false)
        }}
        onNew={() => {
          newChat()
          setDrawer(false)
        }}
      />
      <div className="scrim" aria-hidden="true" onClick={() => setDrawer(false)} />
      <main className="main" inert={open}>
        <header className="head">
          <button ref={menu} className="btn btn--icon menu" type="button" aria-label="Chats" aria-expanded={open} aria-controls="chats" onClick={() => setDrawer(true)}>
            <Icon name="menu" />
          </button>
          <h1>{current?.title || 'New chat'}</h1>
          {current?.state === 'running' && <span className="pill"><span className="dot dot--running" aria-hidden="true" /> Running</span>}
          {current?.state === 'queued' && <span className="pill">Queued</span>}
        </header>
        {banner && (
          <div className="banner" role="status">
            <span>{banner}</span>
            {(conn !== 'open' || error) && <button className="btn" type="button" onClick={retry}>Retry now</button>}
          </div>
        )}
        <ChatView key={selected ?? 'draft'} items={selected ? timeline(state, selected) : []} empty={waiting ? (error ? 'failed' : 'loading') : 'new'} runState={(r) => runState(state, r)} runCap={(r) => runCap(state, r)} onStop={stop} onOpenShot={(run, index) => setViewer({ run, index })} />
        <Composer online={conn === 'open'} busy={state.status.state === 'running'} onSend={send} />
      </main>
      <ShotViewer
        shots={viewerShots}
        index={viewer && viewer.index < viewerShots.length ? viewer.index : null}
        onIndex={(index) => setViewer((v) => v && { ...v, index })}
        onClose={() => setViewer(null)}
      />
    </div>
  )
}
