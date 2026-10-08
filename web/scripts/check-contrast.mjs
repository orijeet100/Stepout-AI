// `npm run check:contrast`: WCAG contrast of the colour pairs in src/design/tokens.css, in light and in dark.
// Text pairs need 4.5:1 (normal text); the edge of a control and the focus ring need 3:1 (WCAG 1.4.11, non-text).
import { readFileSync } from 'node:fs'

const css = readFileSync(new URL('../src/design/tokens.css', import.meta.url), 'utf8')
const lum = (hex) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
}
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05) }

const tokens = { light: {}, dark: {} }
for (const [, name, l, d] of css.matchAll(/--([\w-]+): light-dark\((#\w{6}), (#\w{6})\)/g)) { tokens.light[name] = l; tokens.dark[name] = d }

const grounds = ['bg', 'surface', 'surface-2', 'sidebar', 'active', 'user-bg'] // every fill text can sit on
const pairs = [
  ...grounds.flatMap((g) => [['text', g, 4.5], ['muted', g, 4.5]]),
  ...['bg', 'surface', 'surface-2', 'sidebar'].flatMap((g) => [['accent', g, 4.5], ['ok', g, 4.5], ['warn', g, 4.5], ['err', g, 4.5]]), // links and status text
  ['accent-hover', 'bg', 4.5], ['accent-hover', 'surface', 4.5],
  ['on-accent', 'accent', 4.5], ['on-accent', 'accent-hover', 4.5],
  ['accent', 'accent-soft', 4.5], ['text', 'accent-soft', 4.5], ['muted', 'accent-soft', 4.5],
  ['warn', 'warn-soft', 4.5], ['err', 'err-soft', 4.5], ['text', 'warn-soft', 4.5], ['text', 'err-soft', 4.5], ['muted', 'err-soft', 4.5], ['muted', 'warn-soft', 4.5],
  ...['bg', 'surface', 'sidebar', 'surface-2'].map((g) => ['border-strong', g, 3]), // the edge of a button or the composer
  ['accent', 'bg', 3], ['accent', 'surface', 3], // the focus ring and a filled meter bar
]
let bad = 0
for (const mode of ['light', 'dark']) {
  for (const [fg, bg, min] of pairs) {
    const [a, b] = [tokens[mode][fg], tokens[mode][bg]]
    if (!a || !b) { bad++; console.log(`MISSING ${mode}: --${a ? bg : fg} is not defined in tokens.css`); continue }
    const r = ratio(a, b)
    if (!(r >= min)) { bad++; console.log(`FAIL ${mode}: ${fg} ${a} on ${bg} ${b} = ${r.toFixed(2)} (needs ${min})`) }
  }
}
console.log(bad ? `${bad} failing pair(s)` : `all ${pairs.length * 2} pairs pass`)
process.exit(bad ? 1 : 0)
