import AccessTimeIcon from '@mui/icons-material/AccessTime'
import BeachAccessIcon from '@mui/icons-material/BeachAccess'
import DescriptionIcon from '@mui/icons-material/Description'
import GroupsIcon from '@mui/icons-material/Groups'
import HistoryIcon from '@mui/icons-material/History'
import RuleIcon from '@mui/icons-material/Rule'
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
]

export const NAV_ADMIN = [
  { to: '/panel', label: 'Resumen', icon: <SpaceDashboardIcon /> },
  { to: '/panel/personas', label: 'Personas', icon: <GroupsIcon /> },
  { to: '/panel/fichajes', label: 'Fichajes', icon: <AccessTimeIcon /> },
  { to: '/panel/decisiones', label: 'Por decidir', icon: <RuleIcon /> },
  { to: '/panel/informes', label: 'Informes', icon: <DescriptionIcon /> },
]
