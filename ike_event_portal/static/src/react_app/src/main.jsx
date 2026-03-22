import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

window.mountReactApp = (container, context) => {
  const root = createRoot(container)
  root.render(
    <StrictMode>
      <App odooContext={context} />
    </StrictMode>
  )
  return root
}

window.unmountReactApp = (root) => {
  if (root) {
    root.unmount()
  }
}