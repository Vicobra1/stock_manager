import { useState, type FormEvent } from 'react'
import { ApiError, request } from './api'

type Fields = { username: string; first_name: string; last_name: string; password: string; confirm: string; shop_name: string }
type Errors = Partial<Record<keyof Fields | 'detail', string>>
const EMPTY: Fields = { username: '', first_name: '', last_name: '', password: '', confirm: '', shop_name: '' }

/** Inscription avec création de boutique (décision D6). Après succès, la personne est connectée directement. */
export default function Signup({ onSignedUp, onBack }: { onSignedUp: (accountToken: string) => void; onBack: () => void }) {
  const [form, setForm] = useState<Fields>(EMPTY)
  const [errors, setErrors] = useState<Errors>({})
  const [busy, setBusy] = useState(false)

  const set = (field: keyof Fields) => (e: { target: { value: string } }) => setForm({ ...form, [field]: e.target.value })

  async function submit(e: FormEvent) {
    e.preventDefault()
    // Vérifié ici seulement : les deux saisies doivent être identiques avant d'envoyer quoi que ce soit.
    if (form.password !== form.confirm) { setErrors({ confirm: 'Les deux mots de passe ne sont pas identiques.' }); return }
    setBusy(true); setErrors({})
    try {
      const { confirm: _confirm, ...body } = form
      const data = await request('/auth/signup/', { method: 'POST', body: JSON.stringify(body) })
      onSignedUp(data.token)
    } catch (err) {
      if (err instanceof ApiError && err.status === 400 && typeof err.data === 'object') {
        // Erreurs par champ renvoyées par l'API : { username: [...], password: [...], shop_name: [...] }
        const byField: Errors = {}
        for (const [field, messages] of Object.entries(err.data as Record<string, string | string[]>)) {
          byField[field as keyof Errors] = Array.isArray(messages) ? messages.join(' ') : String(messages)
        }
        setErrors(byField)
      } else {
        setErrors({ detail: err instanceof TypeError ? 'API indisponible. Vérifiez que Django est démarré.'
          : err instanceof Error ? err.message : 'Inscription impossible.' })
      }
      setForm(current => ({ ...current, password: '', confirm: '' }))
    } finally { setBusy(false) }
  }

  const fieldError = (field: keyof Errors) => errors[field] && <span className="field-error">{errors[field]}</span>
  return <main className="login-page">
    <form className="login-card" onSubmit={submit}>
      <div className="brand login-brand"><span className="brand-mark">S</span><span>Stock<span className="brand-light">Boutique</span></span></div>
      <h1>Créer votre boutique</h1>
      <p className="login-subtitle">Votre compte et votre boutique, au plan gratuit.</p>
      {errors.detail && <div className="message error" role="alert">{errors.detail}</div>}
      <label>Nom de la boutique<input required autoFocus value={form.shop_name} onChange={set('shop_name')} />{fieldError('shop_name')}</label>
      <div className="form-row">
        <label>Prénom<input required autoComplete="given-name" value={form.first_name} onChange={set('first_name')} />{fieldError('first_name')}</label>
        <label>Nom<input autoComplete="family-name" placeholder="Facultatif" value={form.last_name} onChange={set('last_name')} />{fieldError('last_name')}</label>
      </div>
      <label>Nom d’utilisateur<input required autoComplete="username" value={form.username} onChange={set('username')} />{fieldError('username')}</label>
      <label>Mot de passe<input required type="password" autoComplete="new-password" value={form.password} onChange={set('password')} />
        {fieldError('password') || <span className="field-hint">Au moins 8 caractères, pas uniquement des chiffres.</span>}</label>
      <label>Confirmer le mot de passe<input required type="password" autoComplete="new-password" value={form.confirm} onChange={set('confirm')} />{fieldError('confirm')}</label>
      <button className="primary" disabled={busy}>{busy ? 'Création…' : 'Créer ma boutique'}</button>
      <p className="login-switch">Déjà un compte ? <button type="button" className="link-button" onClick={onBack}>Se connecter</button></p>
    </form>
  </main>
}
