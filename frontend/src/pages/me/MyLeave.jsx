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
  getAbsenceCalendar,
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
import { useAuth } from '../../hooks/useAuth.js'
import { alCatalogo } from '../../i18n/index.js'

//: De dónde viene cada trozo de deuda. El artículo lo manda el servidor con la
//: fuente; esto es solo cómo se llama en una frase.
const ORIGENES = {
  overtime: alCatalogo('horas extra'),
  holiday: alCatalogo('festivos trabajados'),
  irregular: alCatalogo('jornada repartida de forma irregular'),
  night: alCatalogo('trabajo nocturno'),
}

/** Lo que se debe en descanso, de dónde viene y hasta cuándo hay para devolverlo.
 *
 *  Solo aparece cuando hay deuda: un saldo a cero de algo que no ha pasado nunca
 *  ocupa sitio y no dice nada.
 *
 *  La fecha es la mitad del asunto. «Te quedan 4 h» no sirve para nada sin «antes
 *  del 9 de septiembre», que es lo que permite no llegar tarde ---y llegar tarde
 *  no se arregla: pasado el plazo, el art. 35.1 está incumplido---.
 *
 *  **El desglose es la otra mitad.** Desde que hay más de una fuente ---horas
 *  extra del art. 35.1 y festivos trabajados del art. 37.2--- un total a secas no
 *  dice de dónde sale, y de dónde sale es lo que decide qué plazo corre: las
 *  extra vencen a los cuatro meses y el festivo no vence. Se enseña el total, que
 *  es lo que se disfruta, y debajo qué lo compone.
 */
function DeudaDeDescanso({ deuda }) {
  const { t } = useTranslation()
  const vencidas = Number(deuda.overdue_hours) > 0
  const quedan = Number(deuda.remaining_hours)
  const fuentes = deuda.sources ?? []

  return (
    <Alert severity={vencidas ? 'warning' : 'info'} variant="outlined" sx={{ mb: 2 }}>
      {vencidas &&
        // Sin citar ningún artículo: lo vencido puede venir de más de una fuente
        // ---horas extra del art. 35.1, la jornada repartida del 34.2--- y este
        // aviso citaba siempre el primero. Con ochenta horas del 34.2 decía que
        // eran horas extra y las atribuía al artículo que no era. Cada fuente
        // pone su artículo en su línea, que es donde se puede comprobar.
        t('Hay {{horas}} h de descanso que tenías que recuperar y se ha pasado el plazo.', {
          horas: deuda.overdue_hours,
        })}
      {!vencidas &&
        quedan > 0 &&
        (deuda.due_on && fuentes.length === 1
          ? t('Te quedan {{horas}} h de descanso por disfrutar, hasta el {{fecha}}.', {
              horas: quedan,
              fecha: dateOf(deuda.due_on, { year: 'numeric' }),
            })
          : // Sin fecha en el total. O ninguna fuente lleva plazo ---y poner una
            // inventada convertiría en «fuera de plazo» algo que no lo está---, o
            // hay varias y solo alguna vence: decir «te quedan 12 h hasta el 14
            // de diciembre» cuando solo vencen 4 es peor que no decir la fecha.
            // Cada plazo va en su línea del desglose.
            t('Te quedan {{horas}} h de descanso por disfrutar.', { horas: quedan }))}
      {!vencidas && quedan <= 0 && t('No queda descanso por recuperar.')}
      {fuentes.length > 1 && (
        <Box component="span" sx={{ display: 'block', mt: 0.5 }}>
          {/* Con una sola fuente el desglose sobra: el total ya la nombra. */}
          {fuentes.map((f) => (
            <Box component="span" key={f.source} sx={{ display: 'block' }}>
              {/* Tres casos y no dos. «Sin plazo» y «se pasó el plazo» son cosas
                  distintas: el art. 37.2 no da ninguno para el festivo
                  trabajado, y el 34.2 sí lo daba y ya venció. Decir «sin plazo»
                  de lo segundo suena a que no corre nada. */}
              {Number(f.overdue_hours) > 0
                ? t('{{horas}} h de {{origen}}, fuera de plazo ({{articulo}}).', {
                    horas: f.overdue_hours,
                    origen: ORIGENES[f.source] ? t(ORIGENES[f.source]) : f.source,
                    articulo: f.citation,
                  })
                : f.due_on
                  ? t('{{horas}} h de {{origen}}, hasta el {{fecha}} ({{articulo}}).', {
                      horas: f.owed_hours,
                      origen: ORIGENES[f.source] ? t(ORIGENES[f.source]) : f.source,
                      fecha: dateOf(f.due_on, { year: 'numeric' }),
                      articulo: f.citation,
                    })
                  : t('{{horas}} h de {{origen}}, sin plazo ({{articulo}}).', {
                      horas: f.owed_hours,
                      origen: ORIGENES[f.source] ? t(ORIGENES[f.source]) : f.source,
                      articulo: f.citation,
                    })}
            </Box>
          ))}
        </Box>
      )}
      {quedan > 0 && (
        <Box component="span" sx={{ display: 'block', mt: 0.5 }}>
          {/* Un aviso que dice lo que debes y no el siguiente paso obliga a
              adivinar por qué puerta se devuelve. El permiso se llama así en la
              lista de «Solicitar», y decirlo cuesta una frase. */}
          {t('Para disfrutarlo, pídelo como «Descanso compensatorio».')}
        </Box>
      )}
      {Number(deuda.unconverted_days) > 0 && (
        <Box component="span" sx={{ display: 'block', mt: 0.5 }}>
          {/* No se estima lo que no se sabe: un día sin turno previsto no dice
              cuántas horas devuelve, y ponerle una jornada tipo haría que el
              saldo pareciera saldado sin estarlo. */}
          {t(
            'Hay {{dias}} día(s) de descanso sin turno previsto, así que no se han podido contar en horas.',
            { dias: deuda.unconverted_days },
          )}
        </Box>
      )}
    </Alert>
  )
}

/** Quién fijó estas vacaciones: `propia`, `ajena` o `desconocida`.
 *
 *  Se lee de quién las pidió, y no de si hay plazo: sin este dato no se puede
 *  saber, y no saberlo es una respuesta legítima. Todo lo registrado antes de
 *  que el campo existiera cae aquí.
 */
const quienLasFijo = (tramo) => {
  if (!tramo.requested_by) return 'desconocida'
  return tramo.requested_by === tramo.employee ? 'propia' : 'ajena'
}

/** El calendario de vacaciones de esta persona, para el periodo en curso.
 *
 *  «El calendario de vacaciones se fijará en cada empresa. El trabajador
 *  conocerá las fechas que le correspondan dos meses antes, al menos, del
 *  comienzo del disfrute» (art. 38.3 ET).
 *
 *  **El sujeto del artículo es quien trabaja**, y era el único que no lo veía.
 *  El calendario del equipo existe desde hace tiempo y está tras el permiso de
 *  gestión; el aviso de que a alguien le fijaron las vacaciones con menos de dos
 *  meses lo veían quien las metió y quien las decide. La persona a la que le
 *  fijan las fechas ---la que tiene que reservar un vuelo, cuadrar con su pareja
 *  o apuntar a un crío a un campamento--- no lo veía en ninguna pantalla.
 *
 *  Y se dice **siempre** con cuánta antelación las supo, no solo cuando el plazo
 *  se incumple. Un plazo que solo se nota cuando falla no se puede comprobar:
 *  solo se puede padecer.
 */
function CalendarioDeVacaciones({ desde, hasta, quien }) {
  const { t } = useTranslation()
  const { data: tramos, isLoading } = useQuery({
    queryKey: ['mi-calendario-de-vacaciones', desde, hasta, quien],
    // Acotado a esta persona, y no filtrado después: quien tiene permiso de
    // gestión ve a los suyos, así que sin el filtro este panel enseñaba las
    // vacaciones de media empresa bajo un título que empieza por «Mi». Filtrarlo
    // en la pantalla tampoco valdría: los datos habrían viajado igual.
    queryFn: () => getAbsenceCalendar(desde, hasta, { employee: quien }),
    enabled: Boolean(desde && hasta && quien),
  })

  // Solo vacaciones: el plazo del art. 38.3 es de las vacaciones y de nada más,
  // y mezclar aquí una visita al médico convertiría el calendario en otra copia
  // del historial, que está justo debajo.
  const vacaciones = (tramos ?? []).filter((a) => a.absence_type === 'VACATION')

  return (
    <Panel
      title={t('Mi calendario de vacaciones')}
      hint={t('Las fechas que te corresponden en este periodo, y desde cuándo las sabes.')}
    >
      {isLoading ? (
        <Loading rows={2} />
      ) : vacaciones.length === 0 ? (
        <Empty>
          {/* Un estado vacío que solo dice «no hay nada» deja a quien lo lee sin
              saber si es que no le tocan vacaciones o es que el sistema no las
              tiene. Dice las dos puertas por las que llegan. */}
          {t(
            'Todavía no tienes vacaciones fijadas en este periodo. Aparecerán aquí en cuanto las pidas tú o te las fije la empresa.',
          )}
        </Empty>
      ) : (
        <Stack sx={{ gap: 1.5 }}>
          {vacaciones.map((tramo) => (
            <Box key={tramo.id}>
              <Stack
                direction="row"
                sx={{ gap: 1, alignItems: 'center', justifyContent: 'space-between' }}
              >
                <Typography sx={{ fontWeight: 600 }}>
                  {dayRange(tramo.start_date, tramo.end_date)}
                </Typography>
                <StatusChip status={tramo.status} label={tramo.status_display} />
              </Stack>
              <Typography variant="body2" color="text.secondary">
                {leaveLength(tramo)}
                {' · '}
                {/* Tres casos, no dos. `notice_days` es nulo tanto si las pidió
                    esta persona ---y entonces conoce las fechas por definición---
                    como si **no consta quién las fijó**, que es lo que hay en
                    todo lo registrado antes de que el dato existiera. Meter los
                    dos en la misma frase le diría a alguien que pidió unas
                    vacaciones que no pidió, y encima le quitaría el plazo. */}
                {quienLasFijo(tramo) === 'propia'
                  ? t('las pediste tú')
                  : quienLasFijo(tramo) === 'ajena'
                    ? t('te las fijó {{quien}}', {
                        quien: tramo.requested_by_name || t('la empresa'),
                      })
                    : t('no consta quién las fijó')}
              </Typography>
              {/* El aviso, en la pantalla de quien lo sufre. Antes solo llegaba a
                  quien las metió y a quien las decide: si el aviso de un plazo
                  que existe para proteger a alguien no le llega a esa persona,
                  el plazo lo comprueba justo quien no lo padece. */}
              {tramo.short_notice ? (
                <Alert severity="warning" variant="outlined" sx={{ mt: 0.5, py: 0 }}>
                  {t('Lo supiste con {{plazo}}, y el {{articulo}} pide {{minimo}}.', {
                    plazo: `${tramo.short_notice.days} ${plural(tramo.short_notice.days, t('día'), t('días'))}`,
                    articulo: tramo.short_notice.citation,
                    minimo: `${tramo.short_notice.required} ${t('días')}`,
                  })}
                </Alert>
              ) : (
                tramo.notice_days !== null && (
                  <Typography variant="caption" color="text.secondary">
                    {t('Lo supiste con {{plazo}} de antelación.', {
                      plazo: `${tramo.notice_days} ${plural(tramo.notice_days, t('día'), t('días'))}`,
                    })}
                  </Typography>
                )
              )}
            </Box>
          ))}
        </Stack>
      )}
    </Panel>
  )
}

/** The balance, as a bar plus the three numbers behind it.
 *
 *  Pending days are drawn separately from taken ones: they are not spent yet,
 *  but they are not available either, and a single figure hides which is which.
 */
function Balance({ balance }) {
  const { t } = useTranslation()
  const { entitled, taken, pending, remaining, period_start, period_end } = balance
  //: Los días que suma el convenio por antigüedad, y los años con los que se ha
  //: contado. Van aparte de la cifra grande porque «22 + 1 por antigüedad» es
  //: una frase que alguien puede comprobar, y «23» no.
  const porAntiguedad = Number(balance.seniority_days) || 0
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

      {porAntiguedad > 0 && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
          {t('Incluye {{cuantos}} {{unidad}} por antigüedad, con {{años}} años de servicio.', {
            cuantos: porAntiguedad,
            unidad: plural(porAntiguedad, t('día'), t('días')),
            años: balance.seniority_years,
          })}
        </Typography>
      )}

      {balance.seniority_unknown && (
        <Typography variant="caption" color="warning.main" sx={{ display: 'block', mb: 1 }}>
          {/* Ni se estima ni se calla: contar cero años le quitaría sus días
              justo a quien más lleva, y hacerlo en silencio es lo peor de las
              dos cosas. Solo la empresa puede poner esa fecha. */}
          {t(
            'Tu convenio suma días por antigüedad y no consta tu fecha de inicio de contrato, así que no se han podido contar.',
          )}
        </Typography>
      )}

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
  const { session } = useAuth()
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
        // Las suyas. Sin esto, quien tiene permiso de gestión veía aquí el
        // historial de toda la gente que lleva ---y las filas no dicen de quién
        // son--- mientras el saldo de arriba sí era el suyo. Dos cosas distintas
        // en la misma pantalla, sin nada que las separase.
        employee: session?.user?.id,
        ...(year ? { year } : {}),
        ...(status ? { status } : {}),
      }),
    placeholderData: (previous) => previous,
    enabled: Boolean(session?.user?.id),
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

      {balance?.rest_debt && <DeudaDeDescanso deuda={balance.rest_debt} />}

      <CalendarioDeVacaciones
        desde={balance?.period_start}
        hasta={balance?.period_end}
        quien={session?.user?.id}
      />

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
        noun={{ singular: alCatalogo('solicitud'), plural: alCatalogo('solicitudes') }}
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
