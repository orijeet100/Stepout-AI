import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ChatView from './ChatView'
import { runCap, runState, timeline, type State } from './store'
import { chatOf, historyOf, stateOf } from './testFixtures'

// A chat read back from the API after a restart must look exactly like the same chat watched live: same summary, plan, meters,
// step lines, saved pages and reply. The page is rendered both ways from the same invented fixture and the markup compared.
// (Watched live = the frames as they arrived, then the refresh of the chat's detail the page makes when a Run ends.)
const html = (s: State, name: string) =>
  render(<ChatView items={timeline(s, chatOf(name))} runState={(r) => runState(s, r)} runCap={(r) => runCap(s, r)} onStop={() => {}} onOpenShot={() => {}} />).container.innerHTML

describe('a chat read from history looks like the chat watched live', () => {
  for (const [name, hint] of [
    ['web-run', 'done'],
    ['files-run', 'done'],
    ['refused-action', 'done'],
    ['stopped', 'stopped'],
    ['over-budget', 'stopped'],
    ['chat-reply', 'done'],
    ['declined', 'done'],
  ] as const) {
    it(`${name}`, () => {
      const live = html(stateOf(name, { hint, cap: 1 }), name)
      const history = html(historyOf(name, hint), name)
      expect(live).toContain('class="') // it rendered something
      expect(history).toBe(live)
    })
  }
})
