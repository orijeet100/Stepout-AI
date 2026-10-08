import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import RunBlock from './RunBlock'
import ShotViewer from './ShotViewer'
import { ThumbStrip } from './Shots'
import type { Shot } from './runview'
import { runCap, runState } from './store'
import { raw, runOf, stateOf } from './testFixtures'

const RUN = 'ab'.repeat(16)
const SHOTS: Shot[] = [1, 2, 3].map((n) => ({ path: `${RUN}/${n}.jpg`, url: `https://example.com/${n}`, title: `Page ${n}` }))

// jsdom has no <dialog>.showModal: a stand-in with the two behaviours the component relies on. The real ones
// (focus trap, Esc, focus restored to the opener) are checked in Chrome by web/e2e/test_viewer.py.
const showModal = vi.fn(function (this: HTMLDialogElement) {
  this.setAttribute('open', '')
})
const close = vi.fn(function (this: HTMLDialogElement) {
  this.removeAttribute('open')
  this.dispatchEvent(new Event('close'))
})
beforeAll(() => {
  Object.assign(HTMLDialogElement.prototype, { showModal, close })
})

const open = (index: number | null = 0, shots: Shot[] = SHOTS) => {
  const handlers = { onIndex: vi.fn(), onClose: vi.fn() }
  const view = render(<ShotViewer shots={shots} index={index} {...handlers} />)
  return { ...handlers, ...view }
}

describe('ThumbStrip', () => {
  it('has one thumbnail per saved page, named for screen readers, and opens that page', () => {
    const onOpen = vi.fn()
    render(<ThumbStrip shots={SHOTS} onOpen={onOpen} />)
    const group = screen.getByRole('group', { name: 'Pages the browser saved' })
    const buttons = within(group).getAllByRole('button')
    expect(buttons.map((b) => b.getAttribute('aria-label'))).toEqual(['Open screenshot 1 of 3: Page 1', 'Open screenshot 2 of 3: Page 2', 'Open screenshot 3 of 3: Page 3'])
    fireEvent.click(buttons[1])
    expect(onOpen).toHaveBeenCalledWith(1)
  })

  it('shows nothing when no page was saved, and a placeholder (not a broken image) for a missing file', () => {
    const { container } = render(<ThumbStrip shots={[]} onOpen={() => {}} />)
    expect(container.innerHTML).toBe('')
    render(<ThumbStrip shots={[SHOTS[0]]} onOpen={() => {}} />)
    fireEvent.error(document.querySelector('img.thumb__img')!)
    expect(document.querySelector('img.thumb__img')).toBeNull()
    expect(screen.getByRole('img', { name: 'Screenshot unavailable' })).toBeTruthy()
  })
})

describe('thumbnails in a Run, from the fixtures', () => {
  // `null`: a Run with nothing to open the pages with; otherwise the handler (a do-nothing one by default)
  const block = (upTo: number | undefined, onOpenShot: ((i: number) => void) | null = () => {}) => {
    const s = stateOf('web-run', { upTo, hint: upTo ? undefined : 'done', cap: 1, active: upTo ? 1 : undefined })
    const run = s.runs[runOf('web-run')!]
    return render(<RunBlock run={run} state={runState(s, run)} cap={runCap(s, run)} now={Date.now()} onStop={() => {}} onOpenShot={onOpenShot ?? undefined} />)
  }
  const thumbs = () => [...document.querySelectorAll('.thumb')].map((t) => t.getAttribute('aria-label'))

  it('appear as the shot events arrive, and all are there once the Run is over', () => {
    block(6) // the first page saved
    expect(thumbs()).toEqual(['Open screenshot 1 of 1: Discover events · Luma'])
    document.body.innerHTML = ''
    block(undefined) // the whole Run
    const titles = raw('web-run').filter((f) => f.kind === 'shot').map((f) => (f.data as { title: string }).title)
    expect(thumbs()).toEqual(titles.map((t, i) => `Open screenshot ${i + 1} of ${titles.length}: ${t}`))
  })

  it('opens the page that was clicked, by its index in the Run', () => {
    const onOpenShot = vi.fn()
    block(undefined, onOpenShot)
    fireEvent.click(document.querySelectorAll('.thumb')[1])
    expect(onOpenShot).toHaveBeenCalledWith(1)
  })

  it('a Run without a viewer to open them has no thumbnails', () => {
    block(undefined, null)
    expect(document.querySelector('.thumbs')).toBeNull()
  })
})

describe('ShotViewer', () => {
  it('opens as a modal on the page asked for: large image with alt text, title, address, "n of m"', () => {
    open(1)
    expect(showModal).toHaveBeenCalled()
    expect(screen.getByRole('heading', { name: 'Page 2' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'https://example.com/2' }).getAttribute('rel')).toBe('noopener noreferrer')
    const img = screen.getByAltText('Screenshot of Page 2')
    expect(img.getAttribute('src')).toBe(`/shots/${RUN}/2.jpg`)
    expect(img.className).toContain('viewer__img')
    expect(screen.getByText('2 of 3')).toBeTruthy()
    expect(screen.getByLabelText('Screenshot viewer').hasAttribute('open')).toBe(true)
  })

  it('starts on the Close button (keyboard users land somewhere sensible)', () => {
    open(0)
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Close viewer' }))
  })

  it('steps to the previous and next page across the Run, wrapping at the ends', () => {
    const { onIndex } = open(0)
    fireEvent.click(screen.getByRole('button', { name: /Next/ }))
    expect(onIndex).toHaveBeenLastCalledWith(1)
    fireEvent.click(screen.getByRole('button', { name: /Previous/ }))
    expect(onIndex).toHaveBeenLastCalledWith(2) // from the first back round to the last
  })

  it('the arrow keys step too', () => {
    const { onIndex } = open(1)
    const dialog = screen.getByLabelText('Screenshot viewer')
    fireEvent.keyDown(dialog, { key: 'ArrowRight' })
    expect(onIndex).toHaveBeenLastCalledWith(2)
    fireEvent.keyDown(dialog, { key: 'ArrowLeft' })
    expect(onIndex).toHaveBeenLastCalledWith(0)
    fireEvent.keyDown(dialog, { key: 'Enter' })
    expect(onIndex).toHaveBeenCalledTimes(2) // other keys do nothing
  })

  it('with a single page there is nothing to step to', () => {
    const { onIndex } = open(0, [SHOTS[0]])
    expect((screen.getByRole('button', { name: /Next/ }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: /Previous/ }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.keyDown(screen.getByLabelText('Screenshot viewer'), { key: 'ArrowRight' })
    expect(onIndex).not.toHaveBeenCalled()
    expect(screen.getByText('1 of 1')).toBeTruthy()
  })

  it('closes from the Close button, from Esc (the dialog’s own close event) and from a click on the backdrop', () => {
    const a = open(0)
    fireEvent.click(screen.getByRole('button', { name: 'Close viewer' }))
    expect(a.onClose).toHaveBeenCalledTimes(1)
    a.unmount()

    const b = open(0)
    fireEvent(screen.getByLabelText('Screenshot viewer'), new Event('close')) // what the browser sends on Esc
    expect(b.onClose).toHaveBeenCalledTimes(1)
    b.unmount()

    const c = open(0)
    fireEvent.click(screen.getByLabelText('Screenshot viewer')) // a click on the dialog element itself is a click on its backdrop
    expect(c.onClose).toHaveBeenCalledTimes(1)
    c.onClose.mockClear()
    fireEvent.click(screen.getByAltText('Screenshot of Page 1')) // a click inside the panel is not
    expect(c.onClose).not.toHaveBeenCalled()
  })

  it('closes the dialog when told there is nothing to show, and shows nothing inside it', () => {
    const { rerender, onIndex, onClose } = open(0)
    rerender(<ShotViewer shots={SHOTS} index={null} onIndex={onIndex} onClose={onClose} />)
    expect(close).toHaveBeenCalled()
    expect(document.querySelector('.viewer__panel')).toBeNull()
  })

  it('a missing screenshot shows a placeholder in the viewer too', () => {
    open(0)
    fireEvent.error(screen.getByAltText('Screenshot of Page 1'))
    expect(screen.getByRole('img', { name: 'Screenshot unavailable' })).toBeTruthy()
    expect(document.querySelector('img.viewer__img')).toBeNull()
  })

  it('a page with no title or address still shows, as an untitled page', () => {
    open(0, [{ path: `${RUN}/1.jpg`, url: null, title: null }])
    expect(screen.getByRole('heading', { name: 'Untitled page' })).toBeTruthy()
    expect(screen.queryByRole('link')).toBeNull()
    expect(screen.getByAltText('Screenshot of the page')).toBeTruthy()
  })
})
