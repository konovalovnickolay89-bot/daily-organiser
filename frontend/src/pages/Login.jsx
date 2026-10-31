import { useState } from 'react'
import { login } from '../api'
import { ErrorText } from '../components/ErrorText'

export function Login({ onSuccess, notice = '' }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setPending(true)
    setError('')
    try {
      await login(password)
      onSuccess()
    } catch (err) {
      setError(err.message || 'Could not sign in')
    } finally {
      setPending(false)
    }
  }

  return (
    <main className="login-screen">
      <form className="card login-card" onSubmit={submit}>
        <p className="eyebrow">Home</p>
        <h1>Daily Organiser</h1>
        <p className="lede">Tasks and notes for this house. One shared password.</p>
        <label htmlFor="login-password">Password</label>
        <input
          id="login-password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
          autoFocus
        />
        <ErrorText>{error || notice}</ErrorText>
        <button type="submit" className="button button-primary" disabled={pending}>
          {pending ? 'Checking…' : 'Log in'}
        </button>
      </form>
    </main>
  )
}
