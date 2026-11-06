import { useEffect, useState } from 'react'
import { MOVEMENT_LABELS, money, request, type Movement } from './api'

type Option = { id: number; name: string }
type Filters = { q: string; movement_type: string; supplier: string; product: string; date_from: string; date_to: string }
const EMPTY: Filters = { q: '', movement_type: '', supplier: '', product: '', date_from: '', date_to: '' }
const PAGE_SIZE = 20

const dateTime = (iso: string) => new Date(iso).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })

export default function Movements() {
  const [filters, setFilters] = useState<Filters>(EMPTY)
  const [offset, setOffset] = useState(0)
  const [rows, setRows] = useState<Movement[]>([])
  const [count, setCount] = useState(0)
  const [products, setProducts] = useState<Option[]>([])
  const [suppliers, setSuppliers] = useState<Option[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([request('/products/'), request('/suppliers/')])
      .then(([p, s]) => { setProducts(p.results ?? p); setSuppliers(s.results ?? s) })
      .catch(e => setError(e instanceof Error ? e.message : 'API indisponible.'))
  }, [])

  // Recharge à chaque changement de filtre ou de page ; la requête est retardée de 300 ms pour ne pas
  // interroger l'API à chaque frappe (le timer précédent est annulé par le cleanup).
  useEffect(() => {
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) })
    Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value) })
    const timer = setTimeout(() => {
      request(`/movements/?${params}`)
        .then(data => { setRows(data.results); setCount(data.count); setError('') })
        .catch(e => setError(e instanceof Error ? e.message : 'API indisponible.'))
    }, 300)
    return () => clearTimeout(timer)
  }, [filters, offset])

  function update(patch: Partial<Filters>) { setFilters({ ...filters, ...patch }); setOffset(0) }
  const active = Object.values(filters).some(Boolean)
  const from = count ? offset + 1 : 0
  const to = Math.min(offset + PAGE_SIZE, count)

  return <section className="panel">
    <div className="panel-head"><div><h2>Historique des mouvements</h2><p>{count} mouvement{count !== 1 ? 's' : ''}{active ? ' correspondant aux filtres' : ''}</p></div>
      <label className="search"><span>⌕</span><input placeholder="Produit, référence ou note…" value={filters.q} onChange={e => update({ q: e.target.value })} /></label></div>
    <div className="filters">
      <label>Type<select value={filters.movement_type} onChange={e => update({ movement_type: e.target.value })}><option value="">Tous</option>{Object.entries(MOVEMENT_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>Fournisseur<select value={filters.supplier} onChange={e => update({ supplier: e.target.value })}><option value="">Tous</option>{suppliers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
      <label>Produit<select value={filters.product} onChange={e => update({ product: e.target.value })}><option value="">Tous</option>{products.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
      <label>Du<input type="date" value={filters.date_from} max={filters.date_to || undefined} onChange={e => update({ date_from: e.target.value })} /></label>
      <label>Au<input type="date" value={filters.date_to} min={filters.date_from || undefined} onChange={e => update({ date_to: e.target.value })} /></label>
      <button className="secondary" disabled={!active} onClick={() => { setFilters(EMPTY); setOffset(0) }}>Réinitialiser</button>
    </div>
    {error && <div className="message error filters-msg">{error}</div>}
    <div className="table-wrap"><table><thead><tr><th>DATE</th><th>PRODUIT</th><th>TYPE</th><th>QUANTITÉ</th><th>PRIX UNITAIRE</th><th>NOTE</th></tr></thead>
      <tbody>{rows.map(m => <tr key={m.id}><td>{dateTime(m.created_at)}</td><td><div className="product-name">{m.product_name}</div><div className="ref">{m.product_reference}</div></td><td><span className={`badge move-${m.movement_type}`}>{MOVEMENT_LABELS[m.movement_type]}</span></td><td><b>{m.movement_type === 'sale' ? '−' : '+'}{m.quantity}</b></td><td>{m.unit_price ? money(m.unit_price) : '—'}</td><td>{m.note || '—'}</td></tr>)}
        {!rows.length && <tr><td colSpan={6} className="empty">{active ? 'Aucun mouvement ne correspond à ces filtres.' : 'Aucun mouvement enregistré.'}</td></tr>}</tbody></table></div>
    <div className="pager"><span>{from}–{to} sur {count}</span><div><button className="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>← Précédent</button> <button className="secondary" disabled={offset + PAGE_SIZE >= count} onClick={() => setOffset(offset + PAGE_SIZE)}>Suivant →</button></div></div>
  </section>
}
