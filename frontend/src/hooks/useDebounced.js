import { useEffect, useState } from 'react'

/** The value, but only once it stops changing.
 *
 *  The search box on Personas put its text straight into the query key, so
 *  TanStack Query fired a request per keystroke: eight for "Fernández", seven
 *  of them already stale by the time they came back.
 *
 *  300 ms is roughly the gap between words when typing, so it waits for a pause
 *  rather than for a timer to run out.
 */
export function useDebounced(value, delay = 300) {
  const [settled, setSettled] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return settled
}
