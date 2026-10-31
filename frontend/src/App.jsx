import { useEffect, useState } from 'react'
import { ApiError, currentSession, logout, setUnauthorizedHandler } from './api'
import { AppShell } from './components/AppShell'
import { Login } from './pages/Login'
import { Notes } from './pages/Notes'
import { Tasks } from './pages/Tasks'
import { Today } from './pages/Today'

function viewFromHash() {
  const value = window.location.hash.replace('#', '')
  if (value === 'tasks' || value === 'notes') return value
  return 'today'
}

export default function App() {
  const [session, setSession] = useState('loading')
  const [bootError, setBootError] = useState('')
  const [view, setView] = useState(viewFromHash)

  useEffect(() => {
    setUnauthorizedHandler(() => setSession('out'))
  }, [])

  useEffect(() => {
    let cancelled = false
    currentSession()
      .then(() => {
        if (!cancelled) setSession('in')
      })
      .catch((error) => {
        if (cancelled) return
        if (!(error instanceof ApiError && error.status === 401)) {
          setBootError(error.message || 'Cannot reach the API')
        }
        setSession('out')
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const onHash = () => setView(viewFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  function openView(next) {
    window.location.hash = next
    setView(next)
  }

  async function signOut() {
    try {
      await logout()
    } catch {
      // Drop the local session either way.
    }
    setSession('out')
  }

  if (session === 'loading') {
    return (
      <main className="login-screen">
        <p className="status-line">Checking session…</p>
      </main>
    )
  }

  if (session === 'out') {
    return <Login notice={bootError} onSuccess={() => setSession('in')} />
  }

  return (
    <AppShell view={view} onNavigate={openView} onLogout={signOut}>
      {view === 'today' ? <Today /> : null}
      {view === 'tasks' ? <Tasks /> : null}
      {view === 'notes' ? <Notes /> : null}
    </AppShell>
  )
}
