import { useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Box from '@mui/material/Box'
import Alert from '@mui/material/Alert'
import Autocomplete from '@mui/material/Autocomplete'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import LinearProgress from '@mui/material/LinearProgress'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import AddIcon from '@mui/icons-material/Add'
import AttachFileIcon from '@mui/icons-material/AttachFile'

import {
  cancelAbsence,
  downloadJustification,
  getAbsences,
  getLeaveBalance,
  PAGE_SIZE,
  requestAbsence,
} from '../../services/api.js'
import {
  ConfirmDialog,
  Empty,
  ErrorNote,
  Loading,
  PageHeader,
  Pager,
  Panel,
  StatusChip,
} from '../../components/common.jsx'
import LeaveDialog from '../../components/LeaveDialog.jsx'
import { dateOf, dayRange, leaveLabel, leaveLength, plural } from '../../components/format.js'
import { FilterBar, PickFilter } from '../../components/filters.jsx'

/** The balance, as a bar plus the three numbers behind it.
 *
 *  Pending days are drawn separately from taken ones: they are not spent yet,
 *  but they are not available either, and a single figure hides which is which.
 */
function Balance({ balance }) {
  const { t } = useTranslation()
  const { entitled, taken, pending, remaining, period_start, period_end } = balance
  const pct = (value) => (entitled > 0 ? (value / entitled) * 100 : 0)
  // Which unit the three figures are in. Without it "quedan 9" is ambiguous by
  // about a third, which is exactly how far the balance used to be wrong.
  const unit = balance.working_days ? t('laborables') : t('naturales')

  return (
    <Panel
      title={t('Vacaciones')}
      hint={t('Periodo del {{desde}} al {{hasta}}', {
        desde: dateOf(period_start, { year: 'numeric' }),
        hasta: dateOf(period_end, { year: 'numeric' }),
      })}
    >
      <Stack direction="row" sx={{ alignItems: 'baseline', gap: 1, mb: 1.5 }}>
        <Typography
          sx={{
            fontSize: '2.6rem',
            fontWeight: 650,
            lineHeight: 1,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {remaining}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {t('{{unidad}} {{computo}} de {{total}}', {
            unidad: plural(remaining, t('día'), t('días')),
            computo: unit,
            total: entitled,
          })}
        </Typography>
      </Stack>

      <Box
        sx={{
          position: 'relative',
          height: 10,
          borderRadius: 5,
          bgcolor: 'action.hover',
          overflow: 'hidden',
          mb: 1.5,
        }}
      >
        <Box sx={{ position: 'absolute', inset: 0, display: 'flex' }}>
          <Box sx={{ width: `${pct(taken)}%`, bgcolor: 'primary.main' }} />
          <Box
            sx={{
              width: `${pct(pending)}%`,
              // Hatched, not just a lighter tint: "asked for" and "taken" are
              // different states and should not read as shades of the same one.
              backgroundImage: (t) =>
                `repeating-linear-gradient(45deg, ${t.palette.primary.main} 0 4px, transparent 4px 8px)`,
            }}
          />
        </Box>
      </Box>

      <Stack direction="row" sx={{ gap: 3, flexWrap: 'wrap' }}>
        <Typography variant="caption" color="text.secondary">
          <Trans
            i18nKey="<destacado>{{cuantos}}</destacado> disfrutados"
            values={{ cuantos: taken }}
            components={{ destacado: <strong /> }}
          />
        </Typography>
        <Typography variant="caption" color="text.secondary">
          <Trans
            i18nKey="<destacado>{{cuantos}}</destacado> solicitados sin resolver"
            values={{ cuantos: pending }}
            components={{ destacado: <strong /> }}
          />
        </Typography>
      </Stack>
    </Panel>
  )
}

/** El grupo al que pertenece cada permiso, para agrupar el desplegable.
 *
 *  Diecisiete entradas en una lista plana son diecisiete entradas que hay que
 *  leer enteras. Agrupadas son cuatro decisiones: si son vacaciones, una baja,
 *  un permiso retribuido o uno sin sueldo.
 */
export default function MyLeave() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(1)
  const [confirming, setConfirming] = useState(null)
  //: Año y estado. Con tres años de antigüedad el historial es una lista larga
  //: en la que hay que bajar buscando, y lo que se busca casi siempre es «las
  //: de este año» o «las que están sin resolver».
  const esteAño = new Date().getFullYear()
  const [year, setYear] = useState(String(esteAño))
  const [status, setStatus] = useState('')

  const { data: balance } = useQuery({
    queryKey: ['leave-balance'],
    queryFn: () => getLeaveBalance(),
  })
  const { data: absences, isLoading } = useQuery({
    queryKey: ['absences', 'mine', page, year, status],
    queryFn: () =>
      getAbsences({
        page,
        ...(year ? { year } : {}),
        ...(status ? { status } : {}),
      }),
    placeholderData: (previous) => previous,
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['absences'] })
    queryClient.invalidateQueries({ queryKey: ['leave-balance'] })
  }

  const ask = useMutation({
    mutationFn: requestAbsence,
    onSuccess: () => {
      setAsking(false)
      setError(null)
      refresh()
    },
    onError: setError,
  })

  const withdraw = useMutation({
    mutationFn: cancelAbsence,
    onSuccess: refresh,
    onError: setError,
  })

  const rows = absences?.rows ?? []

  return (
    <>
      <PageHeader
        title={t('Mis ausencias')}
        subtitle={t(
          'Vacaciones, permisos y bajas. Una ausencia aprobada bloquea el fichaje en esas fechas.',
        )}
        action={
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => setAsking(true)}>
            {t('Solicitar')}
          </Button>
        }
      />

      <ErrorNote error={error} onClose={() => setError(null)} />

      {balance ? <Balance balance={balance} /> : <LinearProgress sx={{ mb: 2 }} />}

      <Typography variant="h2" sx={{ fontSize: '1rem', mt: 3, mb: 1.5 }}>
        {t('Historial')}
      </Typography>

      <FilterBar>
        {/* Cinco años hacia atrás: el registro se conserva cuatro, así que más
            allá no hay nada que enseñar. «Todos» al final y no al principio,
            porque casi nadie lo quiere. */}
        <PickFilter
          label={t('Año')}
          value={year}
          onChange={(valor) => {
            setYear(valor)
            setPage(1)
          }}
          options={Array.from({ length: 5 }, (_, i) => ({
            value: String(esteAño - i),
            label: String(esteAño - i),
          }))}
          all={t('Todos')}
          width={130}
        />
        <PickFilter
          label={t('Estado')}
          value={status}
          onChange={(valor) => {
            setStatus(valor)
            setPage(1)
          }}
          options={[
            { value: 'PENDING', label: t('Sin resolver') },
            { value: 'APPROVED', label: t('Aprobada') },
            { value: 'REJECTED', label: t('Rechazada') },
            { value: 'CANCELLED', label: t('Cancelada') },
          ]}
          all={t('Todos')}
          width={170}
        />
      </FilterBar>

      {isLoading ? (
        <Loading rows={3} />
      ) : rows.length === 0 ? (
        <Empty>
          {/* Con un filtro puesto, «no has solicitado ninguna» sería mentira:
              las hay, pero en otro año o en otro estado. Y es una mentira que
              se cree, porque el filtro está arriba y el mensaje abajo. */}
          {year || status
            ? t('Ninguna ausencia coincide con lo que has elegido arriba.')
            : t('Todavía no has solicitado ninguna ausencia.')}
        </Empty>
      ) : (
        <Stack sx={{ gap: 1 }}>
          {rows.map((absence) => (
            <Paper key={absence.id} variant="outlined" sx={{ p: 2 }}>
              <Stack
                direction={{ xs: 'column', sm: 'row' }}
                sx={{ gap: 1.5, justifyContent: 'space-between', alignItems: { sm: 'center' } }}
              >
                <Box sx={{ minWidth: 0 }}>
                  {/* El nombre arriba y la duración abajo, con las fechas. Estuvo
                      un rato diciendo «Visita médica · 1 días» y repitiendo la
                      duración dos líneas seguidas: la de arriba contaba días
                      completos incluso cuando la ausencia eran dos horas y
                      media. */}
                  <Typography sx={{ fontWeight: 600 }}>{leaveLabel(absence)}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {dayRange(absence.start_date, absence.end_date)} · {leaveLength(absence)}
                    {absence.basis && (
                      <Typography component="span" variant="caption" sx={{ ml: 1 }}>
                        ({absence.basis})
                      </Typography>
                    )}
                  </Typography>
                  {absence.reason && (
                    <Typography variant="body2" sx={{ mt: 0.5, fontStyle: 'italic' }}>
                      {absence.reason}
                    </Typography>
                  )}
                  {absence.resolved_by_name && (
                    <Typography variant="caption" color="text.secondary">
                      {t('Resuelta por {{quien}} el {{fecha}}', {
                        quien: absence.resolved_by_name,
                        fecha: dateOf(absence.resolved_at),
                      })}
                    </Typography>
                  )}
                </Box>

                <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexShrink: 0 }}>
                  {absence.has_justification && (
                    <Button
                      size="small"
                      startIcon={<AttachFileIcon />}
                      // Con `catch`, y no es una precaución de manual: la
                      // descarga puede fallar por cosas que no se ven --- en
                      // producción el fichero lo sirve el almacén de objetos, y
                      // si su dominio no está en la CSP el navegador corta la
                      // redirección. Sin esto, la promesa se rechazaba sin que
                      // nadie la recogiera: ni aviso, ni fichero, y quien lo
                      // sufre lee «la aplicación no responde».
                      onClick={() =>
                        downloadJustification(absence.id).catch((fallo) =>
                          setError(
                            fallo?.message
                              ? fallo
                              : {
                                  code: 'download_failed',
                                  message: t('No se pudo descargar el justificante.'),
                                },
                          ),
                        )
                      }
                    >
                      {t('Justificante')}
                    </Button>
                  )}
                  <StatusChip status={absence.status} label={absence.status_display} />
                  {absence.status === 'PENDING' && (
                    <Button
                      size="small"
                      color="inherit"
                      onClick={() =>
                        setConfirming({
                          title: t('Retirar la solicitud'),
                          body: `${leaveLabel(absence)} · ${dayRange(absence.start_date, absence.end_date)}`,
                          detail: t(
                            'Deja de estar pendiente de respuesta. Puedes volver a pedirla, pero esta solicitud queda retirada en el historial.',
                          ),
                          verb: t('Retirar'),
                          run: () => withdraw.mutate(absence.id),
                        })
                      }
                      disabled={withdraw.isPending}
                    >
                      {t('Retirar')}
                    </Button>
                  )}
                </Stack>
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}

      <Pager
        count={absences?.count ?? 0}
        page={page}
        pageSize={PAGE_SIZE}
        onChange={setPage}
        noun={{ singular: 'solicitud', plural: 'solicitudes' }}
      />

      <ConfirmDialog
        request={confirming}
        busy={withdraw.isPending}
        onClose={() => setConfirming(null)}
      />

      <LeaveDialog
        open={asking}
        saving={ask.isPending}
        error={error}
        onClose={() => {
          setAsking(false)
          setError(null)
        }}
        onSubmit={ask.mutate}
      />
    </>
  )
}
