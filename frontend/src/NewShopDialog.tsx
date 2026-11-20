import { useState, type FormEvent } from 'react'
import { ApiError, request, type ShopSummary } from './api'

/** Créer une boutique de plus (décision D6) : réservé aux gérants ; elle démarre au plan gratuit. */
export default function NewShopDialog({ onCreated, onClose }: {
  onCreated: (shop: ShopSummary) => Promise<void> | void
  onClose: () => void
}) {
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError('')
    try {
      const shop: ShopSummary = await request('/auth/shops/', { method: 'POST', body: JSON.stringify({ name }) })
      await onCreated(shop)
    } catch (err) {
      // Nom déjà pris ou vide : { name: [...] } ; sinon le message général (« Seul un gérant… »).
      const byName = err instanceof ApiError ? (err.data as { name?: string[] } | null)?.name : undefined
      setError(byName ? byName.join(' ') : err instanceof Error ? err.message : 'Création impossible.')
      setBusy(false)
    }
  }

  return <div className="overlay"><form className="dialog narrow" onSubmit={submit}>
    <div className="dialog-head"><div><h2>Nouvelle boutique</h2><p>Vous en serez le gérant. Elle démarre au plan gratuit.</p></div>
      <button type="button" className="close" onClick={onClose}>×</button></div>
    <label>Nom de la boutique *<input required autoFocus maxLength={150} value={name} onChange={e => setName(e.target.value)} /></label>
    {error && <p className="form-error" role="alert">{error}</p>}
    <div className="dialog-actions"><button type="button" className="secondary" onClick={onClose}>Annuler</button>
      <button className="primary" disabled={busy}>{busy ? 'Création…' : 'Créer et ouvrir'}</button></div>
  </form></div>
}
