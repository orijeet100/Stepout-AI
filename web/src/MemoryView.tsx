import { useCallback, useEffect, useState, type FormEvent } from 'react'
import Icon from './Icon'
import { parseMemory, type MemoryEntry } from './protocol'

const TITLES: Record<MemoryEntry['kind'], string> = {
  persona: 'Persona: lines you wrote',
  fact: 'Learned from what you said',
  history: 'Earlier tasks',
}
const ORDER: MemoryEntry['kind'][] = ['persona', 'fact', 'history']

async function read(): Promise<{ status: 'ready' | 'off' | 'failed'; entries: MemoryEntry[] }> {
  try {
    const r = await fetch('/api/memory')
    if (r.status === 404) return { status: 'off', entries: [] } // memory is switched off (or this backend has none)
    if (!r.ok) throw new Error(String(r.status))
    return { status: 'ready', entries: parseMemory(await r.json()) }
  } catch {
    return { status: 'failed', entries: [] }
  }
}

/** What the assistant keeps about the User: read from the backend; each entry can be edited or forgotten, and a line can be added to the Persona file. */
export default function MemoryView({ onClose }: { onClose: () => void }) {
  const [entries, setEntries] = useState<MemoryEntry[]>([])
  const [status, setStatus] = useState<'loading' | 'ready' | 'off' | 'failed'>('loading')
  const [line, setLine] = useState('')
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    const got = await read()
    setStatus(got.status)
    if (got.status === 'ready') setEntries(got.entries)
  }, [])
  useEffect(() => {
    let live = true
    void read().then((got) => {
      if (!live) return
      setStatus(got.status)
      if (got.status === 'ready') setEntries(got.entries)
    })
    return () => {
      live = false
    }
  }, [])

  async function keep(e: FormEvent) {
    e.preventDefault()
    const text = line.trim()
    if (!text) return
    try {
      const r = await fetch('/api/memory', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) })
      if (!r.ok) throw new Error(String(r.status))
      setLine('')
      setError(null)
      await load()
    } catch {
      setError('Could not keep that.')
    }
  }

  const [editing, setEditing] = useState<{ id: string; text: string } | null>(null)
  async function save(e: FormEvent) {
    e.preventDefault()
    const text = editing?.text.trim()
    if (!editing || !text) return
    try {
      const r = await fetch(`/api/memory/${encodeURIComponent(editing.id)}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) })
      if (!r.ok) throw new Error(String(r.status))
      setEditing(null)
      setError(null)
      await load()
    } catch {
      setError('Could not save that.')
    }
  }

  async function forget(id: string) {
    try {
      const r = await fetch(`/api/memory/${encodeURIComponent(id)}`, { method: 'DELETE' })
      if (!r.ok && r.status !== 404) throw new Error(String(r.status))
      setError(null)
      await load()
    } catch {
      setError('Could not forget that.')
    }
  }

  return (
    <section className="memory" aria-label="Memory">
      <div className="memory__head">
        <h2>Memory</h2>
        <button className="btn btn--icon btn--ghost" type="button" aria-label="Close Memory" title="Close" onClick={onClose}>
          <Icon name="x" />
        </button>
      </div>
      {status === 'loading' && <p className="memory__note">Loading…</p>}
      {status === 'failed' && (
        <p className="memory__note">
          Could not read Memory. <button className="btn" type="button" onClick={() => void load()}>Try again</button>
        </p>
      )}
      {status === 'off' && <p className="memory__note">Memory is off (STEPOUT_MEMORY=off), so nothing is kept or recalled.</p>}
      {status === 'ready' && (
        <>
          <p className="memory__note">What the assistant knows about you going into a task. It is data, never an instruction. Persona is a file you can also edit by hand.</p>
          <form className="memory__add" onSubmit={keep}>
            <input type="text" value={line} maxLength={500} placeholder="Add a line to your Persona (for example: My CV is in D:\Career)" aria-label="Add a line to your Persona" onChange={(e) => setLine(e.target.value)} />
            <button className="btn" type="submit" disabled={!line.trim()}>Keep</button>
          </form>
          {error && <p className="memory__error" role="alert">{error}</p>}
          {entries.length === 0 ? (
            <p className="memory__note">Nothing is kept yet.</p>
          ) : (
            ORDER.map((kind) => {
              const group = entries.filter((e) => e.kind === kind)
              return group.length === 0 ? null : (
                <section key={kind} className="memory__group" aria-label={TITLES[kind]}>
                  <p className="group__label" aria-hidden="true">{TITLES[kind]}</p>
                  <ul>
                    {group.map((e) =>
                      editing?.id === e.id ? (
                        <li key={e.id}>
                          <form className="memory__edit" onSubmit={save} onKeyDown={(k) => k.key === 'Escape' && setEditing(null)}>
                            <input type="text" value={editing.text} maxLength={500} aria-label={`Edit: ${e.text}`} autoFocus onChange={(c) => setEditing({ id: e.id, text: c.target.value })} />
                            <button className="btn btn--primary" type="submit" disabled={!editing.text.trim()}>Save</button>
                            <button className="btn btn--ghost" type="button" onClick={() => setEditing(null)}>Cancel</button>
                          </form>
                        </li>
                      ) : (
                        <li key={e.id}>
                          <span className="memory__text">
                            {e.text}
                            {e.source && <span className="memory__source">{e.source}</span>}
                          </span>
                          <button className="btn btn--icon btn--ghost" type="button" aria-label={`Edit: ${e.text}`} title="Edit" onClick={() => setEditing({ id: e.id, text: e.text })}>
                            <Icon name="pencil" size={14} />
                          </button>
                          <button className="btn btn--icon btn--ghost" type="button" aria-label={`Forget: ${e.text}`} title="Forget" onClick={() => void forget(e.id)}>
                            <Icon name="trash" size={14} />
                          </button>
                        </li>
                      ),
                    )}
                  </ul>
                </section>
              )
            })
          )}
        </>
      )}
    </section>
  )
}
