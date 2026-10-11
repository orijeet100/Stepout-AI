import type { Ref } from 'react'
import Icon from './Icon'
import type { Chat } from './protocol'
import { chatGroups, type ChatState } from './store'

type Props = { chats: (Chat & { state: ChatState })[]; listed: boolean; failed: boolean; selected: string | null; onSelect: (id: string) => void; onNew: () => void; inert?: boolean; ref?: Ref<HTMLElement> }

export default function Sidebar({ chats, listed, failed, selected, onSelect, onNew, inert, ref }: Props) {
  return (
    <aside id="chats" ref={ref} className="side" aria-label="Chats" inert={inert}>
      <div className="side__head">
        <Icon name="message" />
        <strong>Stepout</strong>
      </div>
      <button className="newchat" type="button" aria-label="New chat" onClick={onNew}>
        <Icon name="compose" />
        <span>New chat</span>
      </button>
      <nav className="side__nav" aria-label="Your chats">
        {chats.length === 0 ? (
          <p className="side__empty">{listed ? 'No chats yet.' : failed ? 'Your chats could not be loaded.' : 'Loading chats…'}</p>
        ) : (
          chatGroups(chats).map((g) => (
            <section key={g.label} className="group" aria-label={g.label}>
              <p className="group__label" aria-hidden="true">{g.label}</p>
              <ul className="chats">
                {g.chats.map((c) => (
                  <li key={c.id}>
                    <button type="button" className="chat" title={c.title || 'New chat'} aria-current={c.id === selected ? 'true' : undefined} onClick={() => onSelect(c.id)}>
                      <span className="chat__title">{c.title || 'New chat'}</span>
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
            </section>
          ))
        )}
      </nav>
    </aside>
  )
}
