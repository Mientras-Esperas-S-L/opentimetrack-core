import Box from '@mui/material/Box'
import CircularProgress from '@mui/material/CircularProgress'

import Clock from './pages/Clock.jsx'
import SignIn from './pages/SignIn.jsx'
import { useAuth } from './hooks/useAuth.js'

export default function App() {
  const { session, loading } = useAuth()

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress />
      </Box>
    )
  }

  return session ? <Clock /> : <SignIn />
}
