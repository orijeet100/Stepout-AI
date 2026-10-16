// `npm run check:contrast`: WCAG contrast of the colour pairs in src/design/tokens.css, in light and in dark.
// Text pairs need 4.5:1 (normal text); the edge of a control and the focus ring need 3:1 (WCAG 1.4.11, non-text).
// Then the blended colours the page paints as color-mix(in srgb, var(--x) N%, transparent) over a ground (the Stop button's tint, a task's
// result, an argument chip): N is read from src/App.css, so changing a percentage there changes what is checked here.
import { readFileSync } from 'node:fs'

const css = readFileSync(new URL('../src/design/tokens.css', import.meta.url), 'utf8')
const app = readFileSync(new URL('../src/App.css', import.meta.url), 'utf8')
const rgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))
const toHex = (c) => '#' + c.map((v) => Math.round(v).toString(16).padStart(2, '0')).join('')
const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
/** `prop: color-mix(in srgb, var(--token) N%, transparent)` inside the rule for `sel`: { token, pct }, or null if the stylesheet no longer has it. */
const tint = (sel, prop) => {
  const rule = app.match(new RegExp(`(?:^|\\n)${escape(sel)}\\s*\\{([^}]*)\\}`))
  const m = rule?.[1].match(new RegExp(`(?:^|[;\\s])${prop}:\\s*color-mix\\(in srgb, var\\(--([\\w-]+)\\) (\\d+)%, transparent\\)`))
  return m ? { token: m[1], pct: Number(m[2]) / 100 } : null
}
const lum = (hex) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
}
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05) }

const tokens = { light: {}, dark: {} }
for (const [, name, l, d] of css.matchAll(/--([\w-]+): light-dark\((#\w{6}), (#\w{6})\)/g)) { tokens.light[name] = l; tokens.dark[name] = d }

const grounds = ['bg', 'surface', 'surface-2', 'fill', 'sidebar', 'active', 'hover', 'card', 'well', 'track'] // every fill text can sit on (a bubble runs surface-2 to fill)
const pairs = [
  ...grounds.flatMap((g) => [['text', g, 4.5], ['muted', g, 4.5]]),
  ...['bg', 'surface', 'sidebar'].map((g) => ['accent', g, 4.5]), // links, and the strong fill of the send button
  ...grounds.flatMap((g) => [['ok', g, 4.5], ['warn', g, 4.5], ['err', g, 4.5]]), // status text and icons
  ['accent-hover', 'bg', 4.5], ['accent-hover', 'surface', 4.5],
  ['on-accent', 'accent', 4.5], ['on-accent', 'accent-hover', 4.5],
  ['warn', 'warn-soft', 4.5], ['err', 'err-soft', 4.5], ['text', 'warn-soft', 4.5], ['text', 'err-soft', 4.5], ['muted', 'err-soft', 4.5], ['muted', 'warn-soft', 4.5],
  ...['bg', 'surface', 'sidebar', 'surface-2', 'active'].map((g) => ['border-strong', g, 3]), // the edge of a button or a control
  ...['bg', 'surface', 'sidebar', 'surface-2'].map((g) => ['ring', g, 3]), // the focus ring
  ['accent', 'bg', 3], ['accent', 'surface', 3], // a filled meter bar
  ['bg', 'err', 4.5], // the label of the destructive button (bg on an err fill)
  ['accent', 'surface-2', 4.5], // the browser's Live badge
]
// A spec is a token name, or { sel, prop, ground }: the colour App.css gives `prop` in the rule `sel`, painted over the token `ground`.
const blended = [
  { label: 'Stop button', fg: 'err', bg: { sel: '.btn--stop', prop: 'background', ground: 'bg' } },
  { label: 'Stop button, hovered', fg: 'err', bg: { sel: '.btn--stop:hover:not(:disabled)', prop: 'background', ground: 'bg' } },
  { label: 'a task result', fg: { sel: '.task__result', prop: 'color', ground: 'card' }, bg: 'card' },
  { label: 'an argument chip', fg: { sel: '.tool__arg', prop: 'color', ground: 'track' }, bg: 'track' },
  { label: 'a tool result', fg: { sel: '.tool__res', prop: 'color', ground: 'well' }, bg: 'well' },
  ...['text', 'muted', 'ok', 'warn', 'err'].map((fg) => ({ label: `${fg} on a hovered task head`, fg, bg: { sel: '.task__head:hover:enabled', prop: 'background', ground: 'card' } })),
]
const colour = (mode, spec) => {
  if (typeof spec === 'string') return tokens[mode][spec]
  const t = tint(spec.sel, spec.prop)
  const [from, ground] = [t && tokens[mode][t.token], tokens[mode][spec.ground]]
  return from && ground ? toHex(rgb(from).map((v, i) => v * t.pct + rgb(ground)[i] * (1 - t.pct))) : undefined
}
let bad = 0
for (const mode of ['light', 'dark']) {
  for (const [fg, bg, min] of pairs) {
    const [a, b] = [tokens[mode][fg], tokens[mode][bg]]
    if (!a || !b) { bad++; console.log(`MISSING ${mode}: --${a ? bg : fg} is not defined in tokens.css`); continue }
    const r = ratio(a, b)
    if (!(r >= min)) { bad++; console.log(`FAIL ${mode}: ${fg} ${a} on ${bg} ${b} = ${r.toFixed(2)} (needs ${min})`) }
  }
  for (const { label, fg, bg } of blended) {
    const [a, b] = [colour(mode, fg), colour(mode, bg)]
    if (!a || !b) { bad++; console.log(`MISSING ${mode}: ${label}: the rule or token is not in App.css or tokens.css any more`); continue }
    const r = ratio(a, b)
    if (!(r >= 4.5)) { bad++; console.log(`FAIL ${mode}: ${label} ${a} on ${b} = ${r.toFixed(2)} (needs 4.5)`) }
  }
}
console.log(bad ? `${bad} failing pair(s)` : `all ${(pairs.length + blended.length) * 2} pairs pass (${blended.length * 2} of them blended)`)
process.exit(bad ? 1 : 0)
