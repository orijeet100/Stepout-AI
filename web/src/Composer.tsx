import { useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import Icon from './Icon'
import Suggestions from './Suggestions'

type Props = { online: boolean; busy: boolean; suggest?: boolean; onSend: (text: string) => void }

export default function Composer({ online, busy, suggest = false, onSend }: Props) {
  const [text, setText] = useState('')
  const box = useRef<HTMLTextAreaElement>(null)
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
    <div className="dock">
      {suggest && <Suggestions online={online} onPick={onSend} />}
      <form className="composer" onSubmit={submit} onClick={(e) => !(e.target as Element).closest('button') && box.current?.focus()}>
        <textarea
          ref={box}
          id="message"
          aria-label="Message"
          rows={1}
          maxLength={20_000}
          value={text}
          placeholder={busy ? 'Ask anything… (queued while a run is active)' : 'Ask anything…'}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <div className="composer__foot">
          <button className="send" type="submit" aria-label="Send" disabled={!online || !text.trim()}>
            <Icon name="send" />
          </button>
        </div>
      </form>
    </div>
  )
}
