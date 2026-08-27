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
import { useTranslation } from 'react-i18next'
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

export function SearchField({ value, onChange, placeholder, width = 240 }) {
  const { t } = useTranslation()
  return (
    <TextField
      size="small"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder ?? t('Buscar')}
      // Un tope, no una medida. Con `width` a secas el campo mide eso pase lo
      // que pase, y en un móvil de 390 px un buscador de 380 más su borde se
      // sale de la pantalla --- lo estrenó Personas al pasar a este componente.
      sx={{ width: '100%', maxWidth: width }}
      slotProps={{
        // En el `input`, no en el `TextField`. Puesto arriba, MUI lo reenvía al
        // div de fuera y el campo se sigue oyendo como «cuadro de texto» a
        // secas: la sonda lo seguía marcando después de «arreglarlo».
        //
        // Y hace falta: el marcador de posición no es una etiqueta ---desaparece
        // al escribir, y hay lectores que no lo anuncian--- así que el buscador
        // no tenía nombre en cinco pantallas.
        htmlInput: { 'aria-label': placeholder },
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
              <IconButton
                size="small"
                onClick={() => onChange('')}
                aria-label={t('Vaciar la búsqueda')}
              >
                <ClearIcon fontSize="small" />
              </IconButton>
            </InputAdornment>
          ) : null,
        },
      }}
    />
  )
}

/** Un desplegable con «todas» delante.
 *
 *  `options` es `[{value, label}]` y el rótulo llega **ya traducido**: aquí no
 *  se traduce nada. La mayoría son nombres que vienen de la base ---personas,
 *  departamentos, centros--- y pasarlos por `t()` haría que un centro llamado
 *  «Entrada» se leyera en catalán.
 */
export function PickFilter({ label, value, onChange, options, all, width = 190 }) {
  const { t } = useTranslation()
  return (
    <TextField
      select
      size="small"
      label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      sx={{ width }}
    >
      <MenuItem value="">{all ?? t('Todas')}</MenuItem>
      {options.map((option) => (
        <MenuItem key={option.value} value={option.value}>
          {option.label}
        </MenuItem>
      ))}
    </TextField>
  )
}
