import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import MemoryView from './MemoryView'

const entries = [
  { id: 'p-3f9a1c', kind: 'persona', text: 'I live in Oslo', source: 'you wrote it in persona.md' },
  { id: 'f-1a2b3c4d', kind: 'fact', text: 'I have a dog called Mo', source: 'you said it on 2026-10-12' },
  { id: 'h-0a0b0c0d', kind: 'history', text: '2026-10-01: "weather in oslo" -> done', source: 'the outcome of a task on 2026-10-01' },
]
const reply = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))

describe('MemoryView', () => {
  let fetchMock: ReturnType<typeof vi.fn>
  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => vi.unstubAllGlobals())

  it('lists what is kept under its three headings, each entry with where it came from', async () => {
    fetchMock.mockReturnValue(reply(entries))
    render(<MemoryView onClose={() => {}} />)
    const persona = await screen.findByRole('region', { name: 'Persona: lines you wrote' })
    expect(within(persona).getByText('I live in Oslo')).toBeTruthy()
    expect(within(screen.getByRole('region', { name: 'Learned from what you said' })).getByText('you said it on 2026-10-12')).toBeTruthy()
    expect(screen.getByRole('region', { name: 'Earlier tasks' })).toBeTruthy()
  })

  it('forgets one entry and reads the list again', async () => {
    fetchMock.mockImplementation((_url: string, init?: RequestInit) => (init?.method === 'DELETE' ? Promise.resolve(new Response(null, { status: 204 })) : reply(entries)))
    render(<MemoryView onClose={() => {}} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Forget: I have a dog called Mo' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/memory/f-1a2b3c4d', { method: 'DELETE' }))
  })

  it('keeps a typed line in the Persona and clears the box', async () => {
    fetchMock.mockImplementation((_url: string, init?: RequestInit) => (init?.method === 'POST' ? reply({ id: 'p-aaaaaa', kind: 'persona', text: 'x', source: '' }, 201) : reply([])))
    render(<MemoryView onClose={() => {}} />)
    const box = await screen.findByRole('textbox', { name: 'Add a line to your Persona' })
    expect((screen.getByRole('button', { name: 'Keep' }) as HTMLButtonElement).disabled).toBe(true) // nothing typed
    fireEvent.change(box, { target: { value: ' My CV is in D:\\Career ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Keep' }))
    await waitFor(() => expect((box as HTMLInputElement).value).toBe(''))
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')!
    expect(JSON.parse(post[1].body)).toEqual({ text: 'My CV is in D:\\Career' })
  })

  it('says so when memory is off, and when it could not be read, with a way to try again', async () => {
    fetchMock.mockReturnValueOnce(reply({}, 404))
    const { unmount } = render(<MemoryView onClose={() => {}} />)
    expect(await screen.findByText(/Memory is off/)).toBeTruthy()
    unmount()
    fetchMock.mockReturnValueOnce(Promise.reject(new Error('down'))).mockReturnValueOnce(reply([]))
    render(<MemoryView onClose={() => {}} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Nothing is kept yet.')).toBeTruthy()
  })

  it('closes', async () => {
    fetchMock.mockReturnValue(reply([]))
    const onClose = vi.fn()
    render(<MemoryView onClose={onClose} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Close Memory' }))
    expect(onClose).toHaveBeenCalled()
  })
})
