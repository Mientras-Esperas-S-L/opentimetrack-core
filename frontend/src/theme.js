import { createTheme } from '@mui/material/styles'

// Un tema propio, no el azul por defecto de MUI. La idea es que la pantalla de
// fichaje se lea de un vistazo en un móvil viejo y a pleno sol: contraste alto,
// tipografía grande y un acento que distinga "dentro" de "fuera" sin depender
// solo del color.
export const buildTheme = (mode = 'light') =>
  createTheme({
    palette: {
      mode,
      primary: { main: mode === 'light' ? '#1b5e4a' : '#4db6a0' },
      secondary: { main: '#b0533a' },
      success: { main: '#2e7d52' },
      background:
        mode === 'light'
          ? { default: '#f6f7f5', paper: '#ffffff' }
          : { default: '#12161a', paper: '#1a2026' },
    },
    shape: { borderRadius: 10 },
    typography: {
      fontFamily: '"Inter", system-ui, -apple-system, "Segoe UI", sans-serif',
      h1: { fontSize: '2rem', fontWeight: 650, letterSpacing: '-0.02em' },
      h2: { fontSize: '1.4rem', fontWeight: 600, letterSpacing: '-0.01em' },
      button: { textTransform: 'none', fontWeight: 600 },
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: { paddingInline: 20, paddingBlock: 10 },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: { backgroundImage: 'none' },
        },
      },
    },
  })
