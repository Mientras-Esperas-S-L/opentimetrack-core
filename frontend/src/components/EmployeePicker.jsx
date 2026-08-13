import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import Autocomplete from '@mui/material/Autocomplete'
import Chip from '@mui/material/Chip'
import TextField from '@mui/material/TextField'

import { getEmployees } from '../services/api.js'
import { useDebounced } from '../hooks/useDebounced.js'

/** Picking a person, by typing rather than by scrolling.
 *
 *  This replaced a plain `Select` listing everybody, which had two problems and
 *  the smaller one was the scrolling. The list came from a paginated endpoint,
 *  so it held **the first fifty people** and nothing more: in a company of two
 *  hundred, three quarters of the workforce simply could not be chosen, and the
 *  dropdown gave no sign of it.
 *
 *  The search runs on the server, over name, surname, address and staff number.
 *  What is loaded before anybody types is one page --- enough to open the field
 *  and see familiar faces --- and typing goes and asks.
 *
 *  ## El valor son identificadores, no objetos de la lista
 *
 *  Y es la parte que hay que respetar al tocar esto, porque de lo contrario
 *  **el campo deja de admitir texto**. MUI reinicia lo tecleado cada vez que
 *  cambia la *identidad* de `value`. Cuando el valor se calculaba filtrando la
 *  página cargada, salía un array nuevo en cada render: cada tecla provocaba un
 *  render que borraba esa misma tecla. El síntoma era inconfundible ---
 *  escribiendo rápido solo sobrevivía la última letra --- y con `multiple`,
 *  que es el caso de «quién lleva el departamento», el campo era inservible.
 *
 *  Pasando identificadores, el valor es una cadena o el array que ya tiene el
 *  formulario, y ninguno de los dos cambia de identidad por teclear.
 *
 *  De paso arregla otro fallo que venía con el anterior: quien ya estaba
 *  elegido se buscaba en la página de resultados de ese momento, así que al
 *  escribir la respuesta dejaba de traerlo y su ficha desaparecía de la
 *  pantalla. Ahora el nombre se resuelve contra lo cargado, contra lo que ya se
 *  eligió en esta sesión, y contra lo que el llamante sepa (`knownNames`).
 */
const NOBODY = []

export default function EmployeePicker({
  value,
  onChange,
  multiple = false,
  label = 'Persona',
  everyoneLabel,
  /** `{ id: nombre }` que el llamante ya conoce, para las fichas de quien no
   *  esté en la página cargada. Sin esto, editar un departamento cuyos
   *  responsables están en la página dos enseñaría fichas sin nombre. */
  knownNames,
  /** Restringe a quien puede gestionar. Lo usa «quién lleva el departamento»:
   *  el servidor solo acepta perfiles de responsable, así que ofrecer al resto
   *  era ofrecer algo que luego se niega --- y se negaba con un 400 después de
   *  haberlo elegido. */
  onlyManagers = false,
  helperText,
  required,
  size,
  sx,
}) {
  const [typed, setTyped] = useState('')
  // Nombres de lo que se va eligiendo aquí, para que la ficha sobreviva a que
  // la búsqueda cambie la lista bajo ella.
  const [picked, setPicked] = useState({})

  // Two characters before asking, and only once typing pauses. One character
  // matches most of the company, and a request per keystroke asks eight times
  // to learn what the eighth answer says.
  const settled = useDebounced(typed)
  const search = settled.trim().length >= 2 ? settled.trim() : undefined

  const { data, isFetching } = useQuery({
    queryKey: ['employees', 'picker', search, onlyManagers],
    queryFn: () =>
      getEmployees({
        is_active: true,
        search,
        ordering: 'last_name',
        ...(onlyManagers ? { can_manage: true } : {}),
      }),
    placeholderData: (previous) => previous,
  })

  // Memorizado aunque parezca trivial: `?? []` crea un array nuevo cada vez que
  // la consulta aún no ha respondido, y de ahí cuelgan dos memos más.
  const people = useMemo(() => data?.rows ?? [], [data])
  const missing = Math.max((data?.count ?? 0) - people.length, 0)

  const nameOf = (person) =>
    `${person.first_name ?? ''} ${person.last_name ?? ''}`.trim() || person.email

  const byId = useMemo(() => new Map(people.map((person) => [person.id, person])), [people])

  const labelFor = (id) => {
    if (id === '') return everyoneLabel
    const person = byId.get(id)
    return person ? nameOf(person) : (picked[id] ?? knownNames?.[id] ?? '…')
  }

  // `everyoneLabel` turns the field into a filter: no selection means the whole
  // company rather than nothing, and that has to be a visible option instead of
  // something people discover by clearing the box.
  const options = useMemo(
    () => (everyoneLabel ? [{ id: '', __everyone: true }, ...people] : people),
    [everyoneLabel, people],
  )

  const chosen = multiple ? (value ?? NOBODY) : (value ?? null)

  const remember = (list) =>
    setPicked((before) => ({
      ...before,
      ...Object.fromEntries(list.filter(Boolean).map((person) => [person.id, nameOf(person)])),
    }))

  return (
    <Autocomplete
      multiple={multiple}
      size={size}
      sx={sx}
      options={options}
      value={chosen}
      loading={isFetching}
      filterOptions={(x) => x} // the server already filtered; filtering again
      // would hide people whose page is not loaded
      // Las opciones son objetos y el valor son identificadores, así que la
      // comparación tiene que aceptar las dos formas.
      isOptionEqualToValue={(option, picked_) => option.id === (picked_?.id ?? picked_)}
      getOptionLabel={(option) =>
        typeof option === 'string'
          ? labelFor(option)
          : option.__everyone
            ? everyoneLabel
            : nameOf(option)
      }
      onInputChange={(_, next, reason) => reason === 'input' && setTyped(next)}
      // The chosen person comes back as a second argument, not just their id.
      // A caller that needs the name --- a dialog title, say --- would otherwise
      // have to look it up in a list it no longer holds.
      onChange={(_, next) => {
        const list = multiple ? next : next ? [next] : []
        const objects = list.filter((item) => typeof item !== 'string')
        remember(objects)
        onChange(
          multiple ? list.map((item) => item?.id ?? item) : (next?.id ?? next ?? ''),
          multiple ? objects : (objects[0] ?? null),
        )
      }}
      renderOption={(props, option) => {
        const { key, ...rest } = props
        return (
          <li key={key} {...rest}>
            {option.__everyone ? everyoneLabel : nameOf(option)}
          </li>
        )
      }}
      renderValue={
        multiple
          ? (ids, getProps) =>
              ids.map((id, index) => (
                <Chip
                  size="small"
                  label={labelFor(id?.id ?? id)}
                  {...getProps({ index })}
                  key={id?.id ?? id}
                />
              ))
          : undefined
      }
      noOptionsText={
        search
          ? 'Nadie coincide.'
          : onlyManagers
            ? 'Nadie tiene perfil de responsable todavía.'
            : 'Escribe para buscar.'
      }
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          required={required}
          helperText={
            // Says out loud that the list is partial. Silence here is what made
            // the old dropdown misleading rather than merely awkward.
            missing > 0 && !search
              ? `Se muestran ${people.length} de ${data.count}. Escribe para buscar entre el resto.`
              : helperText
          }
        />
      )}
    />
  )
}
