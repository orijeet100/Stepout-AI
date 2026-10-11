/** The empty chat's greeting, centred in the panel as the template's is: a title, then a quieter line. */
export default function Greeting() {
  return (
    <div className="greeting">
      <p className="greeting__title">What can I help with?</p>
      <p className="greeting__sub">Ask a question. It plans the steps, shows each one as it happens, and tells you what it cost.</p>
    </div>
  )
}
