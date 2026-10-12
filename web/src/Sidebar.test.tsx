import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Sidebar from './Sidebar'

const at = (days: number) => new Date(Date.now() - days * 86_400_000).toISOString()
const chat = (id: string, title: string, days: number, state: 'idle' | 'queued' | 'running' = 'idle') => ({ id, title, updated_at: at(days), preview: 'a reply', state })
const base = { listed: true, failed: false, selected: null, onSelect: () => {}, onNew: () => {} }

describe('Sidebar', () => {
  it('lists chats under their group, each a one-line row with its full title as a tooltip', () => {
    render(<Sidebar {...base} chats={[chat('a', 'Newest chat', 0), chat('b', 'Week old chat', 3), chat('c', 'Ancient chat', 90)]} />)
    expect(screen.getByRole('region', { name: 'Today' })).toBeTruthy()
    expect(screen.getByRole('region', { name: 'Last 7 days' })).toBeTruthy()
    expect(screen.getByRole('region', { name: 'Older' })).toBeTruthy()
    expect(screen.queryByRole('region', { name: 'Yesterday' })).toBeNull() // empty groups are left out
    expect(screen.getByRole('button', { name: 'Week old chat' }).getAttribute('title')).toBe('Week old chat')
  })

  it('marks the open chat, opens one on click, and starts a new chat', () => {
    const onSelect = vi.fn()
    const onNew = vi.fn()
    render(<Sidebar {...base} chats={[chat('a', 'First', 0), chat('b', 'Second', 0)]} selected="b" onSelect={onSelect} onNew={onNew} />)
    expect(screen.getByRole('button', { name: 'Second' }).getAttribute('aria-current')).toBe('true')
    expect(screen.getByRole('button', { name: 'First' }).getAttribute('aria-current')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'First' }))
    expect(onSelect).toHaveBeenCalledWith('a')
    fireEvent.click(screen.getByRole('button', { name: 'New chat' }))
    expect(onNew).toHaveBeenCalled()
  })

  it('shows a running chat and a queued one with a name for a screen reader', () => {
    render(<Sidebar {...base} chats={[chat('a', 'Busy', 0, 'running'), chat('b', 'Waiting', 0, 'queued')]} />)
    expect(screen.getByRole('img', { name: 'running' })).toBeTruthy()
    expect(screen.getByRole('img', { name: 'queued' })).toBeTruthy()
  })

  it('says why there is no list: not read yet, nothing yet, or could not be read', () => {
    const { rerender } = render(<Sidebar {...base} chats={[]} listed={false} />)
    expect(screen.getByText('Loading chats…')).toBeTruthy()
    rerender(<Sidebar {...base} chats={[]} listed />)
    expect(screen.getByText('No chats yet.')).toBeTruthy()
    rerender(<Sidebar {...base} chats={[]} listed={false} failed />)
    expect(screen.getByText('Your chats could not be loaded.')).toBeTruthy()
  })

  it('has a toggle that folds it to a rail, named for what it will do', () => {
    const onToggle = vi.fn()
    const { rerender } = render(<Sidebar {...base} chats={[chat('a', 'First', 0)]} onToggle={onToggle} />)
    fireEvent.click(screen.getByRole('button', { name: 'Collapse sidebar' }))
    expect(onToggle).toHaveBeenCalled()
    rerender(<Sidebar {...base} chats={[chat('a', 'First', 0)]} onToggle={onToggle} collapsed />)
    expect(screen.getByRole('button', { name: 'Expand sidebar' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'New chat' }).getAttribute('title')).toBe('New chat') // an icon alone in the rail: it has a tooltip
  })

  describe('managing chats', () => {
    afterEach(() => vi.restoreAllMocks())

    it('searches as you type, and says so when nothing matches', () => {
      const onQuery = vi.fn()
      const { rerender } = render(<Sidebar {...base} chats={[chat('a', 'First', 0)]} query="" onQuery={onQuery} />)
      fireEvent.change(screen.getByRole('searchbox', { name: 'Search chats' }), { target: { value: 'oslo' } })
      expect(onQuery).toHaveBeenCalledWith('oslo')
      rerender(<Sidebar {...base} chats={[]} query="oslo" onQuery={onQuery} />)
      expect(screen.getByText('No chats match.')).toBeTruthy()
    })

    it('renames a chat after asking for the new title, and does nothing if the question is dismissed', () => {
      const onRename = vi.fn()
      const ask = vi.spyOn(window, 'prompt').mockReturnValueOnce('  Oslo trip ').mockReturnValueOnce(null).mockReturnValueOnce('   ')
      render(<Sidebar {...base} chats={[chat('a', 'First', 0)]} onRename={onRename} />)
      const rename = screen.getByRole('button', { name: 'Rename chat' })
      fireEvent.click(rename)
      expect(ask).toHaveBeenCalledWith('Rename this chat', 'First')
      expect(onRename).toHaveBeenCalledWith('a', 'Oslo trip')
      fireEvent.click(rename)
      fireEvent.click(rename)
      expect(onRename).toHaveBeenCalledTimes(1) // cancelled, then blank
    })

    it('deletes only after the User confirms, and the question says it cannot be undone', () => {
      const onDelete = vi.fn()
      const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
      render(<Sidebar {...base} chats={[chat('a', 'First', 0)]} onDelete={onDelete} />)
      const del = screen.getByRole('button', { name: 'Delete chat' })
      fireEvent.click(del)
      expect(onDelete).not.toHaveBeenCalled()
      fireEvent.click(del)
      expect(onDelete).toHaveBeenCalledWith('a')
      expect(String(confirm.mock.calls[0][0])).toContain('cannot be brought back')
    })

    it('offers neither while the chat is running or waiting, since the backend would refuse', () => {
      render(<Sidebar {...base} chats={[chat('a', 'Busy', 0, 'running'), chat('b', 'Waiting', 0, 'queued')]} onRename={() => {}} onDelete={() => {}} />)
      expect(screen.queryByRole('button', { name: 'Rename chat' })).toBeNull()
      expect(screen.queryByRole('button', { name: 'Delete chat' })).toBeNull()
    })

    it('opens Memory', () => {
      const onMemory = vi.fn()
      render(<Sidebar {...base} chats={[]} onMemory={onMemory} />)
      fireEvent.click(screen.getByRole('button', { name: 'Memory' }))
      expect(onMemory).toHaveBeenCalled()
    })
  })
})
