/** Si quiere que le recuerden fichar, y por dónde.
 *
 *  Son dos cosas distintas y la pantalla las separa: el interruptor es de la
 *  persona y viaja con ella a cualquier navegador; el aviso en el navegador es
 *  de *este* dispositivo y no puede viajar, porque el permiso lo da el
 *  navegador y no la cuenta.
 *
 *  El aviso del navegador solo aparece cuando hay algo que ofrecer: si el
 *  despliegue no tiene claves configuradas, o el navegador no sabe hacerlo, no
 *  se enseña un interruptor que no va a servir para nada.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import FormControlLabel from '@mui/material/FormControlLabel'
import Stack from '@mui/material/Stack'
import Switch from '@mui/material/Switch'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'

import { updateMe } from '../services/api.js'
import { disablePush, enablePush, pushState, pushSupported } from '../services/push.js'
import { useAuth } from '../hooks/useAuth.js'

export default function RemindersControl() {
  const { session, setSession } = useAuth()
  const queryClient = useQueryClient()
  const wants = session?.user?.wants_punch_reminders !== false

  const remind = useMutation({
    mutationFn: (on) => updateMe({ wants_punch_reminders: on }),
    onSuccess: (user) => {
      if (session) setSession({ ...session, user: { ...session.user, ...user } })
    },
  })

  // El estado vive en el navegador, no aquí: es una lectura asíncrona de algo
  // externo, que es exactamente lo que una query resuelve. 'unknown' mientras
  // contesta, porque pintar «apagado» de entrada hace parpadear el interruptor
  // en cada carga.
  const { data: push = 'unknown' } = useQuery({
    queryKey: ['push', 'state'],
    queryFn: () => (pushSupported() ? pushState() : 'unsupported'),
    staleTime: Infinity,
  })

  const togglePush = useMutation({
    mutationFn: (on) => (on ? enablePush() : disablePush()),
    onSuccess: (state) => queryClient.setQueryData(['push', 'state'], state),
    // El navegador puede negarse por mil motivos —sin HTTPS, en incógnito, con
    // el service worker bloqueado— y ninguno merece un error rojo: se relee el
    // estado real, el interruptor vuelve a su sitio y los recordatorios siguen
    // por correo.
    onError: () => queryClient.invalidateQueries({ queryKey: ['push', 'state'] }),
  })

  const showPush = wants && !['unknown', 'unsupported', 'unconfigured'].includes(push)

  return (
    <Stack direction="row" sx={{ gap: 1.5, alignItems: 'center', flexWrap: 'wrap' }}>
      <Tooltip title="Aviso si empieza tu turno y no has fichado, o si dejas la jornada abierta. Empuja al fichaje real, nunca lo hace por ti.">
        <FormControlLabel
          sx={{ mr: 0 }}
          control={
            <Switch
              size="small"
              checked={wants}
              disabled={remind.isPending}
              onChange={(event) => remind.mutate(event.target.checked)}
            />
          }
          label={<Typography variant="body2">Recordatorios</Typography>}
        />
      </Tooltip>

      {showPush && (
        <Tooltip
          title={
            push === 'denied'
              ? 'Este navegador tiene los avisos bloqueados. Se cambia en sus ajustes de sitio.'
              : 'Además del correo, aviso en este dispositivo. Solo en este: el permiso lo da el navegador.'
          }
        >
          <FormControlLabel
            sx={{ mr: 0 }}
            control={
              <Switch
                size="small"
                checked={push === 'on'}
                disabled={togglePush.isPending || push === 'denied'}
                onChange={(event) => togglePush.mutate(event.target.checked)}
              />
            }
            label={
              <Typography variant="body2" color={push === 'denied' ? 'text.disabled' : undefined}>
                {push === 'denied' ? 'Avisos bloqueados' : 'En este dispositivo'}
              </Typography>
            }
          />
        </Tooltip>
      )}
    </Stack>
  )
}
