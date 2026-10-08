import React from 'react'
import ReactDOM from 'react-dom/client'

import App from './App.jsx'
import NewVersionNotice from './components/NewVersionNotice.jsx'
import Providers from './Providers.jsx'
// Escucha desde el arranque la oferta de instalar del navegador, que llega una
// sola vez y antes de que exista el botón.
import './services/install.js'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Providers>
      <App />
      <NewVersionNotice />
    </Providers>
  </React.StrictMode>,
)
