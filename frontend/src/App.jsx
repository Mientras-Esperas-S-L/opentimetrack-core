import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Box from '@mui/material/Box'
import CircularProgress from '@mui/material/CircularProgress'

import AppShell from './routes/AppShell.jsx'
import RequireManager from './routes/RequireManager.jsx'
import SignIn from './pages/SignIn.jsx'
import SetPassword from './pages/SetPassword.jsx'
import Clock from './pages/Clock.jsx'
import MyTime from './pages/me/MyTime.jsx'
import MyLeave from './pages/me/MyLeave.jsx'
import AuditTrail from './pages/admin/AuditTrail.jsx'
import Overview from './pages/admin/Overview.jsx'
import People from './pages/admin/People.jsx'
import Departments from './pages/admin/Departments.jsx'
import TeamCalendar from './pages/admin/TeamCalendar.jsx'
import Roster from './pages/admin/Roster.jsx'
import ShiftPatterns from './pages/admin/ShiftPatterns.jsx'
import Settings from './pages/admin/Settings.jsx'
import Applications from './pages/admin/Applications.jsx'
import Timesheet from './pages/admin/Timesheet.jsx'
import Decisions from './pages/admin/Decisions.jsx'
import Reports from './pages/admin/Reports.jsx'
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

  return (
    <BrowserRouter>
      <Routes>
        {/* Public, and outside the session check on purpose. Somebody arriving
            from the invitation email has no session by definition; while this
            lived behind it the link fell through to the catch-all and landed on
            the clock, so an invited person could never get a password. */}
        <Route path="set-password/:uid/:token" element={<SetPassword />} />

        {!session ? (
          <Route path="*" element={<SignIn />} />
        ) : (
        <Route element={<AppShell />}>
          <Route index element={<Clock />} />
          <Route path="mi-jornada" element={<MyTime />} />
          <Route path="mis-ausencias" element={<MyLeave />} />
          <Route path="actividad" element={<AuditTrail />} />

          {/* Guarded again here, not only hidden from the menu: a hidden link
              is not a permission, and these routes read other people's data. */}
          <Route path="panel" element={<RequireManager />}>
            <Route index element={<Overview />} />
            <Route path="personas" element={<People />} />
            <Route path="departamentos" element={<Departments />} />
            <Route path="calendario" element={<TeamCalendar />} />
            <Route path="cuadrante" element={<Roster />} />
            <Route path="turnos" element={<ShiftPatterns />} />
            <Route path="ajustes" element={<Settings />} />
            <Route path="aplicaciones" element={<Applications />} />
            <Route path="fichajes" element={<Timesheet />} />
            <Route path="decisiones" element={<Decisions />} />
            <Route path="informes" element={<Reports />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
        )}
      </Routes>
    </BrowserRouter>
  )
}
