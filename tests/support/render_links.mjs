// Renders markdown exactly as web/src/Reply.tsx does (keep this config in step with it) and prints, for each input string on stdin (a JSON list),
// the href of every link the page would make. tests/test_links.py uses it to check that what links.py lets through is what the page shows.
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import path from 'node:path'

const web = path.resolve(import.meta.dirname, '../../web')
const require = createRequire(path.join(web, 'package.json'))
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const { default: Markdown } = await import(pathToFileURL(path.join(web, 'node_modules/react-markdown/index.js')).href)

const SAFE_URL = /^(https?:|mailto:)/i
const render = (text) =>
  renderToStaticMarkup(
    React.createElement(
      Markdown,
      {
        urlTransform: (url) => (SAFE_URL.test(url) ? url : null),
        disallowedElements: ['img'],
        components: { a: ({ href, children }) => (href ? React.createElement('a', { href }, children) : children) },
      },
      text,
    ),
  )

let input = ''
for await (const chunk of process.stdin) input += chunk
const hrefs = (html) => [...html.matchAll(/<a href="([^"]*)"/g)].map((m) => m[1].replaceAll('&amp;', '&'))
console.log(JSON.stringify(JSON.parse(input).map((text) => hrefs(render(text)))))
