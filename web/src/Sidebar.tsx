import type { Ref } from 'react'
import Icon from './Icon'
import type { Chat } from './protocol'
import { chatGroups, type ChatState } from './store'

type Props = {
  chats: (Chat & { state: ChatState })[]
  listed: boolean
  failed: boolean
  selected: string | null
  onSelect: (id: string) => void
  onNew: () => void
  collapsed?: boolean
  onToggle?: () => void
  inert?: boolean
  ref?: Ref<HTMLElement>
  query?: string // what is typed in the search box; the list is already only the chats that match
  onQuery?: (q: string) => void
  onRename?: (id: string, title: string) => void
  onDelete?: (id: string) => void
  onMemory?: () => void
}

export default function Sidebar({ chats, listed, failed, selected, onSelect, onNew, collapsed = false, onToggle, inert, ref, query = '', onQuery, onRename, onDelete, onMemory }: Props) {
  const searching = query.trim() !== ''
  return (
    <aside id="chats" ref={ref} className="side" aria-label="Chats" inert={inert}>
      <div className="side__head">
        <img className="logo" src="/icon.png" alt="" width={20} height={20} />
        <strong>Stepout</strong>
        {onToggle && (
          <button className="btn btn--icon btn--ghost rail" type="button" aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} onClick={onToggle}>
            <Icon name="panel" />
          </button>
        )}
      </div>
      <button className="newchat" type="button" aria-label="New chat" title={collapsed ? 'New chat' : undefined} onClick={onNew}>
        <Icon name="compose" />
        <span>New chat</span>
      </button>
      {onQuery && (
        <div className="side__tools">
          <label className="search">
            <Icon name="search" />
            <input type="search" value={query} placeholder="Search chats" aria-label="Search chats" onChange={(e) => onQuery(e.target.value)} />
          </label>
        </div>
      )}
      {onMemory && (
        <button className="newchat" type="button" aria-label="Memory" title={collapsed ? 'Memory' : 'What the assistant remembers about you'} onClick={onMemory}>
          <Icon name="brain" />
          <span>Memory</span>
        </button>
      )}
      <nav className="side__nav" aria-label="Your chats">
        {chats.length === 0 ? (
          <p className="side__empty">{searching ? 'No chats match.' : listed ? 'No chats yet.' : failed ? 'Your chats could not be loaded.' : 'Loading chats…'}</p>
        ) : (
          chatGroups(chats).map((g) => (
            <section key={g.label} className="group" aria-label={g.label}>
              <p className="group__label" aria-hidden="true">{g.label}</p>
              <ul className="chats">
                {g.chats.map((c) => (
                  <li key={c.id} className="chatrow">
                    <button type="button" className="chat" title={c.title || 'New chat'} aria-current={c.id === selected ? 'true' : undefined} onClick={() => onSelect(c.id)}>
                      <span className="chat__title">{c.title || 'New chat'}</span>
                      {c.state === 'running' && <span className="dot dot--running" role="img" aria-label="running" />}
                      {c.state === 'queued' && (
                        <span className="chat__queued" role="img" aria-label="queued">
                          <Icon name="clock" size={14} />
                        </span>
                      )}
                    </button>
                    {c.state === 'idle' && (onRename || onDelete) && (
                      // not offered while it is running or waiting: the backend refuses to delete such a chat, and a title in use should not move
                      <span className="chatrow__tools">
                        {onRename && (
                          <button
                            className="btn btn--icon btn--ghost"
                            type="button"
                            aria-label="Rename chat"
                            title="Rename"
                            onClick={() => {
                              const title = window.prompt('Rename this chat', c.title)?.trim()
                              if (title) onRename(c.id, title.slice(0, 120))
                            }}
                          >
                            <Icon name="pencil" size={14} />
                          </button>
                        )}
                        {onDelete && (
                          <button
                            className="btn btn--icon btn--ghost"
                            type="button"
                            aria-label="Delete chat"
                            title="Delete"
                            onClick={() => {
                              if (window.confirm(`Delete “${c.title || 'New chat'}”? Its messages, runs and screenshots are removed and cannot be brought back.`)) onDelete(c.id)
                            }}
                          >
                            <Icon name="trash" size={14} />
                          </button>
                        )}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          ))
        )}
      </nav>
    </aside>
  )
}
