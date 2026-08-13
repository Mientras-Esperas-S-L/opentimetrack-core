/** Acotar una lista antes de trabajar con ella.
 *
 *  Va de la mano de la selección: «aprobar todo» sobre veinte cosas mezcladas
 *  da miedo y con razón; sobre las cuatro de una persona, o las de un tipo, es
 *  exactamente lo que alguien quiere hacer. Filtrar es lo que convierte la
 *  acción masiva en algo que se usa sin apretar los dientes.
 *
 *  Todo cliente aquí: son colas de decenas, no de miles, y llegan enteras. En
 *  cuanto una lista se pagine, su filtro tiene que ir al servidor --- filtrar
 *  la página en el navegador enseñaría «3 de 3» de una lista de 200.
 */

import Box from '@mui/material/Box'
import IconButton from '@mui/material/IconButton'
import InputAdornment from '@mui/material/InputAdornment'
import MenuItem from '@mui/material/MenuItem'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import ClearIcon from '@mui/icons-material/Clear'
import SearchIcon from '@mui/icons-material/Search'

/** La fila de controles. Se envuelve en móvil en vez de encogerse hasta ser
 *  ilegible. */
export function FilterBar({ children, right }) {
  return (
    <Stack
      direction="row"
      sx={{ gap: 1.5, alignItems: 'center', flexWrap: 'wrap', mb: 2 }}
      role="search"
    >
      {children}
      {right && <Box sx={{ ml: 'auto' }}>{right}</Box>}
    </Stack>
  )
}

export function SearchField({ value, onChange, placeholder = 'Buscar', width = 240 }) {
  return (
    <TextField
      size="small"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      sx={{ width }}
      slotProps={{
        input: {
          startAdornment: (
            <InputAdornment position="start">
              <SearchIcon fontSize="small" />
            </InputAdornment>
          ),
          // Vaciar tiene que costar un clic. Sin esto la gente borra a mano y
          // deja un espacio dentro, y la lista se queda vacía sin explicación.
          endAdornment: value ? (
            <InputAdornment position="end">
              <IconButton size="small" onClick={() => onChange('')} aria-label="Vaciar la búsqueda">
                <ClearIcon fontSize="small" />
              </IconButton>
            </InputAdornment>
          ) : null,
        },
      }}
    />
  )
}

/** Un desplegable con «todas» delante. `options` es `[{value, label}]`. */
export function PickFilter({ label, value, onChange, options, all = 'Todas', width = 190 }) {
  return (
    <TextField
      select
      size="small"
      label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      sx={{ width }}
    >
      <MenuItem value="">{all}</MenuItem>
      {options.map((option) => (
        <MenuItem key={option.value} value={option.value}>
          {option.label}
        </MenuItem>
      ))}
    </TextField>
  )
}
