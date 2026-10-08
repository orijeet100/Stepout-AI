import Markdown from 'react-markdown'

// Model output is untrusted (contract, Security): no raw HTML (react-markdown does not parse it without a plugin),
// links only to http(s) and mailto with rel="noopener noreferrer", and no images at all, because an image URL in a
// reply is a way to send what the model has seen to someone else's server.
const SAFE_URL = /^(https?:|mailto:)/i

export default function Reply({ text }: { text: string }) {
  return (
    <Markdown
      urlTransform={(url) => (SAFE_URL.test(url) ? url : null)}
      disallowedElements={['img']}
      components={{ a: ({ href, children }) => (href ? <a href={href} target="_blank" rel="noopener noreferrer">{children}</a> : <>{children}</>) }}
    >
      {text}
    </Markdown>
  )
}
