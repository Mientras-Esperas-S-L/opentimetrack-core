import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward'
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward'

import { getEmployees, getPunches } from '../../services/api.js'
import { Empty, Loading, PageHeader, SourceChip } from '../../components/common.jsx'
import { dateOf, timeOf } from '../../components/format.js'
import { useAuth } from '../../hooks/useAuth.js'

/** Groups the flat list of events by local day, newest first.
 *
 *  The API returns events; a person reads days. Doing it here rather than
 *  server-side keeps the endpoint honest --- it returns the record as stored ---
 *  and the grouping is presentation.
 */
function byDay(punches, zone) {
  const groups = new Map()
  for (const punch of punches) {
    const day = new Date(punch.timestamp).toLocaleDateString('sv-SE', { timeZone: zone })
    if (!groups.has(day)) groups.set(day, [])
    groups.get(day).push(punch)
  }
  return [...groups.entries()].sort((a, b) => b[0].localeCompare(a[0]))
}

export default function Timesheet() {
  const { session } = useAuth()
  const zone = session?.tenant?.time_zone

  const [employee, setEmployee] = useState('')

  const { data: people = [] } = useQuery({
    queryKey: ['employees', 'for-filter'],
    queryFn: () => getEmployees({ is_active: true }),
  })

  const { data: punches, isLoading } = useQuery({
    queryKey: ['punches', { employee }],
    queryFn: () => getPunches({ employee: employee || undefined, ordering: '-timestamp' }),
  })

  const days = byDay(punches ?? [], zone)

  return (
    <>
      <PageHeader
        title="Fichajes"
        subtitle="El registro tal y como está guardado. Un fichaje anulado sigue siendo legible: no se borra nada."
      />

      <TextField
        select
        size="small"
        label="Persona"
        value={employee}
        onChange={(event) => setEmployee(event.target.value)}
        sx={{ minWidth: 260, mb: 2 }}
      >
        <MenuItem value="">Toda la empresa</MenuItem>
        {people.map((person) => (
          <MenuItem key={person.id} value={person.id}>
            {`${person.first_name} ${person.last_name}`.trim() || person.email}
          </MenuItem>
        ))}
      </TextField>

      {isLoading ? (
        <Loading rows={6} />
      ) : days.length === 0 ? (
        <Empty>No hay fichajes registrados todavía.</Empty>
      ) : (
        <Stack sx={{ gap: 2 }}>
          {days.map(([day, events]) => (
            <Box key={day}>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{
                  display: 'block',
                  mb: 0.75,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                }}
              >
                {dateOf(day, { weekday: 'long', year: 'numeric' })}
              </Typography>

              <TableContainer component={Paper} variant="outlined" sx={{ overflowX: 'auto' }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ width: 92 }}>Hora</TableCell>
                      <TableCell sx={{ width: 110 }}>Tipo</TableCell>
                      {!employee && <TableCell>Persona</TableCell>}
                      <TableCell align="right">Origen</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {events.map((punch) => (
                      <TableRow
                        key={punch.id}
                        hover
                        sx={{
                          // A voided event stays in the list, struck through:
                          // hiding it would misrepresent the record.
                          ...(punch.is_active === false && {
                            opacity: 0.5,
                            textDecoration: 'line-through',
                          }),
                        }}
                      >
                        <TableCell sx={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
                          {timeOf(punch.timestamp, zone)}
                        </TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            variant={punch.punch_type === 'IN' ? 'filled' : 'outlined'}
                            color={punch.punch_type === 'IN' ? 'success' : 'default'}
                            icon={
                              punch.punch_type === 'IN' ? (
                                <ArrowDownwardIcon sx={{ fontSize: 14 }} />
                              ) : (
                                <ArrowUpwardIcon sx={{ fontSize: 14 }} />
                              )
                            }
                            label={punch.punch_type === 'IN' ? 'Entrada' : 'Salida'}
                            sx={{ height: 22, fontSize: '0.72rem' }}
                          />
                        </TableCell>
                        {!employee && (
                          <TableCell>
                            <Typography variant="body2">{punch.employee_name ?? '—'}</Typography>
                          </TableCell>
                        )}
                        <TableCell align="right">
                          <SourceChip source={punch.source} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          ))}
        </Stack>
      )}
    </>
  )
}
