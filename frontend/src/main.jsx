import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.jsx'

// Phase A has no backend, so the MSW mock layer runs everywhere (incl. the
// deployed demo) by default. Once the real API exists, set
// VITE_USE_REAL_API=true to turn the mocks off without touching code.
async function enableMocking() {
  if (import.meta.env.VITE_USE_REAL_API === 'true') return
  const { worker } = await import('./mocks/browser')
  return worker.start({ onUnhandledRequest: 'bypass' })
}

enableMocking().then(() => {
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </StrictMode>,
  )
})
