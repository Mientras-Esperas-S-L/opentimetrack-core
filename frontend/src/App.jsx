import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
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
import Workplaces from './pages/admin/Workplaces.jsx'
import TeamCalendar from './pages/admin/TeamCalendar.jsx'
import Roster from './pages/admin/Roster.jsx'
import LeaveTypes from './pages/admin/LeaveTypes.jsx'
import ShiftPatterns from './pages/admin/ShiftPatterns.jsx'
import Settings from './pages/admin/Settings.jsx'
import Applications from './pages/admin/Applications.jsx'
import Timesheet from './pages/admin/Timesheet.jsx'
import Decisions from './pages/admin/Decisions.jsx'
import Reports from './pages/admin/Reports.jsx'
import { useAuth } from './hooks/useAuth.js'

export default function App() {
  const { session, loading, unreachable } = useAuth()

  if (loading) {
    return (
      <Box
        sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}
      >
        <CircularProgress />
      </Box>
    )
  }

  // Sesión buena, servidor que no contesta. Antes se caía al formulario de
  // entrada: se le pedía la contraseña a quien la tenía viva, y volver a entrar
  // daba el mismo error. El mensaje del servidor ya dice cuánto falta.
  if (!session && unreachable) {
    return (
      <Box sx={{ maxWidth: 460, mx: 'auto', mt: 8, px: 2 }}>
        <Alert
          severity="warning"
          variant="outlined"
          action={
            <Button color="inherit" size="small" onClick={() => window.location.reload()}>
              Reintentar
            </Button>
          }
        >
          No hemos podido comprobar tu sesión. {unreachable.message ?? ''} Tu sesión sigue guardada:
          no hace falta volver a entrar.
        </Alert>
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
              <Route path="centros" element={<Workplaces />} />
              <Route path="calendario" element={<TeamCalendar />} />
              <Route path="cuadrante" element={<Roster />} />
              <Route path="turnos" element={<ShiftPatterns />} />
            <Route path="permisos" element={<LeaveTypes />} />
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
