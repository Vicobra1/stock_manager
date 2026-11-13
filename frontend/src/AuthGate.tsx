import { useEffect, useState } from 'react'
import App from './App'
import Login from './Login'
import { clearToken, getToken, request, setUnauthorizedHandler, type User } from './api'

/** Affiche la page de connexion tant qu'aucun utilisateur n'est connecté, puis l'application. */
export default function AuthGate() {
  const [user, setUser] = useState<User | null>(null)
  const [checking, setChecking] = useState(() => getToken() !== null)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    setUnauthorizedHandler(() => { setUser(null); setNotice('Votre session a expiré. Veuillez vous reconnecter.') })
    // Au rechargement de la page, le jeton conservé permet de restaurer la session.
    if (getToken()) {
      request('/auth/me/')
        .then(setUser)
        .catch(() => setNotice(current => current || 'Impossible de vérifier votre session. Vérifiez que Django est démarré.'))
        .finally(() => setChecking(false))
    }
    return () => setUnauthorizedHandler(null)
  }, [])

  async function logout() {
    // Même si l'appel échoue (API injoignable, jeton déjà invalide), l'utilisateur doit être déconnecté de cet écran.
    try { await request('/auth/logout/', { method: 'POST' }) } catch { /* rien de plus à faire */ }
    clearToken()
    setUser(null)
    setNotice('')
  }

  if (checking) return <main className="login-page"><p className="login-subtitle">Chargement…</p></main>
  if (!user) return <Login notice={notice} onLogin={u => { setNotice(''); setUser(u) }} />
  return <App user={user} onLogout={() => void logout()} />
}
