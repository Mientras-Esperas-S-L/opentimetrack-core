import { Link as RouterLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import Avatar from '@mui/material/Avatar'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Divider from '@mui/material/Divider'
import List from '@mui/material/List'
import ListItem from '@mui/material/ListItem'
import ListItemAvatar from '@mui/material/ListItemAvatar'
import ListItemText from '@mui/material/ListItemText'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'

import { getOverview } from '../../services/api.js'
import { Empty, Loading, PageHeader, Panel, SourceChip } from '../../components/common.jsx'
import { dateOf, plural, timeOf } from '../../components/format.js'
import { useAuth } from '../../hooks/useAuth.js'

/** A number with its meaning under it, and a colour only when it wants
 *  attention. Four neutral figures in a row are impossible to scan. */
function Figure({ value, label, tone = 'default', to }) {
  const wants = tone === 'attention' && value > 0
  return (
    <Paper
      variant="outlined"
      component={to ? RouterLink : 'div'}
      to={to}
      sx={{
        p: 2,
        textDecoration: 'none',
        display: 'block',
        borderColor: wants ? 'secondary.main' : 'divider',
        ...(to && { '&:hover': { borderColor: 'primary.main' } }),
      }}
    >
      <Typography
        sx={{
          fontSize: '2rem',
          fontWeight: 650,
          lineHeight: 1.1,
          fontVariantNumeric: 'tabular-nums',
          color: wants ? 'secondary.main' : 'text.primary',
        }}
      >
        {value}
      </Typography>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
    </Paper>
  )
}

/** The week as bars. Deliberately unlabelled beyond the day initial: it shows
 *  the shape of the week, and calling it hours would be a lie --- these are
 *  events, and hours need pairing and closing open days. */
function WeekBars({ week }) {
  const { t } = useTranslation()
  const max = Math.max(1, ...week.events)
  const initials = ['D', 'L', 'M', 'X', 'J', 'V', 'S']

  return (
    <Stack direction="row" sx={{ gap: 1, alignItems: 'flex-end', height: 84 }}>
      {week.days.map((day, i) => {
        const value = week.events[i]
        const isToday = i === week.days.length - 1
        return (
          <Stack key={day} sx={{ flex: 1, alignItems: 'center', gap: 0.5 }}>
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>
              {value || ''}
            </Typography>
            <Box
              title={t('{{dia}}: {{cuantos}} eventos', { dia: dateOf(day), cuantos: value })}
              sx={{
                width: '100%',
                height: `${Math.max(3, (value / max) * 56)}px`,
                borderRadius: 0.75,
                bgcolor: isToday ? 'primary.main' : 'action.selected',
              }}
            />
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>
              {initials[new Date(`${day}T00:00:00`).getDay()]}
            </Typography>
          </Stack>
        )
      })}
    </Stack>
  )
}

export default function Overview() {
  const { t } = useTranslation()
  const { session } = useAuth()
  const zone = session?.tenant?.time_zone

  const { data, isLoading } = useQuery({
    queryKey: ['overview'],
    queryFn: getOverview,
    refetchInterval: 60000,
  })

  if (isLoading || !data) {
    return (
      <>
        <PageHeader title={t('Resumen')} />
        <Loading rows={4} />
      </>
    )
  }

  // Las cuatro colas que se pueden contar barato. Sumaba solo dos de las cinco
  // ---ausencias y correcciones pendientes--- y se dejaba fuera las propuestas
  // sin contestar, que era la más grande: la tarjeta decía «2» con 57 esperando.
  //
  // Y este número es lo que decide si alguien entra en «Por decidir», así que
  // equivocarlo a la baja no es un detalle: es una cola que nadie mira.
  const espera = data.awaiting_decision
  const waiting =
    espera.absences +
    espera.corrections +
    (espera.awaiting_employee ?? 0) +
    (espera.recoveries ?? 0) +
    // Las horas extra entran en la cifra grande ahora que se pueden contar.
    // Quedarse fuera era el fallo de la vuelta 2 en pequeño: la portada decía
    // un número y «Por decidir» tenía más cosas que ese número.
    (espera.overtime ?? 0)

  // Las horas extra ya traen número. Venían sin él porque contarlas costaba
  // medio segundo y esto se refresca cada minuto; ahora la misma lectura son
  // cinco consultas. Se sigue aceptando la forma vieja por si un servidor sin
  // actualizar responde solo con el «hay».
  const horasExtra = espera.overtime
  const hayHorasExtra = horasExtra > 0 || (horasExtra === undefined && espera.overtime_pending)

  return (
    <>
      <PageHeader
        title={t('Resumen')}
        subtitle={t('Situación de {{dia}}. Se actualiza cada minuto.', {
          dia: dateOf(data.date, { weekday: 'long', year: undefined }),
        })}
      />

      <Box
        sx={{
          display: 'grid',
          gap: 2,
          gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' },
          mb: 3,
        }}
      >
        <Figure value={data.working_now.length} label={t('trabajando ahora')} />
        <Figure value={data.off_today.length} label={t('fuera hoy')} />
        <Figure
          value={waiting}
          label={t('esperando decisión')}
          tone="attention"
          to="/panel/decisiones"
        />
        <Figure
          value={data.headcount}
          label={plural(data.headcount, t('persona de alta'), t('personas de alta'))}
          to="/panel/personas"
        />
      </Box>

      <Box
        sx={{
          display: 'grid',
          gap: 2,
          gridTemplateColumns: { xs: '1fr', lg: '1.4fr 1fr' },
          alignItems: 'start',
        }}
      >
        <Panel
          title={t('Trabajando ahora')}
          hint={t(
            'Quien tiene una entrada sin salida hoy. Sale del registro, no de un estado aparte.',
          )}
        >
          {data.working_now.length === 0 ? (
            <Empty>{t('Nadie ha fichado la entrada todavía.')}</Empty>
          ) : (
            <List disablePadding>
              {data.working_now.map((person, i) => (
                <Box key={person.employee}>
                  {i > 0 && <Divider component="li" />}
                  <ListItem disableGutters secondaryAction={<SourceChip source={person.source} />}>
                    <ListItemAvatar sx={{ minWidth: 46 }}>
                      <Avatar sx={{ width: 32, height: 32, fontSize: '0.8rem' }}>
                        {person.name.slice(0, 1)}
                      </Avatar>
                    </ListItemAvatar>
                    <ListItemText
                      primary={person.name}
                      secondary={t('desde las {{hora}}', {
                        hora: timeOf(person.since, zone),
                      })}
                    />
                  </ListItem>
                </Box>
              ))}
            </List>
          )}
        </Panel>

        <Stack sx={{ gap: 2 }}>
          <Panel title={t('La semana')} hint={t('Eventos de fichaje por día. No son horas.')}>
            <WeekBars week={data.week} />
          </Panel>

          <Panel title={t('Fuera hoy')}>
            {data.off_today.length === 0 ? (
              <Empty>{t('Nadie tiene ausencia aprobada para hoy.')}</Empty>
            ) : (
              <List disablePadding dense>
                {data.off_today.map((person) => (
                  <ListItem key={person.employee} disableGutters>
                    <ListItemText
                      primary={person.name}
                      secondary={t('{{tipo}} · hasta el {{fecha}}', {
                        tipo: person.type_display,
                        fecha: dateOf(person.until),
                      })}
                    />
                  </ListItem>
                ))}
              </List>
            )}
          </Panel>

          {(waiting > 0 || hayHorasExtra) && (
            <Button
              component={RouterLink}
              to="/panel/decisiones"
              variant="contained"
              size="large"
              fullWidth
            >
              {waiting > 0
                ? t('Resolver {{cuantas}} {{unidad}}', {
                    cuantas: waiting,
                    unidad: plural(waiting, t('solicitud'), t('solicitudes')),
                  })
                : t('Ver las horas extra por resolver')}
            </Button>
          )}
          {horasExtra > 0 && (
            <Typography variant="caption" color="text.secondary" sx={{ textAlign: 'center' }}>
              {horasExtra === 1
                ? t(
                    'Uno de ellos son horas extra del mes, con cuatro meses de plazo para compensarse con descanso (art. 35.1).',
                  )
                : t(
                    '{{cuantos}} de ellos son horas extra del mes, con cuatro meses de plazo para compensarse con descanso (art. 35.1).',
                    { cuantos: horasExtra },
                  )}
            </Typography>
          )}
        </Stack>
      </Box>
    </>
  )
}
