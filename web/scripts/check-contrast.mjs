// `npm run check:contrast`: WCAG contrast of the text/background pairs in src/design/tokens.css (light and dark).
import { readFileSync } from 'node:fs'

const css = readFileSync(new URL('../src/design/tokens.css', import.meta.url), 'utf8')
const lum = (hex) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
}
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05) }

const tokens = { light: {}, dark: {} }
for (const [, name, l, d] of css.matchAll(/--([\w-]+): light-dark\((#\w{6}), (#\w{6})\)/g)) { tokens.light[name] = l; tokens.dark[name] = d }

// [foreground, background]; all need 4.5:1 (normal text)
const pairs = [
  ['text', 'bg'], ['text', 'sidebar'], ['text', 'user-bg'], ['text', 'active'], ['text', 'surface'],
  ['muted', 'bg'], ['muted', 'sidebar'], ['muted', 'surface'], ['muted', 'active'],
  ['accent', 'bg'], ['accent', 'surface'], ['accent', 'accent-soft'], ['on-accent', 'accent'],
  ['ok', 'bg'], ['ok', 'surface'], ['warn', 'bg'], ['warn', 'surface'], ['err', 'bg'], ['err', 'surface'],
]
let bad = 0
for (const mode of ['light', 'dark']) {
  for (const [fg, bg] of pairs) {
    const r = ratio(tokens[mode][fg], tokens[mode][bg])
    if (!(r >= 4.5)) { bad++; console.log(`FAIL ${mode}: ${fg} ${tokens[mode][fg]} on ${bg} ${tokens[mode][bg]} = ${r.toFixed(2)}`) }
  }
}
console.log(bad ? `${bad} failing pair(s)` : `all ${pairs.length * 2} pairs pass`)
process.exit(bad ? 1 : 0)
