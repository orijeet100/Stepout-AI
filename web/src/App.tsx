import './App.css'
import ChatView from './ChatView'
import Composer from './Composer'
import Sidebar from './Sidebar'
import { chatList, runState, timeline } from './store'
import { useBackend } from './useBackend'

export default function App() {
  const { state, send, stop, newChat, select, retry } = useBackend()
  const { selected, conn, attempt, error } = state
  const chats = chatList(state)
  const current = chats.find((c) => c.id === selected)
  const banner =
    conn === 'connecting'
      ? 'Connecting…'
      : conn === 'closed'
        ? `Disconnected. Reconnecting${attempt > 1 ? ` (attempt ${attempt})` : ''}…`
        : error
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
        <ChatView items={selected ? timeline(state, selected) : []} runState={(r) => runState(state, r)} onStop={stop} />
        <Composer online={conn === 'open'} busy={state.status.state === 'running'} onSend={send} />
      </main>
    </div>
  )
}
