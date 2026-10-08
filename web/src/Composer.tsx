import { useState, type FormEvent, type KeyboardEvent } from 'react'
import Icon from './Icon'

type Props = { online: boolean; busy: boolean; onSend: (text: string) => void }

export default function Composer({ online, busy, onSend }: Props) {
  const [text, setText] = useState('')
  const submit = (e?: FormEvent) => {
    e?.preventDefault()
    const t = text.trim()
    if (!t || !online) return
    onSend(t)
    setText('')
  }
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends, Shift+Enter is a newline; Enter while an input method is composing (Japanese, Chinese…) is not "send".
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }
  return (
    <form className="composer" onSubmit={submit}>
      <textarea
        aria-label="Message"
        rows={1}
        maxLength={20_000}
        value={text}
        placeholder={busy ? 'Message — queued while a run is active' : 'Message'}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
      />
      <button className="btn btn--primary btn--icon" type="submit" aria-label="Send" disabled={!online || !text.trim()}>
        <Icon name="send" />
      </button>
    </form>
  )
}
