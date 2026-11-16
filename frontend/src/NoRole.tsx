import type { User } from './api'

/** Écran d'un compte connecté qui n'a encore aucun rôle : il n'a accès à aucune donnée. */
export default function NoRole({ user, onLogout }: { user: User; onLogout: () => void }) {
  return <main className="login-page">
    <section className="login-card">
      <div className="brand login-brand"><span className="brand-mark">S</span><span>Stock<span className="brand-light">Boutique</span></span></div>
      <h1>Accès en attente</h1>
      <p className="login-subtitle">Vous êtes connecté en tant que <span className="no-role-user">{user.first_name || user.username}</span>, mais votre compte n’a pas encore de rôle.</p>
      <div className="message">Demandez au gérant de vous attribuer le rôle « Gérant » ou « Vendeur ».</div>
      <button className="secondary no-role-logout" onClick={onLogout}>Se déconnecter</button>
    </section>
  </main>
}
