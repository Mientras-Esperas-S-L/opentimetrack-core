import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import LoginIcon from '@mui/icons-material/Login'
import LogoutIcon from '@mui/icons-material/Logout'
import PauseIcon from '@mui/icons-material/PauseCircle'

import { useAuth } from '../hooks/useAuth.js'
import { clock, getMyShiftToday, getToday } from '../services/api.js'
import { hhmm, hhmmss, timeOf } from '../components/format.js'
import { serverAt, serverClockReady } from '../services/serverClock.js'
import { localeDeFechas } from '../i18n/index.js'

/** Un latido común, en el borde del segundo.
 *
 *  Los dos números de esta pantalla —la hora y el tiempo trabajado— tienen que
 *  saltar **a la vez**. Antes no lo hacían: el reloj se enganchaba al borde del
 *  segundo y el contador a un `setInterval` que arrancaba cuando llegara la
 *  respuesta, así que iban desfasados hasta un segundo y se notaba. Dos relojes
 *  que no coinciden en la misma pantalla dan sensación de aparato roto, y esta
 *  es justo la pantalla que no puede darla.
 *
 *  Un `setTimeout` recalculado cada vuelta, no un `setInterval`: el intervalo
 *  acumula el retraso de cada ciclo y con la pestaña en segundo plano se queda
 *  atrás sin recuperarse nunca.
 *
 *  Devuelve el instante, no un contador, y lo lee dentro del efecto: leer el
 *  reloj durante el render es impuro y React 19 lo rechaza.
 */
function useSecondTick() {
  const [now, setNow] = useState(0)

  useEffect(() => {
    let timer
    const beat = () => {
      setNow(Date.now())
      timer = setTimeout(beat, 1000 - (Date.now() % 1000))
    }
    beat()
    return () => clearTimeout(timer)
  }, [])

  return now
}

/** El tiempo trabajado hoy, al segundo y sin poder desviarse.
 *
 *  La primera versión sumaba segundos a lo que dijo el servidor, anclándolo al
 *  instante en que llegó la respuesta. Parecía razonable y estaba mal: entre
 *  que el servidor mide y el navegador ancla pasan la red y un render, así que
 *  el contador nacía adelantado. Con la entrada a las 07:02:00 clavadas y el
 *  reloj en 12:15:50 enseñaba 5:13:51, un segundo de más --- y al lado del
 *  reloj de pared se veía.
 *
 *  Ahora hace la misma cuenta que hace el servidor: los tramos cerrados tal y
 *  como vienen, y el abierto medido desde la hora de su fichaje de entrada
 *  hasta ahora. No hay nada que se acumule, así que no hay nada que se desvíe:
 *  a la hora que sea, el número es el que saldría de restar.
 */
function useLiveSeconds(today, running) {
  const now = useSecondTick()
  const segments = today?.segments ?? []

  const closed = segments
    .filter((segment) => segment.out && segment.counts_as_work !== false)
    .reduce((total, segment) => total + segment.seconds, 0)

  const open = segments.find((segment) => !segment.out && segment.counts_as_work !== false)
  if (!running || !open || !now) return today?.worked_seconds ?? 0

  const since = Date.parse(open.in)
  if (Number.isNaN(since)) return today?.worked_seconds ?? 0

  // Con la hora del servidor, no la del navegador: si el dispositivo va cinco
  // minutos adelantado, el contador diría cinco minutos de más.
  const running_seconds = Math.floor((serverAt(now).getTime() - since) / 1000)
  return closed + Math.max(0, running_seconds)
}

/** El reloj de pared: la hora del servidor, avanzando.
 *
 *  Está aquí y no en un rincón porque es la hora que se va a registrar si la
 *  persona pulsa. Verla moverse es lo que hace que la pantalla parezca viva y,
 *  sobre todo, que la hora del registro no parezca cosa del móvil.
 */
function WallClock({ zone, sx }) {
  const now = useSecondTick()
  if (!now || !serverClockReady()) return null

  return (
    <Typography
      variant="h6"
      color="text.secondary"
      sx={{ fontVariantNumeric: 'tabular-nums', fontWeight: 400, ...sx }}
      aria-live="off"
    >
      {serverAt(now).toLocaleTimeString(localeDeFechas(), {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        timeZone: zone,
      })}
    </Typography>
  )
}

const STATES = {
  WORKING: { label: 'Trabajando', color: 'success' },
  //: El servidor lo devuelve desde que existe `PunchInterval.BREAK`, y aquí no
  //: estaba: `STATES[estado]` caía al respaldo y la pantalla decía «Sin
  //: empezar» a quien tenía la jornada abierta y una pausa en marcha. No se
  //: notaba porque nada de la web podía abrir una pausa; la puerta de
  //: integración sí.
  ON_BREAK: { label: 'En pausa', color: 'warning' },
  OFF: { label: 'Jornada cerrada', color: 'default' },
  NOT_STARTED: { label: 'Sin empezar', color: 'default' },
}

/** Qué es cada tramo del día, para el desglose.
 *
 *  Sin esto una pausa se lee igual que un rato trabajado, que es justo lo que el
 *  art. 3.d viene a distinguir. */
const TRAMOS = {
  BREAK: { etiqueta: 'Pausa', color: 'warning' },
  STANDBY: { etiqueta: 'Presencia', color: 'info' },
  DISCONNECTION: { etiqueta: 'Fuera de horario', color: 'info' },
}

const MODOS = [
  { valor: 'ONSITE', etiqueta: 'Presencial' },
  { valor: 'REMOTE', etiqueta: 'A distancia' },
]

/** El modo elegido hoy, si se eligió.
 *
 *  Se recuerda por día y no para siempre: el art. 3.e habla del día «o parte de
 *  él», y quien ayer trabajó en casa hoy puede estar en la obra. Y **no hay
 *  valor por defecto**: vacío significa «no consta», y suponer «presencial»
 *  llenaría el registro de un dato que nadie ha afirmado ---peor que el hueco,
 *  porque el hueco se ve---.
 */
function modoDeHoy(dia) {
  try {
    const guardado = JSON.parse(localStorage.getItem('ott.work-mode') ?? 'null')
    return guardado?.dia === dia ? guardado.modo : ''
  } catch {
    return ''
  }
}

function recuerdaElModo(dia, modo) {
  try {
    localStorage.setItem('ott.work-mode', JSON.stringify({ dia, modo }))
  } catch {
    // Una pestaña privada o el almacenamiento lleno. El fichaje va igual: esto
    // solo ahorra volver a decirlo en el siguiente del día.
  }
}

export default function Clock() {
  const { session } = useAuth()
  const queryClient = useQueryClient()
  const [error, setError] = useState(null)

  const { data: today, isLoading } = useQuery({
    queryKey: ['today'],
    queryFn: getToday,
    refetchInterval: 60000,
  })

  // Lo previsto frente a lo hecho. Nunca se mezcla con el registro: el turno
  // dice cuando se puede trabajar, el fichaje lo que se trabajo.
  const { data: expected } = useQuery({
    queryKey: ['my-shift-today'],
    queryFn: getMyShiftToday,
  })

  //: El día en la zona de la persona, que es la que la pantalla enseña. Sirve
  //: para que el modo de trabajo se olvide al cambiar de día.
  const hoy = new Date().toISOString().slice(0, 10)
  const [modo, setModo] = useState(() => modoDeHoy(hoy))

  const punch = useMutation({
    mutationFn: (que = {}) =>
      clock(`web-${navigator.userAgentData?.platform ?? navigator.platform ?? 'unknown'}`, {
        interval: que.interval,
        // Solo en la entrada de la jornada: es lo que abre el tramo, y todo lo
        // descriptivo viaja en el evento que abre. Mandarlo al salir lo pondría
        // en un fichaje que no describe nada.
        workMode: que.interval || working ? undefined : modo,
      }),
    onSuccess: (registrado) => {
      setError(null)

      // El servidor ya manda el estado del día dentro de la respuesta, así que
      // se usa en vez de volver a preguntarlo. Es la pantalla que más se usa y
      // el peor momento para un viaje de más: la persona está delante del botón
      // esperando a ver si el fichaje ha entrado, muchas veces con la cobertura
      // de una obra.
      //
      // Se conserva lo que la consulta de `today` añade por su cuenta ---quién
      // y en qué zona--- porque eso no viene en la respuesta del fichaje.
      if (registrado?.day_status) {
        queryClient.setQueryData(['today'], (antes) => ({ ...antes, ...registrado.day_status }))
      } else {
        queryClient.invalidateQueries({ queryKey: ['today'] })
      }

      // Estas sí se vuelven a pedir: son de otras pantallas y el fichaje las
      // cambia, pero nadie las está mirando en este instante.
      queryClient.invalidateQueries({ queryKey: ['overview'] })
      queryClient.invalidateQueries({ queryKey: ['punches'] })
      queryClient.invalidateQueries({ queryKey: ['my-shift-today'] })
    },
    onError: (fallo) => {
      setError(fallo)
      // Con el plazo agotado no se sabe qué pasó, así que se pregunta. Si el
      // servidor sí lo registró, el panel de abajo lo enseña en un segundo y la
      // pregunta se contesta sola --- sin que nadie tenga que volver a pulsar.
      if (fallo?.code === 'timeout') {
        queryClient.invalidateQueries({ queryKey: ['today'] })
      }
    },
  })

  const working = today?.state === 'WORKING'
  const enPausa = today?.state === 'ON_BREAK'
  const seconds = useLiveSeconds(today, working)
  const state = STATES[today?.state] ?? STATES.NOT_STARTED

  return (
    <Box sx={{ maxWidth: 560, mx: 'auto' }}>
      <Typography variant="h1" sx={{ fontSize: '1.5rem', mb: 0.5 }}>
        Hola, {session?.user?.first_name || session?.user?.full_name}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        {new Date().toLocaleDateString(localeDeFechas(), {
          weekday: 'long',
          day: 'numeric',
          month: 'long',
        })}
      </Typography>

      {expected?.has_shift && (
        <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
          Hoy tienes turno de <strong>{hhmm(expected.expected_minutes * 60)}</strong>.
          {expected.difference_minutes < 0
            ? ` Llevas ${hhmm(Math.abs(expected.difference_minutes) * 60)} menos.`
            : expected.difference_minutes > 0
              ? ` Llevas ${hhmm(expected.difference_minutes * 60)} de más.`
              : ' Vas al día.'}
        </Alert>
      )}

      <Paper variant="outlined" sx={{ p: { xs: 3, sm: 4 }, textAlign: 'center' }}>
        {isLoading ? (
          <CircularProgress />
        ) : (
          <>
            <Chip label={state.label} color={state.color} sx={{ mb: 1.5 }} />

            {/* La hora, y del servidor. Es la que se va a guardar si pulsa, así
                que enseñar la del dispositivo —que puede ir cinco minutos
                adelantado— sembraría justo la duda que el diseño quiere
                cerrar. */}
            <WallClock zone={today?.time_zone} sx={{ mb: 2.5 }} />

            <Typography
              sx={{
                fontSize: { xs: '3.2rem', sm: '3.8rem' },
                fontWeight: 300,
                fontVariantNumeric: 'tabular-nums',
                lineHeight: 1,
                mb: 0.5,
              }}
            >
              {hhmmss(seconds)}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
              trabajadas hoy
            </Typography>

            {error && (
              <Alert
                severity="warning"
                variant="outlined"
                sx={{ mb: 3, textAlign: 'left' }}
                onClose={() => setError(null)}
              >
                {error.message}
                {/* Lo que de verdad hace falta saber, y solo aquí, donde se
                    escribe en el registro: **no ha quedado nada**. Sin esta
                    frase, quien está en un sótano ve un aviso, se encoge de
                    hombros y se va convencido de haber fichado --- que es cómo se
                    pierde un fichaje sin que nadie se entere.
                    El service worker no guarda cola a propósito: la hora de un
                    fichaje no se decide en el navegador. */}
                {error.code === 'network_error' && (
                  <Typography variant="body2" sx={{ mt: 0.5, fontWeight: 600 }}>
                    No se ha registrado nada. Vuelve a pulsar cuando tengas cobertura.
                  </Typography>
                )}
                {/* Y cuando la petición sí salió, lo honesto es no afirmarlo.
                    El plazo se agota a los diez segundos y el servidor ha
                    podido registrarla: decir aquí «no ha quedado nada» hacía
                    fichar otra vez, y ese segundo toque ya no lo frena la
                    guarda de cinco segundos --- así que entraba una salida
                    encima de la entrada. */}
                {error.code === 'timeout' && (
                  <Typography variant="body2" sx={{ mt: 0.5, fontWeight: 600 }}>
                    Puede que sí haya quedado registrado. Mira abajo antes de volver a pulsar: si
                    aparece, está hecho.
                  </Typography>
                )}
              </Alert>
            )}

            {/* El modo de trabajo, y solo antes de entrar: es el fichaje de
                entrada el que abre el tramo y lo describe. Sin preselección a
                propósito ---ver `modoDeHoy`---, así que quien no lo toca ficha
                exactamente como antes y en el registro consta que no se dijo. */}
            {!working && !enPausa && (
              <Stack sx={{ alignItems: 'center', mb: 3 }} spacing={1}>
                <Stack direction="row" spacing={1}>
                  {MODOS.map(({ valor, etiqueta }) => (
                    <Chip
                      key={valor}
                      label={etiqueta}
                      color={modo === valor ? 'primary' : 'default'}
                      variant={modo === valor ? 'filled' : 'outlined'}
                      onClick={() => {
                        const elegido = modo === valor ? '' : valor
                        setModo(elegido)
                        recuerdaElModo(hoy, elegido)
                      }}
                    />
                  ))}
                </Stack>
                <Typography variant="caption" color="text.secondary">
                  Desde dónde trabajas hoy (art. 3.e). Puedes dejarlo sin decir.
                </Typography>
              </Stack>
            )}

            {/* Un toque. El servidor decide si es entrada o salida.
                En pausa solo se ofrece volver: el art. 3.d pide el final de la
                pausa, y dejar fichar la salida desde aquí cerraría la jornada
                con la pausa abierta ---un día que dice que alguien se fue a
                comer y no volvió nunca---. */}
            <Button
              variant="contained"
              color={enPausa ? 'warning' : working ? 'secondary' : 'primary'}
              size="large"
              startIcon={enPausa ? <LoginIcon /> : working ? <LogoutIcon /> : <LoginIcon />}
              onClick={() => punch.mutate(enPausa ? { interval: 'BREAK' } : {})}
              disabled={punch.isPending}
              sx={{ py: 2, px: 6, fontSize: '1.15rem', borderRadius: 2 }}
            >
              {punch.isPending
                ? 'Registrando…'
                : enPausa
                  ? 'Volver de la pausa'
                  : working
                    ? 'Fichar salida'
                    : 'Fichar entrada'}
            </Button>

            {/* La pausa que no es tiempo de trabajo (art. 3.d). Secundaria y
                debajo: es lo que se hace una vez al día, no lo que se viene a
                hacer aquí. Si el convenio dice que el descanso cuenta como
                trabajo, el servidor no lo descuenta ---la regla es de la
                empresa, no nuestra--- y esto sigue sirviendo para registrarlo,
                que es lo que pide el artículo. */}
            {working && (
              <Box sx={{ mt: 2 }}>
                <Button
                  variant="text"
                  startIcon={<PauseIcon />}
                  onClick={() => punch.mutate({ interval: 'BREAK' })}
                  disabled={punch.isPending}
                >
                  Empezar una pausa
                </Button>
              </Box>
            )}
          </>
        )}
      </Paper>

      {today?.segments?.length > 0 && (
        <Paper variant="outlined" sx={{ p: 3, mt: 2 }}>
          <Typography variant="h2" sx={{ fontSize: '1rem', mb: 2 }}>
            Hoy
          </Typography>
          <Stack spacing={1.5} divider={<Divider flexItem />}>
            {today.segments.map((segment) => (
              <Stack
                key={segment.in}
                direction="row"
                sx={{ justifyContent: 'space-between', alignItems: 'center' }}
              >
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                  <Typography sx={{ fontVariantNumeric: 'tabular-nums' }}>
                    {timeOf(segment.in, today.time_zone)}
                    {' → '}
                    {segment.out ? timeOf(segment.out, today.time_zone) : '…'}
                  </Typography>
                  {/* Qué es este tramo. Un rato de pausa se leía igual que un
                      rato trabajado, que es lo que el art. 3.d distingue. */}
                  {TRAMOS[segment.interval] && (
                    <Chip
                      size="small"
                      variant="outlined"
                      color={TRAMOS[segment.interval].color}
                      label={TRAMOS[segment.interval].etiqueta}
                    />
                  )}
                  {segment.work_mode === 'REMOTE' && (
                    <Chip size="small" variant="outlined" label="A distancia" />
                  )}
                </Stack>
                <Typography variant="body2" color="text.secondary">
                  {hhmm(segment.seconds)}
                </Typography>
              </Stack>
            ))}
          </Stack>
          {today.break_seconds > 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
              {hhmm(today.break_seconds)} de pausa. Si tu convenio dice que el descanso es tiempo de
              trabajo, ya está contado en las horas de arriba.
            </Typography>
          )}
          <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block' }}>
            Horas de {today.time_zone}. Las pone el servidor, no tu dispositivo.
          </Typography>
        </Paper>
      )}
    </Box>
  )
}
