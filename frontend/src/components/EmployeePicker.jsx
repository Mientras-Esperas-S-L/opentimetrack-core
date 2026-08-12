import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import Autocomplete from '@mui/material/Autocomplete'
import Chip from '@mui/material/Chip'
import TextField from '@mui/material/TextField'

import { getEmployees } from '../services/api.js'

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
 */
export default function EmployeePicker({
  value,
  onChange,
  multiple = false,
  label = 'Persona',
  everyoneLabel,
  helperText,
  required,
  size,
  sx,
}) {
  const [typed, setTyped] = useState('')

  // Two characters before asking. One matches most of the company and makes a
  // request per keystroke to learn nothing.
  const search = typed.trim().length >= 2 ? typed.trim() : undefined

  const { data, isFetching } = useQuery({
    queryKey: ['employees', 'picker', search],
    queryFn: () => getEmployees({ is_active: true, search, ordering: 'last_name' }),
    placeholderData: (previous) => previous,
  })

  const people = data?.rows ?? []
  const missing = Math.max((data?.count ?? 0) - people.length, 0)

  const nameOf = (person) =>
    `${person.first_name ?? ''} ${person.last_name ?? ''}`.trim() || person.email

  // `everyoneLabel` turns the field into a filter: no selection means the whole
  // company rather than nothing, and that has to be a visible option instead of
  // something people discover by clearing the box.
  const options = everyoneLabel ? [{ id: '', __everyone: true }, ...people] : people

  const selected = multiple
    ? people.filter((person) => (value ?? []).includes(person.id))
    : (options.find((person) => person.id === (value ?? '')) ?? null)

  return (
    <Autocomplete
      multiple={multiple}
      size={size}
      sx={sx}
      options={options}
      value={selected}
      loading={isFetching}
      filterOptions={(x) => x} // the server already filtered; filtering again
      // would hide people whose page is not loaded
      isOptionEqualToValue={(option, chosen) => option.id === chosen.id}
      getOptionLabel={(option) => (option.__everyone ? everyoneLabel : nameOf(option))}
      onInputChange={(_, next, reason) => reason === 'input' && setTyped(next)}
      // The chosen person comes back as a second argument, not just their id.
      // A caller that needs the name --- a dialog title, say --- would otherwise
      // have to look it up in a list it no longer holds.
      onChange={(_, next) =>
        onChange(multiple ? next.map((person) => person.id) : (next?.id ?? ''), next)
      }
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
          ? (chosen, getProps) =>
              chosen.map((person, index) => (
                <Chip
                  size="small"
                  label={nameOf(person)}
                  {...getProps({ index })}
                  key={person.id}
                />
              ))
          : undefined
      }
      noOptionsText={search ? 'Nadie coincide.' : 'Escribe para buscar.'}
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
