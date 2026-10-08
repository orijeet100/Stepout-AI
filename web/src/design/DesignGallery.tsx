import { useState } from 'react'
import FixtureScreen from './FixtureScreen.tsx'
import { useHash } from './useHash.ts'
import './directions.css'
import './gallery.css'

const DIRECTIONS = {
  a: { name: 'Paper', note: 'Warm cream, serif replies, terracotta. Closest to Claude.ai.' },
  b: { name: 'Slate', note: 'Neutral white and graphite, one sans, teal. Closest to ChatGPT.' },
  c: { name: 'Ink', note: 'Cool graphite, mono run detail, run-green. Denser and more technical.' },
} as const
type Dir = keyof typeof DIRECTIONS
type Theme = 'system' | 'light' | 'dark'

/** `#/design/b?theme=dark&viewer=1` → direction, theme, and which screenshot starts open. */
function parse(hash: string) {
  const [path, query = ''] = hash.split('?')
  const q = new URLSearchParams(query)
  const seg = path.split('/')[2]
  const dir: Dir = seg === 'b' || seg === 'c' ? seg : 'a'
  const theme = q.get('theme') === 'light' || q.get('theme') === 'dark' ? (q.get('theme') as Theme) : 'system'
  const viewer = q.has('viewer') ? Number(q.get('viewer')) || 0 : null
  return { dir, theme, viewer }
}
const link = (dir: Dir, theme: Theme) => `#/design/${dir}${theme === 'system' ? '' : `?theme=${theme}`}`

export default function DesignGallery() {
  const hash = useHash()
  const { dir, theme, viewer: initial } = parse(hash)
  const [viewer, setViewer] = useState<number | null>(initial)
  return (
    <div className="gallery" data-dir={dir} data-theme={theme === 'system' ? undefined : theme}>
      <nav className="gallery__bar" aria-label="Design directions">
        <strong>Direction</strong>
        {(Object.keys(DIRECTIONS) as Dir[]).map((d) => (
          <a key={d} href={link(d, theme)} aria-current={d === dir ? 'page' : undefined}>
            {d.toUpperCase()} · {DIRECTIONS[d].name}
          </a>
        ))}
        <span className="gallery__note">{DIRECTIONS[dir].note}</span>
        <span className="gallery__spacer" />
        {(['system', 'light', 'dark'] as Theme[]).map((t) => (
          <a key={t} href={link(dir, t)} aria-current={t === theme ? 'true' : undefined}>{t}</a>
        ))}
        <button type="button" onClick={() => setViewer(0)}>Open viewer</button>
        <a href="#/">Back to chat</a>
      </nav>
      <div className="gallery__stage">
        <FixtureScreen viewer={viewer} onViewer={setViewer} />
      </div>
    </div>
  )
}
