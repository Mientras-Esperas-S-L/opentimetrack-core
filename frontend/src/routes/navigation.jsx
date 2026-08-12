import AccessTimeIcon from '@mui/icons-material/AccessTime'
import BeachAccessIcon from '@mui/icons-material/BeachAccess'
import ApartmentIcon from '@mui/icons-material/Apartment'
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth'
import EditCalendarIcon from '@mui/icons-material/EditCalendar'
import ScheduleIcon from '@mui/icons-material/Schedule'
import DescriptionIcon from '@mui/icons-material/Description'
import GroupsIcon from '@mui/icons-material/Groups'
import HistoryIcon from '@mui/icons-material/History'
import PolicyIcon from '@mui/icons-material/Policy'
import RuleIcon from '@mui/icons-material/Rule'
import SettingsIcon from '@mui/icons-material/Settings'
import SpaceDashboardIcon from '@mui/icons-material/SpaceDashboard'

/** The two halves of the application, kept in one place.
 *
 *  The split is not cosmetic: everything under "Mi trabajo" is about the person
 *  using it and needs no privilege, everything under "Gestión" is about other
 *  people and does. Adding a screen to the wrong list is the kind of mistake
 *  that shows one worker another's absences, so the lists are separate and the
 *  routes are guarded again on their own.
 */

export const NAV_ME = [
  { to: '/', label: 'Fichar', icon: <AccessTimeIcon />, end: true },
  { to: '/mi-jornada', label: 'Mi jornada', icon: <HistoryIcon /> },
  { to: '/mis-ausencias', label: 'Mis ausencias', icon: <BeachAccessIcon /> },
  // Aqui y no en Gestion: si el registro sirve para saber quien ha leido tu
  // ficha, la persona cuya ficha es tiene que poder mirarlo.
  { to: '/actividad', label: 'Actividad', icon: <PolicyIcon /> },
]

export const NAV_ADMIN = [
  { to: '/panel', label: 'Resumen', icon: <SpaceDashboardIcon /> },
  { to: '/panel/personas', label: 'Personas', icon: <GroupsIcon /> },
  { to: '/panel/departamentos', label: 'Departamentos', icon: <ApartmentIcon /> },
  { to: '/panel/calendario', label: 'Calendario', icon: <CalendarMonthIcon /> },
  { to: '/panel/cuadrante', label: 'Cuadrante', icon: <EditCalendarIcon /> },
  { to: '/panel/turnos', label: 'Turnos', icon: <ScheduleIcon /> },
  { to: '/panel/fichajes', label: 'Fichajes', icon: <AccessTimeIcon /> },
  { to: '/panel/decisiones', label: 'Por decidir', icon: <RuleIcon /> },
  { to: '/panel/informes', label: 'Informes', icon: <DescriptionIcon /> },
  { to: '/panel/ajustes', label: 'Ajustes', icon: <SettingsIcon /> },
]
