import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { log } from './lib/logger'

log.ok('Surgeon HUD bundle loaded — check Socket.IO + /video in Network tab if overlays fail.')

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
