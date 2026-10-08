import { useSyncExternalStore } from 'react'

// Under this width the chat list is a drawer (U5). Keep in step with the media query in App.css.
const NARROW = '(max-width: 899px)'

const subscribe = (onChange: () => void) => {
  const query = window.matchMedia?.(NARROW)
  query?.addEventListener('change', onChange)
  return () => query?.removeEventListener('change', onChange)
}

/** Is the window narrower than 900 px? (false where there is no matchMedia, as in a test DOM) */
export const useNarrow = () => useSyncExternalStore(subscribe, () => window.matchMedia?.(NARROW).matches ?? false, () => false)
