import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import RunBlock from './RunBlock'
import { BrowserPanel, ShotImage } from './Shots'
import { runCap, runState } from './store'
import { raw, runOf, stateOf } from './testFixtures'

const RUN = 'ab'.repeat(16)
const shot = (n: number, extra: object = {}) => ({ path: `${RUN}/${n}.jpg`, url: `https://example.com/${n}`, title: `Page ${n}`, ...extra })
const liveImg = () => document.querySelector<HTMLImageElement>('img.browser__live')

describe('BrowserPanel: live while the Run runs, the last page after', () => {
  it('while live: the stream, a Live marker that says view only, and "Opening page…" until a page is known', () => {
    render(<BrowserPanel runId={RUN} live shots={[]} />)
    expect(liveImg()!.getAttribute('src')).toBe(`/live/${RUN}`)
    expect(liveImg()!.getAttribute('alt')).toMatch(/Live view.*View only/)
    expect(screen.getByText('Live').closest('.browser__badge')!.getAttribute('title')).toMatch(/nothing you do here reaches the browser/)
    expect(screen.getByText('Opening page…')).toBeTruthy()
    expect(screen.queryByText('Last page')).toBeNull()
  })

  it('captions the live view with the title and address of the latest saved page', () => {
    render(<BrowserPanel runId={RUN} live shots={[shot(1), shot(2)]} />)
    expect(screen.getByText('Page 2')).toBeTruthy()
    const link = screen.getByRole('link', { name: 'https://example.com/2' })
    expect(link.getAttribute('rel')).toBe('noopener noreferrer')
    expect(link.getAttribute('target')).toBe('_blank')
    expect(screen.queryByText('Page 1')).toBeNull() // the latest, not the first
  })

  it('has no way to send anything back: no input, no button, no click handler on the live image', () => {
    render(<BrowserPanel runId={RUN} live shots={[shot(1)]} onOpen={() => {}} />)
    const panel = document.querySelector('.browser')!
    expect(panel.querySelectorAll('input, textarea, select, button')).toHaveLength(0) // while live, even the "open viewer" button is not there
    expect(liveImg()!.closest('a, button')).toBeNull()
  })

  it('when the Run is over it shows the last saved screenshot, marked "Last page", and no stream', () => {
    render(<BrowserPanel runId={RUN} live={false} shots={[shot(1), shot(2)]} />)
    expect(liveImg()).toBeNull()
    expect(screen.getByText('Last page')).toBeTruthy()
    const img = screen.getByAltText('Screenshot of Page 2')
    expect(img.getAttribute('src')).toBe(`/shots/${RUN}/2.jpg`)
  })

  it('when the stream breaks or answers 404 it swaps to the last screenshot, not a broken image', () => {
    render(<BrowserPanel runId={RUN} live shots={[shot(1)]} />)
    fireEvent.error(liveImg()!)
    expect(liveImg()).toBeNull()
    expect(screen.getByText('Last page')).toBeTruthy()
    expect(screen.getByAltText('Screenshot of Page 1')).toBeTruthy()
  })

  it('a stream that fails before any page was saved says so in words', () => {
    render(<BrowserPanel runId={RUN} live shots={[]} />)
    fireEvent.error(liveImg()!)
    expect(liveImg()).toBeNull()
    expect(screen.getByText('No page to show yet.')).toBeTruthy()
    expect(document.querySelector('img')).toBeNull() // nothing that could be a broken image
  })

  it('shows nothing for a Run that is over and never saved a page', () => {
    const { container } = render(<BrowserPanel runId={RUN} live={false} shots={[]} />)
    expect(container.innerHTML).toBe('')
  })

  it('never builds a stream address from an id that is not the backend’s', () => {
    render(<BrowserPanel runId="../../etc" live shots={[shot(1)]} />)
    expect(liveImg()).toBeNull()
    expect(screen.getByText('Last page')).toBeTruthy() // falls back to the screenshot
  })

  it('a page address that is not http(s) is text, never a link', () => {
    render(<BrowserPanel runId={RUN} live={false} shots={[shot(1, { url: 'javascript:alert(1)' })]} />)
    expect(screen.getByText('javascript:alert(1)').tagName).toBe('SPAN')
    expect(screen.queryByRole('link')).toBeNull()
  })

  it('the last screenshot opens the viewer when there is one to open', () => {
    const onOpen = vi.fn()
    render(<BrowserPanel runId={RUN} live={false} shots={[shot(1), shot(2), shot(3)]} onOpen={onOpen} />)
    fireEvent.click(screen.getByRole('button', { name: 'Open screenshot: Page 3' }))
    expect(onOpen).toHaveBeenCalledWith(2) // the index of the last one
  })
})

describe('ShotImage: a missing screenshot is a placeholder', () => {
  it('shows the image, and a placeholder if it fails to load', () => {
    render(<ShotImage shot={shot(1)} />)
    fireEvent.error(screen.getByAltText('Screenshot of Page 1'))
    expect(screen.queryByAltText('Screenshot of Page 1')).toBeNull()
    expect(screen.getByRole('img', { name: 'Screenshot unavailable' })).toBeTruthy()
  })

  it('shows the placeholder at once for a path that is not the backend’s, without requesting anything', () => {
    for (const path of ['', '../secret.txt', 'https://evil.example/a.jpg', `${RUN}/1.png`]) {
      const { container, unmount } = render(<ShotImage shot={shot(1, { path })} />)
      expect(container.querySelector('img'), path).toBeNull()
      expect(screen.getByRole('img', { name: 'Screenshot unavailable' })).toBeTruthy()
      unmount()
    }
  })
})

describe('in a Run, from the fixtures', () => {
  const FRAMES = { opening: 5, withOnePage: 6 } // frames of the web run: the first Browser step; and the first screenshot
  const block = (s: ReturnType<typeof stateOf>, name = 'web-run', state?: 'running' | 'done') => {
    const run = s.runs[runOf(name)!]
    return render(<RunBlock run={run} state={state ?? runState(s, run)} cap={runCap(s, run)} now={Date.now()} onStop={() => {}} />)
  }

  it('a running Browser Run shows the live view; before its first screenshot it says it is opening a page', () => {
    block(stateOf('web-run', { upTo: FRAMES.opening, active: 1 }))
    expect(liveImg()!.getAttribute('src')).toBe(`/live/${runOf('web-run')}`)
    expect(screen.getByText('Opening page…')).toBeTruthy()
  })

  it('once the Browser has saved a page, the live view is captioned with its title and address', () => {
    block(stateOf('web-run', { upTo: FRAMES.withOnePage, active: 1 }))
    expect(screen.getByText('Discover events · Luma')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'https://luma.com/discover' })).toBeTruthy()
  })

  it('when the Run is over the live view is gone and the last page of the Run is shown', () => {
    const shots = raw('web-run').filter((f) => f.kind === 'shot')
    const last = shots.at(-1)!.data as { shot: string; title: string }
    block(stateOf('web-run', { hint: 'done', cap: 1 }))
    expect(liveImg()).toBeNull()
    expect(screen.getByText('Last page')).toBeTruthy()
    expect(screen.getByAltText(`Screenshot of ${last.title}`).getAttribute('src')).toBe(`/shots/${last.shot}`)
  })

  it('a Run with no Browser step has nothing to watch: no panel while running, none when over', () => {
    const files = stateOf('files-run', { upTo: 5, active: 1 })
    block(files, 'files-run')
    expect(document.querySelector('.browser')).toBeNull()
    expect(document.querySelector('.browser__empty')).toBeNull()
    block(stateOf('chat-reply', { hint: 'done', cap: 1 }), 'chat-reply')
    expect(document.querySelector('.browser')).toBeNull()
  })

  it('a stopped Run keeps showing the page it had reached', () => {
    block(stateOf('stopped', { hint: 'stopped', cap: 1 }), 'stopped')
    expect(screen.getByText('Last page')).toBeTruthy()
    expect(screen.getByText('Engineering · Example Blog')).toBeTruthy()
  })
})
