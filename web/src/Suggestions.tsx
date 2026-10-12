// Four things to try, one for each of the Assistant's hands (web search, the browser, files, the reader). Each sends as typed.
const ASKS = [
  "What's the news in New York today?",
  'What are the top three events on Luma this weekend in New York?',
  'How many files are in my Documents folder, by type?',
  'Summarize the newest PDF in my Downloads folder',
]

/** Suggested questions as quiet pills: under the composer on a wide screen, one scrolling row above it on a phone; they rise in one after another. */
export default function Suggestions({ online, onPick }: { online: boolean; onPick: (text: string) => void }) {
  return (
    <div className="suggestions" role="group" aria-label="Suggested questions">
      {ASKS.map((text, i) => (
        <button key={text} type="button" className="suggestion" style={{ animationDelay: `${i * 60}ms` }} disabled={!online} onClick={() => onPick(text)}>
          {text}
        </button>
      ))}
    </div>
  )
}
