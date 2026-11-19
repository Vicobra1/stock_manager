import { useEffect, useState, type FormEvent } from 'react'
import { request } from './api'

export type Supplier = { id: number; name: string; phone: string; email: string; address: string; notes: string }
type Form = Omit<Supplier, 'id'>
const EMPTY: Form = { name: '', phone: '', email: '', address: '', notes: '' }

/** Page Fournisseurs (décision F-2) : le gérant ajoute, modifie et supprime ; le vendeur consulte seulement. */
export default function Suppliers({ canEdit, onChanged }: { canEdit: boolean; onChanged: () => void }) {
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [editing, setEditing] = useState<Supplier | null>(null)
  const [form, setForm] = useState<Form | null>(null)
  const [busy, setBusy] = useState(false)

  async function load() {
    try {
      const data = await request('/suppliers/')
      setSuppliers(data.results ?? data); setError('')
    } catch (e) { setError(e instanceof Error ? e.message : 'API indisponible.') }
  }
  useEffect(() => {
    request('/suppliers/').then(data => setSuppliers(data.results ?? data))
      .catch(e => setError(e instanceof Error ? e.message : 'API indisponible.'))
  }, [])

  function openNew() { setEditing(null); setForm(EMPTY); setError('') }
  function openEdit(s: Supplier) { setEditing(s); setForm({ name: s.name, phone: s.phone, email: s.email, address: s.address, notes: s.notes }); setError('') }

  async function save(e: FormEvent) {
    e.preventDefault(); if (!form) return
    setBusy(true); setError('')
    try {
      await request(`/suppliers/${editing ? `${editing.id}/` : ''}`, { method: editing ? 'PATCH' : 'POST', body: JSON.stringify(form) })
      setNotice(editing ? 'Fournisseur modifié.' : 'Fournisseur ajouté.')
      setForm(null)
      await load(); onChanged()
    } catch (err) { setError(err instanceof Error ? err.message : 'Enregistrement impossible.') } finally { setBusy(false) }
  }

  async function remove(s: Supplier) {
    if (!window.confirm(`Supprimer le fournisseur « ${s.name} » ?`)) return
    try {
      await request(`/suppliers/${s.id}/`, { method: 'DELETE' })
      setNotice('Fournisseur supprimé.')
      await load(); onChanged()
    } catch (err) { setNotice(''); setError(err instanceof Error ? err.message : 'Suppression impossible.') }
  }

  const filtered = suppliers.filter(s => `${s.name} ${s.phone} ${s.email}`.toLowerCase().includes(query.toLowerCase()))
  const field = (key: keyof Form) => ({ value: form?.[key] ?? '', onChange: (e: { target: { value: string } }) => form && setForm({ ...form, [key]: e.target.value }) })

  return <>
    {(error || notice) && !form && <div className={`message ${error ? 'error' : ''}`}>{error || notice}<button onClick={() => { setError(''); setNotice('') }}>×</button></div>}
    <section className="panel">
      <div className="panel-head"><div><h2>Fournisseurs</h2><p>{filtered.length} fournisseur{filtered.length !== 1 ? 's' : ''}{canEdit ? '' : ' · consultation seule'}</p></div>
        <div className="panel-tools"><label className="search"><span>⌕</span><input placeholder="Rechercher un fournisseur…" value={query} onChange={e => setQuery(e.target.value)} /></label>
          {canEdit && <button className="primary" onClick={openNew}>＋ <span>Nouveau fournisseur</span></button>}</div></div>
      <div className="table-wrap"><table><thead><tr><th>FOURNISSEUR</th><th>TÉLÉPHONE</th><th>E-MAIL</th><th>ADRESSE</th><th>NOTES</th>{canEdit && <th></th>}</tr></thead>
        <tbody>{filtered.map(s => <tr key={s.id}><td><div className="product-name">{s.name}</div></td><td>{s.phone || '—'}</td><td>{s.email || '—'}</td><td>{s.address || '—'}</td><td>{s.notes || '—'}</td>
          {canEdit && <td><div className="actions"><button title="Modifier" onClick={() => openEdit(s)}>✎</button><button title="Supprimer" aria-label={`Supprimer ${s.name}`} onClick={() => void remove(s)}>×</button></div></td>}</tr>)}
          {!filtered.length && <tr><td colSpan={canEdit ? 6 : 5} className="empty">{suppliers.length ? 'Aucun fournisseur trouvé.' : canEdit ? 'Aucun fournisseur : ajoutez le premier pour pouvoir créer des produits.' : 'Aucun fournisseur pour le moment.'}</td></tr>}</tbody></table></div>
    </section>
    {form && <div className="overlay"><form className="dialog" onSubmit={save}>
      <div className="dialog-head"><div><h2>{editing ? 'Modifier le fournisseur' : 'Nouveau fournisseur'}</h2><p>Seul le nom est obligatoire.</p></div><button type="button" className="close" onClick={() => setForm(null)}>×</button></div>
      <div className="form-grid">
        <label>Nom *<input required autoFocus {...field('name')} /></label>
        <label>Téléphone<input type="tel" {...field('phone')} /></label>
        <label>E-mail<input type="email" {...field('email')} /></label>
        <label>Adresse<input {...field('address')} /></label>
      </div>
      <label>Notes<input {...field('notes')} /></label>
      {error && <p className="form-error">{error}</p>}
      <div className="dialog-actions"><button type="button" className="secondary" onClick={() => setForm(null)}>Annuler</button><button className="primary" disabled={busy}>{busy ? 'Enregistrement…' : 'Enregistrer'}</button></div>
    </form></div>}
  </>
}
