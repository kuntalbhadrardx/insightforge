import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './landing.css'
import './auth.css'
import AuthPage from './AuthPage.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <AuthPage />
  </StrictMode>,
)
