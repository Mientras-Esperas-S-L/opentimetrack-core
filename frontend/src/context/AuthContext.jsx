import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  getMe,
  setPreferredLanguage,
  signIn as apiSignIn,
  signOut as apiSignOut,
  tokens,
} from '../services/api.js'
import { AuthContext } from './authContext.js'

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)

  // A stored token is not proof of a valid session: it may have expired, or the
  // person may have been deactivated. It gets checked against the server once.
  useEffect(() => {
    let cancelled = false

    const restore = async () => {
      if (!tokens.access) {
        setLoading(false)
        return
      }
      try {
        const data = await getMe()
        if (!cancelled) {
          setPreferredLanguage(data)
          setSession(data)
        }
      } catch {
        tokens.clear()
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    restore()
    return () => {
      cancelled = true
    }
  }, [])

  const signIn = useCallback(async (credentials) => {
    const data = await apiSignIn(credentials)
    setPreferredLanguage(data)
    setSession({ user: data.user, tenant: data.tenant })
    return data
  }, [])

  const signOut = useCallback(async () => {
    await apiSignOut()
    setSession(null)
  }, [])

  const value = useMemo(
    () => ({ session, loading, signIn, signOut, setSession }),
    [session, loading, signIn, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
