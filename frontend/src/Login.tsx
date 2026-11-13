import { useState, type FormEvent } from 'react'
import { request, setToken, type User } from './api'

export default function Login({ notice, onLogin }: { notice: string; onLogin: (user: User) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError('')
    try {
      const data = await request('/auth/login/', { method: 'POST', body: JSON.stringify({ username, password }) })
      setToken(data.token)
      onLogin(data.user)
    } catch (err) {
      // fetch lève un TypeError quand le serveur est injoignable.
      setError(err instanceof TypeError ? 'API indisponible. Vérifiez que Django est démarré.' : err instanceof Error ? err.message : 'Connexion impossible.')
      setPassword('')
    } finally { setBusy(false) }
  }

  const message = error || notice
  return <main className="login-page">
    <form className="login-card" onSubmit={submit}>
      <div className="brand login-brand"><span className="brand-mark">S</span><span>Stock<span className="brand-light">Boutique</span></span></div>
      <h1>Connexion</h1>
      <p className="login-subtitle">Connectez-vous pour gérer votre stock.</p>
      {message && <div className="message error" role="alert">{message}</div>}
      <label>Nom d’utilisateur<input required autoFocus autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} /></label>
      <label>Mot de passe<input required type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} /></label>
      <button className="primary" disabled={busy}>{busy ? 'Connexion…' : 'Se connecter'}</button>
    </form>
  </main>
}
