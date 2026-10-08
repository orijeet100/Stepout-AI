// Invented data in the v1 contract's shape (docs/ui-contract.md). No real paths, no real runs.

export type Verdict = 'allow' | 'refuse' | 'ask'
export type StepState = 'pending' | 'running' | 'done' | 'failed'

export type Chat = { id: string; title: string; preview: string; state: 'idle' | 'queued' | 'running' }
export type PlanItem = { role: string; goal: string; status: StepState }
export type StepLine = { role: string; line: string; verdict: Verdict; cost: number; note?: string; running?: boolean }
export type Shot = { url: string; title: string; art: 0 | 1 | 2 }
export type Run = {
  request: string
  state: 'running' | 'done'
  plan: PlanItem[]
  steps: StepLine[]
  shots: Shot[]
  cost: number
  cap: number
  elapsed: string
  reply?: string
}

export const chats: Chat[] = [
  { id: 'c1', title: 'Top events on Luma this weekend', preview: 'Now checking which are free…', state: 'running' },
  { id: 'c2', title: 'PDFs in the Projects folder', preview: 'Waiting for the current run', state: 'queued' },
  { id: 'c3', title: 'Compare two laptop reviews', preview: 'The second review rates the battery higher…', state: 'idle' },
  { id: 'c4', title: 'Weather in Lisbon next week', preview: 'Mostly sunny, 22–25 °C, one rainy day', state: 'idle' },
  { id: 'c5', title: 'Find the lease renewal letter', preview: 'I need a hint about which folder to look in', state: 'idle' },
  { id: 'c6', title: 'Summarise the Q3 board memo', preview: 'Three decisions and two open risks', state: 'idle' },
]

export const finished: Run = {
  request: 'What are the top three events on Luma this weekend in New York?',
  state: 'done',
  plan: [
    { role: 'browser', goal: 'Open the Luma discover page for New York', status: 'done' },
    { role: 'browser', goal: 'Read the three most popular weekend events', status: 'done' },
    { role: 'orchestrator', goal: 'Write up the answer', status: 'done' },
  ],
  steps: [
    { role: 'browser', line: 'open luma.com/discover', verdict: 'allow', cost: 0.0124 },
    { role: 'browser', line: 'open luma.com/ny', verdict: 'allow', cost: 0.0153 },
    { role: 'browser', line: 'click “Add to calendar”', verdict: 'refuse', cost: 0.0038, note: 'Would download a file. This assistant is read-only for now.' },
    { role: 'browser', line: 'read the first three listings', verdict: 'allow', cost: 0.0192 },
    { role: 'orchestrator', line: 'answer', verdict: 'allow', cost: 0.0425 },
  ],
  shots: [
    { url: 'https://luma.com/discover', title: 'Discover events · Luma', art: 0 },
    { url: 'https://luma.com/ny', title: 'New York · Luma', art: 1 },
    { url: 'https://luma.com/ny?when=weekend', title: 'This weekend · New York · Luma', art: 2 },
  ],
  cost: 0.0932,
  cap: 1,
  elapsed: '32 s',
  reply: `Here are the three most popular events in New York this weekend:

1. **Rooftop Jazz Night** — Saturday, 7:00 pm · Williamsburg · [luma.com/e/jazz-rooftop](https://luma.com/e/jazz-rooftop)
2. **AI Builders Meetup** — Saturday, 6:30 pm · SoHo · [luma.com/e/ai-meetup](https://luma.com/e/ai-meetup)
3. **Sunday Sketch Club** — Sunday, 11:00 am · Chelsea · [luma.com/e/sketch-club](https://luma.com/e/sketch-club)

I couldn't add them to a calendar: this assistant can only read for now.`,
}

export const running: Run = {
  request: 'Which of those are free to attend?',
  state: 'running',
  plan: [
    { role: 'browser', goal: 'Open each event page', status: 'done' },
    { role: 'browser', goal: 'Read the ticket price on each', status: 'running' },
    { role: 'orchestrator', goal: 'Say which ones are free', status: 'pending' },
  ],
  steps: [
    { role: 'browser', line: 'open luma.com/e/jazz-rooftop', verdict: 'allow', cost: 0.0141 },
    { role: 'browser', line: 'read the “Tickets” section', verdict: 'allow', cost: 0.0236 },
    { role: 'browser', line: 'open luma.com/e/ai-meetup', verdict: 'allow', cost: 0.0152 },
    { role: 'browser', line: 'read the “Tickets” section', verdict: 'allow', cost: 0, running: true },
  ],
  shots: [{ url: 'https://luma.com/e/jazz-rooftop', title: 'Rooftop Jazz Night · Luma', art: 1 }],
  cost: 0.0739,
  cap: 1,
  elapsed: '12 s',
}

/** Every screenshot in the conversation, in order — what the viewer steps through. */
export const allShots: Shot[] = [...finished.shots, ...running.shots]
