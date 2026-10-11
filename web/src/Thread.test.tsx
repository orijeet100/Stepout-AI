import { act, fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ChatView from './ChatView'
import type { Frame } from './protocol'
import { initial, reducer, runCap, runState, starting, timeline, type Action, type State } from './store'
import { chatOf, stateOf } from './testFixtures'

// The thread as the template lays it out: your messages are bubbles, everything the assistant says in answer shares one tile.
const view = (s: State, chat: string, props: Partial<Parameters<typeof ChatView>[0]> = {}) =>
  render(<ChatView items={timeline(s, chat)} starting={starting(s, chat, timeline(s, chat))} runState={(r) => runState(s, r)} runCap={(r) => runCap(s, r)} onStop={() => {}} {...props} />)

const C = 'c'.repeat(32)
const at = (s: number) => `2026-10-01T09:00:${String(s).padStart(2, '0')}.000Z`
const frame = (frame: Frame): Action => ({ type: 'frame', frame })
const yours = (text: string, secs = 1) => frame({ type: 'message', id: `m${secs}`, conversation_id: C, role: 'user', text, run_id: null, cost_usd: null, at: at(secs) })
const status = (state: 'idle' | 'running', active: boolean) =>
  frame({ type: 'status', state, active: active ? { conversation_id: C, run_id: 'r'.repeat(32), cap_usd: 1 } : null, queued: [] })
const run = (...actions: Action[]) => actions.reduce(reducer, initial as State)

describe('one tile for everything the assistant says in answer', () => {
  it('a run and its reply are one row with one tile; your message is a bubble, not a tile', () => {
    const name = 'web-run'
    const { container } = view(stateOf(name, { hint: 'done', cap: 1 }), chatOf(name))
    expect(container.querySelectorAll('.turn')).toHaveLength(1)
    expect(container.querySelectorAll('.turn__tile')).toHaveLength(1)
    const turn = container.querySelector('.turn')!
    expect(turn.querySelector('.runblock')).toBeTruthy()
    expect(turn.querySelector('.reply')).toBeTruthy() // the run card and the reply sit in the same body
    expect(container.querySelector('.user')).toBeTruthy()
    expect(container.querySelector('.user')!.closest('.turn')).toBeNull()
  })

  it('each of your messages starts a new answer row', () => {
    const s = run(yours('first', 1), frame({ type: 'message', id: 'a1', conversation_id: C, role: 'assistant', text: 'one', run_id: null, cost_usd: null, at: at(2) }), yours('second', 3), frame({ type: 'message', id: 'a2', conversation_id: C, role: 'assistant', text: 'two', run_id: null, cost_usd: null, at: at(4) }))
    const { container } = view(s, C)
    expect([...container.querySelectorAll('.col > *')].map((n) => (n.classList.contains('user') ? 'you' : 'assistant'))).toEqual(['you', 'assistant', 'you', 'assistant'])
  })

  it('a message read back from history does not slide in; one that was just sent does', () => {
    const old = view(run(yours('old', 1)), C)
    expect(old.container.querySelector('.user')!.className).not.toContain('user--new')
    old.unmount()
    const fresh = run(frame({ type: 'message', id: 'n', conversation_id: C, role: 'user', text: 'new', run_id: null, cost_usd: null, at: new Date().toISOString() }))
    expect(view(fresh, C).container.querySelector('.user')!.className).toContain('user--new')
  })
})

describe('the assistant is starting', () => {
  it('says it is working from the moment your message is taken until the first thing of its run arrives', () => {
    const waiting = run(yours('hi'), status('running', false)) // taken from the queue, the front door is screening it
    expect(starting(waiting, C, timeline(waiting, C))).toBe(true)
    const { container } = view(waiting, C)
    expect(container.querySelector('.working')!.textContent).toBe('Working…')
    expect(container.querySelectorAll('.turn__tile')).toHaveLength(1)
  })

  it('is not shown when idle, when the message is only queued, or when another chat holds the run', () => {
    expect(starting(run(yours('hi')), C, timeline(run(yours('hi')), C))).toBe(false) // idle
    const other = run(yours('hi'), frame({ type: 'status', state: 'running', active: { conversation_id: 'd'.repeat(32), run_id: 'r'.repeat(32), cap_usd: 1 }, queued: [{ conversation_id: C }] }))
    expect(starting(other, C, timeline(other, C))).toBe(false) // waiting its turn behind another chat's run
  })

  it('goes away when the first event of the run arrives (the card takes the same row)', () => {
    const s = run(yours('hi'), status('running', true), frame({ type: 'trace', id: 'e1', conversation_id: C, run_id: 'r'.repeat(32), parent: null, kind: 'step', role: 'orchestrator', data: { summary: 'plan' }, cost_usd: 0, at: at(3) }))
    expect(starting(s, C, timeline(s, C))).toBe(false)
    const { container } = view(s, C)
    expect(container.querySelector('.working')).toBeNull()
    expect(container.querySelectorAll('.turn')).toHaveLength(1)
  })
})

describe('the way back to the end', () => {
  it('appears when the reader has scrolled up, and takes them to the end', () => {
    const s = run(yours('one', 1), yours('two', 2), yours('three', 3))
    const { container } = view(s, C)
    const box = container.querySelector('.scroll') as HTMLElement
    const jump = screen.getByLabelText('Scroll to the end', { selector: 'button' })
    expect(jump.className).not.toContain('is-on')
    Object.defineProperty(box, 'scrollHeight', { value: 2000, configurable: true })
    Object.defineProperty(box, 'clientHeight', { value: 500, configurable: true })
    act(() => {
      box.scrollTop = 100
      fireEvent.scroll(box)
    })
    expect(jump.className).toContain('is-on')
    expect(jump.getAttribute('tabindex')).toBe('0')
    fireEvent.click(jump)
    expect(box.scrollTop).toBe(2000)
  })
})
