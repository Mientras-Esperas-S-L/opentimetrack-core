import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Divider from '@mui/material/Divider'
import Drawer from '@mui/material/Drawer'
import IconButton from '@mui/material/IconButton'
import List from '@mui/material/List'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemText from '@mui/material/ListItemText'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import CloseIcon from '@mui/icons-material/Close'

import { getHelpArticle, getHelpIndex, searchHelp } from '../services/api.js'

/** La ayuda de la aplicación, en un cajón lateral.
 *
 *  Al lado y no encima: quien lee la ayuda la lee **para hacer algo**, y una ventana
 *  que tapa el formulario obliga a memorizar el paso y cerrarla para ejecutarlo. Por
 *  eso el cajón no es modal y la pantalla sigue viéndose y usándose detrás.
 *
 *  Tres estados y no más: el índice, una búsqueda y un artículo. Sin historial ni
 *  migas de pan, que en un corpus de unas decenas de artículos cortos es peso muerto:
 *  la flecha vuelve al índice y ya está.
 */
export default function HelpDrawer({ abierto, tema, onClose }) {
  const { t, i18n } = useTranslation()
  const idioma = (i18n.language || 'es').slice(0, 2)

  const [indice, setIndice] = useState(null)
  const [articulo, setArticulo] = useState(null)
  const [busqueda, setBusqueda] = useState('')
  const [resultados, setResultados] = useState(null)
  const [error, setError] = useState(null)

  //  El artículo que pidió el botón. **El cajón se remonta con una `key` en cada
  //  apertura** ---la pone AppShell---, así que aquí no hay que limpiar nada: un
  //  `setState` síncrono dentro de un efecto dispara renders en cascada y el linter
  //  del proyecto lo para.
  useEffect(() => {
    if (!abierto || !tema) return
    getHelpArticle(tema, idioma)
      .then(setArticulo)
      .catch(() => {
        //  Que falte un artículo no es motivo para no enseñar nada: se cae al índice
        //  y se dice, que es mejor que un cajón en blanco.
        setError('sin-articulo')
      })
  }, [abierto, tema, idioma])

  useEffect(() => {
    if (!abierto || indice) return
    getHelpIndex(idioma)
      .then(setIndice)
      .catch(() => setError('sin-indice'))
  }, [abierto, indice, idioma])

  const abrir = useCallback(
    (slug) => {
      setError(null)
      getHelpArticle(slug, idioma)
        .then(setArticulo)
        .catch(() => setError('sin-articulo'))
    },
    [idioma]
  )

  const buscar = useCallback(
    (texto) => {
      setBusqueda(texto)
      if (texto.trim().length < 2) {
        setResultados(null)
        return
      }
      searchHelp(texto, idioma)
        .then((d) => setResultados(d.results))
        .catch(() => setResultados([]))
    },
    [idioma]
  )

  const enLista = resultados ?? null

  return (
    <Drawer
      anchor="right"
      open={abierto}
      onClose={onClose}
      //  `keepMounted` no: el cajón pide su contenido al abrirse y mantenerlo montado
      //  dejaría el artículo de la vez anterior a la vista durante un instante.
      //
      //  Y con sitio para la barra de arriba: el cajón ocupa la altura entera de la
      //  ventana y la barra va por encima, así que sin este hueco su cabecera queda
      //  debajo ---medido en devel: no se veían ni el título ni el botón de cerrar,
      //  y el primer aviso salía cortado por la mitad---.
      PaperProps={{
        sx: {
          width: { xs: '100%', sm: 420 },
          p: 2,
          pt: { xs: 9, md: 11 },
          display: 'flex',
          flexDirection: 'column',
        },
      }}
    >
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
        <Stack direction="row" sx={{ alignItems: 'center', gap: 0.5 }}>
          {articulo && (
            <IconButton size="small" onClick={() => setArticulo(null)} aria-label={t('Volver al índice')}>
              <ArrowBackIcon fontSize="small" />
            </IconButton>
          )}
          <Typography variant="h3" sx={{ fontSize: '1.05rem' }}>
            {t('Ayuda')}
          </Typography>
        </Stack>
        <IconButton size="small" onClick={onClose} aria-label={t('Cerrar la ayuda')}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </Stack>

      {error === 'sin-indice' && <Alert severity="error">{t('No he podido leer la ayuda.')}</Alert>}
      {error === 'sin-articulo' && (
        <Alert severity="info" sx={{ mb: 1 }}>
          {t('Todavía no hay un artículo para esta pantalla.')}
        </Alert>
      )}

      {articulo ? (
        <Box>
          <Typography variant="h2" sx={{ fontSize: '1.25rem', mb: 0.5 }}>
            {articulo.title}
          </Typography>
          {articulo.summary && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {articulo.summary}
            </Typography>
          )}
          {articulo.blocks.map((bloque, i) => (
            <Bloque key={i} bloque={bloque} />
          ))}
        </Box>
      ) : (
        <>
          <TextField
            size="small"
            fullWidth
            value={busqueda}
            onChange={(e) => buscar(e.target.value)}
            label={t('Buscar en la ayuda')}
            sx={{ mb: 1 }}
          />
          {enLista ? (
            <List dense>
              {enLista.length === 0 && (
                <Typography variant="body2" color="text.secondary" sx={{ p: 1 }}>
                  {t('Nada que se parezca a eso.')}
                </Typography>
              )}
              {enLista.map((a) => (
                <ListItemButton key={a.slug} onClick={() => abrir(a.slug)}>
                  <ListItemText primary={a.title} secondary={a.summary} />
                </ListItemButton>
              ))}
            </List>
          ) : (
            (indice?.sections ?? []).map((seccion) => (
              <Box key={seccion.slug} sx={{ mb: 1 }}>
                <Typography variant="overline" color="text.secondary">
                  {seccion.title}
                </Typography>
                <Divider />
                <List dense>
                  {seccion.articles.map((a) => (
                    <ListItemButton key={a.slug} onClick={() => abrir(a.slug)}>
                      <ListItemText primary={a.title} secondary={a.summary} />
                    </ListItemButton>
                  ))}
                </List>
              </Box>
            ))
          )}
          {indice?.sections?.length === 0 && !enLista && (
            <Typography variant="body2" color="text.secondary">
              {t('Todavía no hay ayuda escrita.')}
            </Typography>
          )}
        </>
      )}

      <Box sx={{ flexGrow: 1 }} />
      {articulo && (
        <Button size="small" onClick={() => setArticulo(null)} sx={{ mt: 2, alignSelf: 'flex-start' }}>
          {t('Volver al índice')}
        </Button>
      )}
    </Drawer>
  )
}

/** Un bloque del artículo. Cada tipo sabe cómo se ve; lo que no se reconoce se
 *  ignora en silencio, para que un bloque nuevo del servidor no rompa una pantalla
 *  vieja. */
function Bloque({ bloque }) {
  const { data, kind } = bloque
  if (kind === 'heading') {
    return (
      <Typography variant="h3" sx={{ fontSize: '1rem', mt: 2, mb: 0.5 }}>
        {data.text}
      </Typography>
    )
  }
  if (kind === 'paragraph') {
    return (
      <Typography variant="body2" sx={{ mb: 1 }}>
        {data.text}
      </Typography>
    )
  }
  if (kind === 'list') {
    return (
      <Box component={data.ordered ? 'ol' : 'ul'} sx={{ pl: 3, mb: 1 }}>
        {(data.items ?? []).map((item, i) => (
          <Typography key={i} component="li" variant="body2">
            {item}
          </Typography>
        ))}
      </Box>
    )
  }
  if (kind === 'callout') {
    return (
      <Alert severity={data.variant === 'warning' ? 'warning' : 'info'} sx={{ my: 1 }}>
        {data.text}
      </Alert>
    )
  }
  return null
}
