import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import Composer from './Composer'

const setup = (props: Partial<Parameters<typeof Composer>[0]> = {}) => {
  const onSend = vi.fn()
  render(<Composer online busy={false} onSend={onSend} {...props} />)
  return { onSend, box: screen.getByLabelText('Message') as HTMLTextAreaElement }
}
const type = (box: HTMLTextAreaElement, text: string) => fireEvent.change(box, { target: { value: text } })

describe('Composer', () => {
  it('Enter sends the trimmed text and clears the box', () => {
    const { onSend, box } = setup()
    type(box, '  hello  ')
    fireEvent.keyDown(box, { key: 'Enter' })
    expect(onSend).toHaveBeenCalledExactlyOnceWith('hello')
    expect(box.value).toBe('')
  })

  it('Shift+Enter is a newline, not a send', () => {
    const { onSend, box } = setup()
    type(box, 'a')
    expect(fireEvent.keyDown(box, { key: 'Enter', shiftKey: true })).toBe(true) // not default-prevented: the browser inserts the newline
    expect(onSend).not.toHaveBeenCalled()
  })

  it('Enter while an input method is composing does not send', () => {
    const { onSend, box } = setup()
    type(box, 'にほん')
    fireEvent.keyDown(box, { key: 'Enter', isComposing: true })
    expect(onSend).not.toHaveBeenCalled()
  })

  it('sends nothing when empty or when the connection is down', () => {
    const empty = setup()
    fireEvent.keyDown(empty.box, { key: 'Enter' })
    type(empty.box, '   ')
    fireEvent.keyDown(empty.box, { key: 'Enter' })
    expect(empty.onSend).not.toHaveBeenCalled()
  })

  it('is disabled offline, and says messages queue while a run is active', () => {
    const offline = setup({ online: false })
    type(offline.box, 'hi')
    expect((screen.getByLabelText('Send') as HTMLButtonElement).disabled).toBe(true)
    fireEvent.keyDown(offline.box, { key: 'Enter' })
    expect(offline.onSend).not.toHaveBeenCalled()
  })

  it('placeholder tells you a message will queue while a run is active', () => {
    const { box } = setup({ busy: true })
    expect(box.placeholder).toMatch(/queued/)
  })

  it('offers no suggestions unless asked to', () => {
    setup()
    expect(screen.queryByRole('group', { name: 'Suggested questions' })).toBeNull()
  })

  it('offers four suggested questions, and a click sends that text as it is', () => {
    const { onSend } = setup({ suggest: true })
    const group = screen.getByRole('group', { name: 'Suggested questions' })
    expect(group.querySelectorAll('button')).toHaveLength(4)
    fireEvent.click(screen.getByRole('button', { name: "What's the news in New York today?" }))
    expect(onSend).toHaveBeenCalledExactlyOnceWith("What's the news in New York today?")
  })

  it('cannot send a suggestion while the connection is down', () => {
    const { onSend } = setup({ suggest: true, online: false })
    const first = screen.getAllByRole('button').find((b) => b.className.includes('suggestion')) as HTMLButtonElement
    expect(first.disabled).toBe(true)
    fireEvent.click(first)
    expect(onSend).not.toHaveBeenCalled()
  })
})
