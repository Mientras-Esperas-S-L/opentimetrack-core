import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery } from '@tanstack/react-query'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import DownloadIcon from '@mui/icons-material/Download'

import { downloadReport, getHoursWorked } from '../services/api.js'
import { save } from '../services/download.js'
import { alCatalogo } from '../i18n/index.js'
import {
  capitalised,
  dateOf,
  dayRange,
  durationOf,
  monthBounds,
  monthName,
  plural,
} from './format.js'
import { ErrorNote, Loading, Panel } from './common.jsx'

const PERIODOS = [
  { clave: 'semana', texto: alCatalogo('Esta semana') },
  { clave: 'semana-pasada', texto: alCatalogo('La semana pasada') },
  { clave: 'mes', texto: alCatalogo('Este mes') },
  { clave: 'mes-pasado', texto: alCatalogo('El mes pasado') },
  { clave: 'anual', texto: alCatalogo('Este año') },
  { clave: 'fechas', texto: alCatalogo('Entre fechas') },
]

const DIA = 24 * 60 * 60 * 1000

// Todo en el calendario local y escrito como `yyyy-mm-dd`, igual que
// `monthBounds`: con `toISOString` el límite se movería un día de noche.
const iso = (fecha) => fecha.toLocaleDateString('sv-SE')
const deIso = (texto) => new Date(`${texto}T00:00:00`)
const masDias = (fecha, dias) =>
  new Date(fecha.getFullYear(), fecha.getMonth(), fecha.getDate() + dias)
// La semana empieza en lunes, como la cuenta el convenio y no como la pinta el
// calendario estadounidense.
const lunesDe = (fecha) => masDias(fecha, -((fecha.getDay() + 6) % 7))

function rangoDe(clave) {
  const hoy = new Date()
  const lunes = lunesDe(hoy)
  switch (clave) {
    case 'semana-pasada':
      return { from: iso(masDias(lunes, -7)), to: iso(masDias(lunes, -1)) }
    case 'mes':
      return { from: iso(new Date(hoy.getFullYear(), hoy.getMonth(), 1)), to: iso(hoy) }
    case 'mes-pasado':
      return monthBounds({ year: hoy.getFullYear(), month: hoy.getMonth() - 1 })
    case 'anual':
      return { from: iso(new Date(hoy.getFullYear(), 0, 1)), to: iso(hoy) }
    default:
      return { from: iso(lunes), to: iso(hoy) }
  }
}

/** El desglose que se lee de un vistazo según lo largo que sea el periodo.
 *
 *  Una semana, por días. Hasta un par de meses, por semanas. Más, por meses.
 *  Con los tramos sin horas incluidos: una semana en blanco es un dato, y
 *  quitarla haría que el desglose no sumara a la vista lo que dice el total.
 */
function desglose(dias, from, to, t) {
  const horas = new Map(dias.map((d) => [d.day, d.seconds]))
  const inicio = deIso(from)
  const fin = deIso(to)
  const largo = Math.round((fin - inicio) / DIA) + 1
  const filas = []

  if (largo <= 7) {
    for (let d = inicio; d <= fin; d = masDias(d, 1)) {
      filas.push({
        clave: iso(d),
        texto: capitalised(dateOf(iso(d), { weekday: 'long' })),
        seconds: horas.get(iso(d)) ?? 0,
      })
    }
    return filas
  }

  const suma = (desde, hasta) =>
    dias.filter((d) => d.day >= desde && d.day <= hasta).reduce((s, d) => s + d.seconds, 0)

  if (largo <= 62) {
    for (let lunes = lunesDe(inicio); lunes <= fin; lunes = masDias(lunes, 7)) {
      const desde = iso(lunes < inicio ? inicio : lunes)
      const domingo = masDias(lunes, 6)
      const hasta = iso(domingo > fin ? fin : domingo)
      filas.push({
        clave: desde,
        texto: t('Semana {{dias}}', { dias: dayRange(desde, hasta) }),
        seconds: suma(desde, hasta),
      })
    }
    return filas
  }

  for (
    let mes = new Date(inicio.getFullYear(), inicio.getMonth(), 1);
    mes <= fin;
    mes = new Date(mes.getFullYear(), mes.getMonth() + 1, 1)
  ) {
    const limites = monthBounds({ year: mes.getFullYear(), month: mes.getMonth() })
    filas.push({
      clave: limites.from,
      texto: capitalised(monthName({ year: mes.getFullYear(), month: mes.getMonth() })),
      seconds: suma(limites.from, limites.to),
    })
  }
  return filas
}

/** «¿Cuánto he trabajado?», para la semana, el mes o las fechas que uno elija.
 *
 *  Las cifras son las del informe que se descarga, calculadas en el servidor:
 *  la pausa que no cuenta, la jornada que cruza la medianoche y la regla de
 *  cada día ya están resueltas allí. Sumarlas aquí acabaría diciendo otra cosa
 *  que el documento.
 */
export default function MisHoras() {
  const { t } = useTranslation()
  const [periodo, setPeriodo] = useState('semana')
  const [fechas, setFechas] = useState(() => rangoDe('mes'))
  const [error, setError] = useState(null)

  const rango = periodo === 'fechas' ? fechas : rangoDe(periodo)
  const valido = Boolean(rango.from && rango.to) && rango.from <= rango.to

  const { data, isLoading, error: fallo } = useQuery({
    queryKey: ['hours', 'mine', rango.from, rango.to],
    queryFn: () => getHoursWorked({ date_from: rango.from, date_to: rango.to }),
    enabled: valido,
    placeholderData: (previous) => previous,
  })

  const bajar = useMutation({
    mutationFn: () => downloadReport({ date_from: rango.from, date_to: rango.to, format: 'pdf' }),
    onSuccess: save,
    onError: setError,
  })

  const dias = data?.days ?? []
  const filas = data ? desglose(dias, rango.from, rango.to, t) : []
  const mayor = Math.max(...filas.map((f) => f.seconds), 1)

  return (
    <Panel
      title={t('Cuánto he trabajado')}
      hint={t('Las mismas cifras que el informe que descargas.')}
      sx={{ mb: 3 }}
    >
      <ErrorNote error={error ?? fallo} onClose={error ? () => setError(null) : undefined} />

      <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap', mb: 2 }}>
        {PERIODOS.map(({ clave, texto }) => (
          <Chip
            key={clave}
            label={t(texto)}
            color={periodo === clave ? 'primary' : 'default'}
            variant={periodo === clave ? 'filled' : 'outlined'}
            onClick={() => setPeriodo(clave)}
            aria-pressed={periodo === clave}
          />
        ))}
      </Stack>

      {periodo === 'fechas' && (
        <Stack direction="row" sx={{ gap: 2, flexWrap: 'wrap', mb: 2 }}>
          <TextField
            type="date"
            size="small"
            label={t('Desde')}
            value={fechas.from}
            onChange={(event) => setFechas({ ...fechas, from: event.target.value })}
            slotProps={{ inputLabel: { shrink: true }, htmlInput: { max: fechas.to } }}
          />
          <TextField
            type="date"
            size="small"
            label={t('Hasta')}
            value={fechas.to}
            onChange={(event) => setFechas({ ...fechas, to: event.target.value })}
            error={Boolean(fechas.from && fechas.to) && !valido}
            helperText={
              Boolean(fechas.from && fechas.to) && !valido
                ? t('La fecha final no puede ir antes que la inicial.')
                : undefined
            }
            slotProps={{ inputLabel: { shrink: true }, htmlInput: { min: fechas.from } }}
          />
        </Stack>
      )}

      {!valido ? null : isLoading ? (
        <Loading rows={3} />
      ) : data ? (
        <>
          <Stack
            direction="row"
            sx={{ gap: 3, flexWrap: 'wrap', alignItems: 'flex-end', mb: filas.length ? 2 : 0 }}
          >
            <Box>
              <Typography variant="h5" sx={{ fontVariantNumeric: 'tabular-nums' }}>
                {durationOf(data.total_seconds / 60)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {t('trabajadas en {{cuantos}} {{unidad}}', {
                  cuantos: dias.length,
                  unidad: plural(dias.length, t('día'), t('días')),
                })}
              </Typography>
            </Box>
            {data.overtime_seconds > 0 && (
              <Box>
                <Typography variant="h6" sx={{ fontVariantNumeric: 'tabular-nums' }}>
                  {durationOf(data.overtime_seconds / 60)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {/* Son las que se ficharon como extra, no lo que pasa del turno. */}
                  {t('horas extra registradas')}
                </Typography>
              </Box>
            )}
            <Button
              size="small"
              variant="outlined"
              startIcon={<DownloadIcon />}
              disabled={bajar.isPending}
              onClick={() => bajar.mutate()}
              sx={{ ml: 'auto' }}
            >
              {t('Descargar este periodo')}
            </Button>
          </Stack>

          <Stack sx={{ gap: 0.75 }}>
            {filas.map((fila) => (
              <Box key={fila.clave}>
                <Stack direction="row" sx={{ justifyContent: 'space-between', gap: 2 }}>
                  <Typography variant="body2">{fila.texto}</Typography>
                  <Typography
                    variant="body2"
                    color={fila.seconds ? 'text.primary' : 'text.secondary'}
                    sx={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}
                  >
                    {fila.seconds ? durationOf(fila.seconds / 60) : '—'}
                  </Typography>
                </Stack>
                <Box sx={{ height: 4, borderRadius: 2, bgcolor: 'action.hover', mt: 0.25 }}>
                  <Box
                    sx={{
                      height: 1,
                      width: `${(fila.seconds / mayor) * 100}%`,
                      borderRadius: 2,
                      bgcolor: 'primary.main',
                    }}
                  />
                </Box>
              </Box>
            ))}
          </Stack>
        </>
      ) : null}
    </Panel>
  )
}
