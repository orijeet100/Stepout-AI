import './App.css'
import ChatView from './ChatView'
import Composer from './Composer'
import Sidebar from './Sidebar'
import { chatList, runCap, runState, timeline } from './store'
import { useBackend } from './useBackend'

export default function App() {
  const { state, send, stop, newChat, select, retry } = useBackend()
  const { selected, conn, attempt, error } = state
  const chats = chatList(state)
  const current = chats.find((c) => c.id === selected)
  // After the first failure, "connecting" is just the next attempt: keep saying "reconnecting" instead of flickering.
  const banner =
    conn === 'open'
      ? error
      : attempt === 0
        ? 'Connecting…'
        : `Disconnected. Reconnecting${attempt > 1 ? ` (attempt ${attempt})` : ''}…`
  return (
    <div className="app">
      <Sidebar chats={chats} selected={selected} onSelect={select} onNew={newChat} />
      <main className="main">
        <header className="head">
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
        <ChatView items={selected ? timeline(state, selected) : []} runState={(r) => runState(state, r)} runCap={(r) => runCap(state, r)} onStop={stop} />
        <Composer online={conn === 'open'} busy={state.status.state === 'running'} onSend={send} />
      </main>
    </div>
  )
}
