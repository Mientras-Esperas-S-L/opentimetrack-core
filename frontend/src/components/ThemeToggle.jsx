/** Elegir claro, oscuro o el del sistema.
 *
 *  Tres opciones y no dos. Un interruptor de dos posiciones obliga a elegir un
 *  bando y pierde la única respuesta que acierta sin preguntar: la del sistema.
 *  Quien puso su teléfono en oscuro a las nueve de la noche no quiere volver a
 *  decirlo aquí.
 *
 *  En la barra superior y no enterrado en Ajustes: es una preferencia de este
 *  aparato --- se guarda en el navegador, no en la ficha --- y quien la busca la
 *  busca porque le está molestando la pantalla **ahora**.
 */

import { useState } from 'react'
import IconButton from '@mui/material/IconButton'
import ListItemIcon from '@mui/material/ListItemIcon'
import ListItemText from '@mui/material/ListItemText'
import Menu from '@mui/material/Menu'
import MenuItem from '@mui/material/MenuItem'
import Tooltip from '@mui/material/Tooltip'
import CheckIcon from '@mui/icons-material/Check'
import DarkModeIcon from '@mui/icons-material/DarkMode'
import LightModeIcon from '@mui/icons-material/LightMode'
import SettingsBrightnessIcon from '@mui/icons-material/SettingsBrightness'

import { useColorScheme } from '../hooks/useColorScheme.js'

const OPTIONS = [
  { value: 'system', label: 'El del sistema', icon: <SettingsBrightnessIcon fontSize="small" /> },
  { value: 'light', label: 'Claro', icon: <LightModeIcon fontSize="small" /> },
  { value: 'dark', label: 'Oscuro', icon: <DarkModeIcon fontSize="small" /> },
]

export default function ThemeToggle() {
  const { choice, resolved, setChoice } = useColorScheme()
  const [anchor, setAnchor] = useState(null)

  return (
    <>
      <Tooltip title="Aspecto de la pantalla">
        <IconButton
          size="small"
          onClick={(event) => setAnchor(event.currentTarget)}
          aria-label="Cambiar entre claro y oscuro"
          aria-haspopup="menu"
        >
          {/* El icono dice lo que se está viendo, no lo que se elegiría al
              pulsar: un sol cuando la pantalla está clara. Al revés se lee como
              un error cada vez. */}
          {resolved === 'dark' ? (
            <DarkModeIcon fontSize="small" />
          ) : (
            <LightModeIcon fontSize="small" />
          )}
        </IconButton>
      </Tooltip>

      <Menu anchorEl={anchor} open={Boolean(anchor)} onClose={() => setAnchor(null)}>
        {OPTIONS.map((option) => (
          <MenuItem
            key={option.value}
            selected={choice === option.value}
            onClick={() => {
              setChoice(option.value)
              setAnchor(null)
            }}
          >
            <ListItemIcon>{option.icon}</ListItemIcon>
            <ListItemText>{option.label}</ListItemText>
            {choice === option.value && <CheckIcon fontSize="small" sx={{ ml: 1.5 }} />}
          </MenuItem>
        ))}
      </Menu>
    </>
  )
}
