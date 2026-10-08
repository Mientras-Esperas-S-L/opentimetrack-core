import { Component } from 'react'
import { useTranslation } from 'react-i18next'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'

/** Lo que se ve si una pantalla revienta al pintarse.
 *
 *  Sin esto, un error de pintado desmontaba la aplicación entera y quedaba la
 *  página en blanco, sin menú ni forma de salir que no fuera recargar. Pasó al
 *  cancelar el diálogo de un permiso (08/10/2026). Va alrededor de la pantalla
 *  y no de toda la aplicación: la barra y el menú siguen ahí, y cambiar de
 *  pantalla la vuelve a intentar, porque quien la monta le pone la ruta de `key`.
 *
 *  No arregla el fallo que lo dispara: lo deja en la consola, como antes, y le
 *  da a la persona por dónde seguir.
 */
export default class FalloDePantalla extends Component {
  state = { fallo: null }

  static getDerivedStateFromError(fallo) {
    return { fallo }
  }

  render() {
    return this.state.fallo ? <Aviso /> : this.props.children
  }
}

function Aviso() {
  const { t } = useTranslation()
  return (
    <Box sx={{ maxWidth: 560 }}>
      <Alert
        severity="error"
        action={
          <Button color="inherit" size="small" onClick={() => window.location.reload()}>
            {t('Recargar')}
          </Button>
        }
      >
        {t('Algo ha fallado en esta pantalla. Lo que ya estaba guardado sigue guardado.')}
      </Alert>
    </Box>
  )
}
