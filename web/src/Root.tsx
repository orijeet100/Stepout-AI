import App from './App.tsx'
import DesignGallery from './design/DesignGallery.tsx'
import { useHash } from './design/useHash.ts'

// U1 only: `#/design/a|b|c` shows the design directions; everything else is the chat.
export default function Root() {
  return useHash().startsWith('#/design') ? <DesignGallery /> : <App />
}
