import Icon from './Icon'
import type { Chat } from './protocol'
import { plain, type ChatState } from './store'

type Props = { chats: (Chat & { state: ChatState })[]; selected: string | null; onSelect: (id: string) => void; onNew: () => void }

export default function Sidebar({ chats, selected, onSelect, onNew }: Props) {
  return (
    <aside className="side" aria-label="Chats">
      <div className="brand">
        <strong>Stepout</strong>
        <button className="btn btn--icon" type="button" aria-label="New chat" onClick={onNew}>
          <Icon name="plus" />
        </button>
      </div>
      <nav>
        {chats.length === 0 ? (
          <p className="muted side__empty">No chats yet.</p>
        ) : (
          <ul className="chats">
            {chats.map((c) => (
              <li key={c.id}>
                <button type="button" className="chat" aria-current={c.id === selected ? 'true' : undefined} onClick={() => onSelect(c.id)}>
                  <span className="chat__title">{c.title || 'New chat'}</span>
                  <span className="chat__prev">{plain(c.preview)}</span>
                  {c.state === 'running' && <span className="dot dot--running" role="img" aria-label="running" />}
                  {c.state === 'queued' && (
                    <span className="chat__queued" role="img" aria-label="queued">
                      <Icon name="clock" size={14} />
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </nav>
    </aside>
  )
}
