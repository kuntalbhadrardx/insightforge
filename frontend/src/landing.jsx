import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './landing.css'
import Landing from './LandingPage.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Landing />
  </StrictMode>,
)
