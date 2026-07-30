import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { GoogleOAuthProvider } from '@react-oauth/google'
import 'leaflet/dist/leaflet.css'
import './index.css'
import './i18n'
import App from './App.tsx'

// Empty string is a valid, intentional state: GoogleOAuthProvider still
// renders (so the rest of the app doesn't crash), but GoogleLoginButton
// checks this same env var itself and shows a "not configured" state
// instead of rendering Google's button with a bad/missing client ID.
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_OAUTH_CLIENT_ID || ''

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </GoogleOAuthProvider>
  </StrictMode>,
)
