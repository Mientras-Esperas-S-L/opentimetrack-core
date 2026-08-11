import { useContext } from 'react'

import { AuthContext } from '../context/authContext.js'

/** Lives apart from the provider so the module only exports components,
 *  which is what fast refresh needs to work. */
export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
