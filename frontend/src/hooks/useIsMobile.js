import { useEffect, useState } from 'react'

const MOBILE_QUERY = '(max-width: 1023px)'

export default function useIsMobile() {
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false
    return window.matchMedia(MOBILE_QUERY).matches
  })

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const mql = window.matchMedia(MOBILE_QUERY)
    const handler = (e) => setIsMobile(e.matches)
    mql.addEventListener ? mql.addEventListener('change', handler) : mql.addListener(handler)
    return () => {
      mql.removeEventListener ? mql.removeEventListener('change', handler) : mql.removeListener(handler)
    }
  }, [])

  return isMobile
}
