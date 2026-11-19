import { useState } from 'react'
import { PLAN_LABELS, ROLE_LABELS, type ShopSummary, type User } from './api'

/** Second temps de la connexion (décision D2) : choisir la boutique dans laquelle travailler dans cet onglet. */
export default function ShopChooser({ user, shops, notice, onChoose, onLogout }: {
  user: User
  shops: ShopSummary[]
  notice: string
  onChoose: (shop: ShopSummary) => Promise<void>
  onLogout: () => void
}) {
  const [busy, setBusy] = useState<number | null>(null)
  const [error, setError] = useState('')

  async function choose(shop: ShopSummary) {
    setBusy(shop.id); setError('')
    try { await onChoose(shop) } catch (err) {
      setError(err instanceof Error ? err.message : 'Impossible d’ouvrir cette boutique.')
      setBusy(null)
    }
  }

  const message = error || notice
  return <main className="login-page">
    <section className="login-card">
      <div className="brand login-brand"><span className="brand-mark">S</span><span>Stock<span className="brand-light">Boutique</span></span></div>
      <h1>Choisir une boutique</h1>
      <p className="login-subtitle">Bonjour {user.first_name || user.username}, dans quelle boutique travaillez-vous ?</p>
      {message && <div className="message error" role="alert">{message}</div>}
      <ul className="shop-list">{shops.map(shop => <li key={shop.id}>
        <button className="shop-choice" disabled={busy !== null} onClick={() => void choose(shop)}>
          <span className="shop-choice-name">{shop.name}</span>
          <span className="shop-choice-meta"><span className={`role-badge ${shop.role}`}>{ROLE_LABELS[shop.role]}</span> Plan {PLAN_LABELS[shop.plan]}</span>
          <span className="shop-choice-go">{busy === shop.id ? 'Ouverture…' : '→'}</span>
        </button>
      </li>)}</ul>
      <button className="secondary no-role-logout" onClick={onLogout}>Se déconnecter</button>
    </section>
  </main>
}
