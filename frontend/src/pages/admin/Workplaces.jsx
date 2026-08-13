import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import Autocomplete from '@mui/material/Autocomplete'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import AddIcon from '@mui/icons-material/Add'
import PlaceIcon from '@mui/icons-material/Place'

import {
  createHoliday,
  createWorkplace,
  deleteHoliday,
  deleteWorkplace,
  getHolidays,
  getWorkingTimeRules,
  getWorkplaces,
  updateWorkplace,
} from '../../services/api.js'
import { dateOf } from '../../components/format.js'
import { ConfirmDialog, Empty, ErrorNote, Loading, PageHeader } from '../../components/common.jsx'
import { useAuth } from '../../hooks/useAuth.js'

/** Todas las zonas horarias que conoce el navegador.
 *
 *  `Intl.supportedValuesOf` viene de fábrica y trae la lista IANA al día, que
 *  es la misma contra la que valida el servidor. Mantener una copia aquí sería
 *  garantizar que las dos se separen: las zonas cambian ---países que dejan el
 *  horario de verano, territorios que se pasan de huso--- y una lista escrita a
 *  mano envejece sin avisar.
 */
const TODAS_LAS_ZONAS = Intl.supportedValuesOf?.('timeZone') ?? []

/** Where the work is done, as opposed to who it is done with.
 *
 *  Three things hang off the place rather than off the company, and the screen
 *  says so rather than asking for fields whose purpose is invisible: the record
 *  is inspected per workplace, two of the fourteen public holidays are decided
 *  by the town hall, and Spain has two time zones.
 */
function WorkplaceDialog({
  open,
  workplace,
  regions,
  zonasDelPais,
  companyZone,
  onClose,
  onSave,
  saving,
  error,
}) {
  // Las del país primero, y sin repetirlas abajo.
  const zonasHorarias = [
    ...Object.keys(zonasDelPais),
    ...TODAS_LAS_ZONAS.filter((zona) => !zonasDelPais[zona]),
  ]

  const empty = {
    name: '',
    address: '',
    municipality: '',
    municipality_code: '',
    region: '',
    time_zone: '',
  }
  const [form, setForm] = useState(empty)
  const [loaded, setLoaded] = useState(null)

  if (open && loaded !== (workplace?.id ?? 'new')) {
    setLoaded(workplace?.id ?? 'new')
    setForm(workplace ? { ...empty, ...workplace } : empty)
  }
  if (!open && loaded !== null) setLoaded(null)

  const set = (field) => (event) => setForm({ ...form, [field]: event.target.value })

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form
        onSubmit={(event) => {
          event.preventDefault()
          onSave(form)
        }}
      >
        <DialogTitle>{workplace ? 'Editar centro' : 'Nuevo centro de trabajo'}</DialogTitle>
        <DialogContent>
          <ErrorNote error={error} />
          <Stack sx={{ gap: 2, pt: 1 }}>
            <TextField
              autoFocus
              required
              fullWidth
              label="Nombre"
              placeholder="Oficina central, Nave de Getafe…"
              value={form.name}
              onChange={set('name')}
            />
            <TextField
              fullWidth
              label="Dirección"
              value={form.address}
              onChange={set('address')}
              helperText="Es donde una inspección pediría el registro de esta gente."
            />

            <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
              <TextField
                fullWidth
                label="Municipio"
                value={form.municipality}
                onChange={set('municipality')}
                helperText="Decide los dos festivos locales."
              />
              <TextField
                label="Código INE"
                value={form.municipality_code}
                onChange={set('municipality_code')}
                sx={{ minWidth: 150 }}
                helperText="Opcional"
              />
            </Stack>

            <TextField
              select
              fullWidth
              label="Comunidad autónoma"
              value={form.region}
              onChange={set('region')}
              helperText="Decide los festivos autonómicos. Sin ella solo se aplican los nacionales."
            >
              <MenuItem value="">Sin especificar</MenuItem>
              {Object.entries(regions).map(([code, name]) => (
                <MenuItem key={code} value={code}>
                  {name}
                </MenuItem>
              ))}
            </TextField>

            {/* Se elige de una lista, no se teclea. Una zona horaria es un
                identificador IANA exacto ---«Europe/Madrid»--- y escribirlo a
                mano solo puede salir mal: «Madrid», «Canarias» o «España» son
                todo lo que a nadie se le ocurre poner, y las tres las rechaza
                el servidor sin decir cuál era la buena.

                Delante van las del país, que vienen del marco legal; detrás,
                el resto de las que conoce el navegador, para una empresa
                española con una delegación en Lisboa. */}
            <Autocomplete
              options={zonasHorarias}
              groupBy={(zona) => (zonasDelPais[zona] ? 'En este país' : 'Las demás')}
              getOptionLabel={(zona) =>
                zonasDelPais[zona] ? `${zona} · ${zonasDelPais[zona]}` : zona
              }
              value={form.time_zone || null}
              onChange={(_, zona) => setForm({ ...form, time_zone: zona ?? '' })}
              renderInput={(params) => (
                <TextField
                  {...params}
                  fullWidth
                  label="Zona horaria"
                  placeholder={companyZone}
                  helperText={`Vacío usa la de la empresa (${companyZone}). Solo hace falta si el centro está en otra: en España, Canarias.`}
                />
              )}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} color="inherit">
            Cancelar
          </Button>
          <Button type="submit" variant="contained" disabled={saving || !form.name.trim()}>
            Guardar
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}

/** El calendario del año, y los dos días que nadie puede publicarnos.
 *
 *  Los doce nacionales y autonómicos entran con `import_holidays` desde un
 *  fichero transcrito del BOE. Los dos locales los propone cada ayuntamiento y
 *  los aprueba su comunidad, así que acaban en medio centenar de boletines y
 *  ocho mil municipios: no hay registro que leer. Se teclean, y la pantalla lo
 *  dice en vez de disimularlo.
 */
function Holidays({ workplaces }) {
  const queryClient = useQueryClient()
  const { session } = useAuth()
  const isAdmin = session?.user?.role === 'ADMIN'

  const thisYear = new Date().getFullYear()
  const [year, setYear] = useState(thisYear)
  const [adding, setAdding] = useState({ day: '', name: '', workplace: '' })
  const [error, setError] = useState(null)

  const { data: holidays = [] } = useQuery({
    queryKey: ['holidays', year],
    queryFn: () => getHolidays({ year }),
  })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['holidays'] })

  const add = useMutation({
    mutationFn: createHoliday,
    onSuccess: () => {
      setAdding({ day: '', name: '', workplace: '' })
      setError(null)
      refresh()
    },
    onError: setError,
  })
  const drop = useMutation({ mutationFn: deleteHoliday, onSuccess: refresh, onError: setError })

  const imported = holidays.filter((h) => h.scope === 'NATIONAL' || h.scope === 'REGIONAL')
  const typed = holidays.filter((h) => h.scope === 'LOCAL' || h.scope === 'COMPANY')

  return (
    <Box sx={{ mt: 4 }}>
      <Stack direction="row" sx={{ gap: 2, alignItems: 'baseline', mb: 1 }}>
        <Typography variant="h6">Festivos</Typography>
        <TextField
          select
          size="small"
          value={year}
          onChange={(event) => setYear(Number(event.target.value))}
          sx={{ minWidth: 110 }}
        >
          {[thisYear - 1, thisYear, thisYear + 1].map((option) => (
            <MenuItem key={option} value={option}>
              {option}
            </MenuItem>
          ))}
        </TextField>
        <Typography variant="body2" color="text.secondary">
          {holidays.length} de los 14 del art. 37.2
        </Typography>
      </Stack>

      <ErrorNote error={error} onClose={() => setError(null)} />

      {imported.length === 0 && (
        <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
          No hay festivos nacionales ni autonómicos de {year}. Los trae{' '}
          <code>python manage.py import_holidays --year {year}</code> desde el calendario transcrito
          del BOE.
        </Alert>
      )}

      <Stack sx={{ gap: 0.5 }}>
        {holidays.map((day) => (
          <Stack
            key={day.id}
            direction="row"
            sx={{
              gap: 1.5,
              alignItems: 'center',
              py: 0.5,
              borderBottom: 1,
              borderColor: 'divider',
            }}
          >
            <Typography variant="body2" sx={{ minWidth: 110, fontVariantNumeric: 'tabular-nums' }}>
              {dateOf(day.day, { weekday: 'short' })}
            </Typography>
            <Typography variant="body2" sx={{ flexGrow: 1 }}>
              {day.name}
            </Typography>
            <Chip size="small" variant="outlined" label={day.workplace_name ?? day.scope_display} />
            {isAdmin && (day.scope === 'LOCAL' || day.scope === 'COMPANY') && (
              <Button size="small" color="inherit" onClick={() => drop.mutate(day.id)}>
                Quitar
              </Button>
            )}
          </Stack>
        ))}
      </Stack>

      {isAdmin && (
        <Box
          component="form"
          onSubmit={(event) => {
            event.preventDefault()
            add.mutate({ ...adding, workplace: adding.workplace || null })
          }}
          sx={{ mt: 2 }}
        >
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            sx={{ gap: 1.5, alignItems: 'flex-start' }}
          >
            <TextField
              required
              size="small"
              type="date"
              label="Día"
              value={adding.day}
              onChange={(event) => setAdding({ ...adding, day: event.target.value })}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <TextField
              required
              size="small"
              label="Nombre"
              placeholder="Feria de Jerez"
              value={adding.name}
              onChange={(event) => setAdding({ ...adding, name: event.target.value })}
              sx={{ flexGrow: 1 }}
            />
            <TextField
              select
              size="small"
              label="Dónde"
              value={adding.workplace}
              onChange={(event) => setAdding({ ...adding, workplace: event.target.value })}
              sx={{ minWidth: 190 }}
            >
              <MenuItem value="">Toda la empresa</MenuItem>
              {workplaces.map((place) => (
                <MenuItem key={place.id} value={place.id}>
                  {place.name}
                </MenuItem>
              ))}
            </TextField>
            <Button type="submit" variant="outlined" disabled={add.isPending}>
              Añadir
            </Button>
          </Stack>
          <Typography variant="caption" color="text.secondary">
            Los dos festivos locales de cada municipio se meten aquí: los aprueba cada ayuntamiento
            y no hay ningún registro nacional del que traerlos.
            {typed.length > 0 && ` Hay ${typed.length} puestos a mano en ${year}.`}
          </Typography>
        </Box>
      )}
    </Box>
  )
}

export default function Workplaces() {
  const queryClient = useQueryClient()
  const { session } = useAuth()
  const isAdmin = session?.user?.role === 'ADMIN'

  const [editing, setEditing] = useState(undefined)
  const [error, setError] = useState(null)
  const [confirming, setConfirming] = useState(null)

  const { data: workplaces = [], isLoading } = useQuery({
    queryKey: ['workplaces'],
    queryFn: () => getWorkplaces(),
  })
  // The regions come from the applicable legal framework, not from a list in
  // the frontend: a company in another country gets its own subdivisions, and
  // one whose country has none simply never sees the field offer anything.
  const { data: rules } = useQuery({
    queryKey: ['working-time-rules'],
    queryFn: getWorkingTimeRules,
  })
  const regions = rules?.regions ?? {}
  // Las del país, del marco legal. En España son dos; en casi todo lo demás,
  // una --- y donde no haya ninguna declarada, la lista completa del navegador
  // sigue estando ahí.
  const zonasDelPais = rules?.time_zones ?? {}
  const companyZone = session?.tenant?.time_zone ?? 'Europe/Madrid'

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['workplaces'] })

  const save = useMutation({
    mutationFn: (form) => (editing ? updateWorkplace(editing.id, form) : createWorkplace(form)),
    onSuccess: () => {
      setEditing(undefined)
      setError(null)
      refresh()
    },
    onError: setError,
  })

  const remove = useMutation({
    mutationFn: deleteWorkplace,
    onSuccess: () => {
      setConfirming(null)
      refresh()
    },
    onError: (failure) => {
      setConfirming(null)
      setError(failure)
    },
  })

  return (
    <>
      <PageHeader
        title="Centros de trabajo"
        subtitle="Dónde se trabaja. Decide los festivos locales, la zona horaria de la jornada y dónde se pide el registro en una inspección."
        action={
          isAdmin && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setEditing(null)}>
              Nuevo centro
            </Button>
          )
        }
      />

      <ErrorNote error={error} onClose={() => setError(null)} />

      {isLoading ? (
        <Loading rows={3} />
      ) : workplaces.length === 0 ? (
        <Empty>
          Todavía no hay centros. Sin ellos no se pueden aplicar los festivos locales, y toda la
          plantilla se mide en la zona horaria de la empresa.
        </Empty>
      ) : (
        <Stack component="ul" sx={{ gap: 1.5, listStyle: 'none', m: 0, p: 0 }}>
          {workplaces.map((place) => (
            <Paper component="li" key={place.id} variant="outlined" sx={{ p: 2 }}>
              <Stack
                direction={{ xs: 'column', sm: 'row' }}
                sx={{ gap: 1.5, alignItems: { sm: 'center' } }}
              >
                <PlaceIcon color="disabled" />
                <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                  <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                    <Typography sx={{ fontWeight: 600 }}>{place.name}</Typography>
                    <Chip
                      size="small"
                      variant="outlined"
                      label={
                        place.people_count === 1 ? '1 persona' : `${place.people_count} personas`
                      }
                    />
                    {/* Solo cuando difiere de la de la empresa: repetirla en
                        cada fila sería ruido, y callarla donde cambia sería
                        esconder justo el dato por el que existe el campo. */}
                    {place.time_zone && (
                      <Chip
                        size="small"
                        color="primary"
                        variant="outlined"
                        label={place.time_zone}
                      />
                    )}
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    {[place.address, place.municipality, place.region_name]
                      .filter(Boolean)
                      .join(' · ') || 'Sin dirección'}
                  </Typography>
                  {!place.region && (
                    <Typography variant="caption" color="warning.main">
                      Sin comunidad autónoma: solo se le aplicarán los festivos nacionales.
                    </Typography>
                  )}
                </Box>

                {isAdmin && (
                  <Stack direction="row" sx={{ gap: 0.5, flexShrink: 0 }}>
                    <Button size="small" onClick={() => setEditing(place)}>
                      Editar
                    </Button>
                    {place.people_count === 0 && (
                      <Button
                        size="small"
                        color="inherit"
                        onClick={() =>
                          setConfirming({
                            title: 'Eliminar el centro',
                            body: place.name,
                            detail: 'No trabaja nadie ahí, así que no se pierde nada.',
                            verb: 'Eliminar',
                            run: () => remove.mutate(place.id),
                          })
                        }
                      >
                        Eliminar
                      </Button>
                    )}
                  </Stack>
                )}
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}

      {workplaces.some((place) => place.people_count === 0) && (
        <Alert severity="info" variant="outlined" sx={{ mt: 2 }}>
          Un centro con gente dentro no se puede eliminar: se quedarían sin festivos locales y
          pasarían a medirse en la zona de la empresa. Muévelos primero.
        </Alert>
      )}

      <ConfirmDialog
        request={confirming}
        busy={remove.isPending}
        onClose={() => setConfirming(null)}
      />

      <Holidays workplaces={workplaces} />

      <WorkplaceDialog
        open={editing !== undefined}
        workplace={editing}
        regions={regions}
        zonasDelPais={zonasDelPais}
        companyZone={companyZone}
        saving={save.isPending}
        error={error}
        onClose={() => {
          setEditing(undefined)
          setError(null)
        }}
        onSave={save.mutate}
      />
    </>
  )
}
