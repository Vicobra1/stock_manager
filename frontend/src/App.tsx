import { useEffect, useState, type FormEvent } from 'react'
import './App.css'
import Dashboard from './Dashboard'
import Movements from './Movements'

type Supplier = { id: number; name: string }
type Product = { id: number; name: string; reference: string; supplier: number; supplier_name: string; purchase_price: string; selling_price: string; quantity: number; low_stock_threshold: number; is_low_stock: boolean; is_active: boolean }
const API = '/api'

type Page = 'dashboard' | 'products' | 'movements'
const PAGES: Record<Page, { icon: string; label: string; title: string; subtitle: string }> = {
  dashboard: { icon: '◔', label: 'Tableau de bord', title: 'Tableau de bord', subtitle: 'Ventes, valeur du stock et alertes en un coup d’œil.' },
  products: { icon: '▦', label: 'Produits', title: 'Produits', subtitle: 'Gérez votre catalogue et suivez les quantités disponibles.' },
  movements: { icon: '⇅', label: 'Mouvements', title: 'Historique des mouvements', subtitle: 'Toutes les entrées et ventes, filtrables par type, produit, fournisseur et date.' },
}

function App() {
  const [page, setPage] = useState<Page>('products')
  const [products, setProducts] = useState<Product[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [query, setQuery] = useState('')
  const [includeInactive, setIncludeInactive] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<Product | null>(null)
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({ name: '', reference: '', supplier: '', purchase_price: '', selling_price: '', initial_quantity: '0', low_stock_threshold: '5' })
  const [movement, setMovement] = useState<{ product: Product; kind: 'sale' | 'entry' } | null>(null)
  const [moveQty, setMoveQty] = useState('1')

  async function request(path: string, init?: RequestInit) {
    const response = await fetch(`${API}${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.detail || Object.values(data).flat().join(' ') || 'Une erreur est survenue.')
    return data
  }
  async function refresh() {
    try {
      const [p, s] = await Promise.all([request(includeInactive ? '/products/' : '/products/?active=true'), request('/suppliers/')])
      setProducts(p.results ?? p); setSuppliers(s.results ?? s); setError('')
    } catch (e) { setError(e instanceof Error ? e.message : 'API indisponible. Vérifiez que Django est démarré.') }
  }
  useEffect(() => { void refresh() }, [includeInactive])

  function openNew() {
    setEditing(null); setForm({ name: '', reference: '', supplier: '', purchase_price: '', selling_price: '', initial_quantity: '0', low_stock_threshold: '5' }); setShowForm(true)
  }
  function openEdit(p: Product) {
    setEditing(p); setForm({ name: p.name, reference: p.reference, supplier: String(p.supplier), purchase_price: p.purchase_price, selling_price: p.selling_price, initial_quantity: '0', low_stock_threshold: String(p.low_stock_threshold) }); setShowForm(true)
  }
  async function saveProduct(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError('')
    const body = { ...form, supplier: Number(form.supplier), purchase_price: Number(form.purchase_price), selling_price: Number(form.selling_price), low_stock_threshold: Number(form.low_stock_threshold), ...(editing ? {} : { initial_quantity: Number(form.initial_quantity) }) }
    try { await request(`/products/${editing ? `${editing.id}/` : ''}`, { method: editing ? 'PATCH' : 'POST', body: JSON.stringify(body) }); setShowForm(false); setNotice(editing ? 'Produit modifié.' : 'Produit ajouté.'); await refresh() }
    catch (e) { setError(e instanceof Error ? e.message : 'Enregistrement impossible.') } finally { setBusy(false) }
  }
  async function submitMovement(e: FormEvent) {
    e.preventDefault(); if (!movement) return; setBusy(true)
    try { await request(`/products/${movement.product.id}/${movement.kind}/`, { method: 'POST', body: JSON.stringify({ quantity: Number(moveQty) }) }); setMovement(null); setNotice(movement.kind === 'sale' ? 'Vente enregistrée.' : 'Entrée de stock enregistrée.'); await refresh() }
    catch (e) { setError(e instanceof Error ? e.message : 'Mouvement impossible.') } finally { setBusy(false) }
  }
  async function remove(p: Product) {
    if (!window.confirm(`Supprimer « ${p.name} » ?`)) return
    try { await request(`/products/${p.id}/`, { method: 'DELETE' }); setNotice('Produit supprimé.'); await refresh() }
    catch (e) { setError(e instanceof Error ? e.message : 'Suppression impossible.') }
  }
  async function deactivate(p: Product) {
    if (!window.confirm(`Désactiver « ${p.name} » ? Le produit sera retiré du catalogue actif, mais son historique sera conservé.`)) return
    try {
      await request(`/products/${p.id}/`, { method: 'PATCH', body: JSON.stringify({ is_active: false }) })
      setNotice(`${p.name} a été désactivé.`)
      await refresh()
    } catch (e) { setError(e instanceof Error ? e.message : 'Désactivation impossible.') }
  }
  async function reactivate(p: Product) {
    try {
      await request(`/products/${p.id}/`, { method: 'PATCH', body: JSON.stringify({ is_active: true }) })
      setNotice(`${p.name} a été réactivé.`)
      await refresh()
    } catch (e) { setError(e instanceof Error ? e.message : 'Réactivation impossible.') }
  }
  const filtered = products.filter(p => `${p.name} ${p.reference} ${p.supplier_name}`.toLowerCase().includes(query.toLowerCase()))
  const lowCount = products.filter(p => p.is_low_stock).length
  const money = (v: string) => `${Number(v).toLocaleString('fr-FR')} FC`

  return <main className="app-shell">
    <aside className="sidebar"><div className="brand"><span className="brand-mark">S</span><span>Stock<span className="brand-light">Boutique</span></span></div><p className="nav-label">GESTION</p>{(Object.keys(PAGES) as Page[]).map(key => <button key={key} className={`nav-item ${page === key ? 'active' : ''}`} onClick={() => setPage(key)}><span>{PAGES[key].icon}</span> {PAGES[key].label}</button>)}<div className="side-note"><span className="status-dot"/> API Django</div></aside>
    <section className="main-area"><header className="topbar"><span className="crumb">Gestion <span>/</span> {PAGES[page].label}</span><span className="avatar">B</span></header>
      <div className="content"><div className="page-heading"><div><p className="eyebrow">INVENTAIRE</p><h1>{PAGES[page].title}</h1><p className="subtitle">{PAGES[page].subtitle}</p></div>{page === 'products' && <button className="primary" onClick={openNew}>＋ <span>Nouveau produit</span></button>}</div>
        {page === 'dashboard' && <Dashboard onShowMovements={() => setPage('movements')} />}
        {page === 'movements' && <Movements />}
        {page === 'products' && <>
        <div className="stats"><article className="stat-card"><span className="stat-icon purple">▦</span><div><p>Produits actifs</p><strong>{products.length}</strong></div></article><article className="stat-card"><span className="stat-icon amber">↘</span><div><p>Stock faible</p><strong>{lowCount}</strong></div></article><article className="stat-card"><span className="stat-icon green">▤</span><div><p>Fournisseurs</p><strong>{suppliers.length}</strong></div></article></div>
        {(error || notice) && <div className={`message ${error ? 'error' : ''}`}>{error || notice}<button onClick={() => { setError(''); setNotice('') }}>×</button></div>}
        <section className="panel"><div className="panel-head"><div><h2>Catalogue produits</h2><p>{filtered.length} produit{filtered.length !== 1 ? 's' : ''}</p><label className="inactive-filter"><input type="checkbox" checked={includeInactive} onChange={e => setIncludeInactive(e.target.checked)} /> Inclure les produits désactivés</label></div><label className="search"><span>⌕</span><input placeholder="Rechercher un produit…" value={query} onChange={e => setQuery(e.target.value)} /></label></div>
          <div className="table-wrap"><table><thead><tr><th>PRODUIT</th><th>FOURNISSEUR</th><th>PRIX D’ACHAT</th><th>PRIX DE VENTE</th><th>QUANTITÉ</th><th>ÉTAT</th><th></th></tr></thead><tbody>{filtered.map(p => <tr key={p.id}><td><div className="product-name">{p.name}</div><div className="ref">{p.reference}</div></td><td>{p.supplier_name}</td><td>{money(p.purchase_price)}</td><td className="price-sale">{money(p.selling_price)}</td><td><b>{p.quantity}</b><span className="unit"> unités</span></td><td><span className={`badge ${!p.is_active ? 'inactive' : p.is_low_stock ? 'warning' : 'success'}`}><i/> {!p.is_active ? 'Désactivé' : p.is_low_stock ? 'Stock faible' : 'En stock'}</span></td><td><div className="actions">{p.is_active ? <><button title="Enregistrer une vente" onClick={() => { setMovement({ product: p, kind: 'sale' }); setMoveQty('1') }}>−</button><button title="Ajouter du stock" onClick={() => { setMovement({ product: p, kind: 'entry' }); setMoveQty('1') }}>＋</button><button title="Modifier" onClick={() => openEdit(p)}>✎</button><button title="Désactiver le produit" aria-label={`Désactiver ${p.name}`} onClick={() => void deactivate(p)}>⏻</button></> : <button title="Réactiver le produit" aria-label={`Réactiver ${p.name}`} onClick={() => void reactivate(p)}>↻</button>}<button title="Supprimer" onClick={() => void remove(p)}>×</button></div></td></tr>)}{!filtered.length && <tr><td colSpan={7} className="empty">{error ? 'Connexion à l’API en attente…' : 'Aucun produit trouvé.'}</td></tr>}</tbody></table></div>
        </section></>}
      </div>
    </section>
    {showForm && <div className="overlay"><form className="dialog" onSubmit={saveProduct}><div className="dialog-head"><div><h2>{editing ? 'Modifier le produit' : 'Nouveau produit'}</h2><p>Les champs marqués d’un astérisque sont obligatoires.</p></div><button type="button" className="close" onClick={() => setShowForm(false)}>×</button></div><div className="form-grid"><label>Nom *<input required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}/></label><label>Référence *<input required value={form.reference} onChange={e => setForm({ ...form, reference: e.target.value })}/></label><label>Fournisseur *<select required value={form.supplier} onChange={e => setForm({ ...form, supplier: e.target.value })}><option value="">Choisir un fournisseur</option>{suppliers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label><label>Prix d’achat (FC) *<input required min="0" step="0.01" type="number" value={form.purchase_price} onChange={e => setForm({ ...form, purchase_price: e.target.value })}/></label><label>Prix de vente (FC) *<input required min="0" step="0.01" type="number" value={form.selling_price} onChange={e => setForm({ ...form, selling_price: e.target.value })}/></label>{!editing && <label>Stock initial<input min="0" type="number" value={form.initial_quantity} onChange={e => setForm({ ...form, initial_quantity: e.target.value })}/></label>}<label>Seuil d’alerte<input min="0" type="number" value={form.low_stock_threshold} onChange={e => setForm({ ...form, low_stock_threshold: e.target.value })}/></label></div>{error && <p className="form-error">{error}</p>}<div className="dialog-actions"><button type="button" className="secondary" onClick={() => setShowForm(false)}>Annuler</button><button className="primary" disabled={busy}>{busy ? 'Enregistrement…' : 'Enregistrer'}</button></div></form></div>}
    {movement && <div className="overlay"><form className="dialog narrow" onSubmit={submitMovement}><div className="dialog-head"><div><h2>{movement.kind === 'sale' ? 'Enregistrer une vente' : 'Ajouter au stock'}</h2><p>{movement.product.name} · disponible : {movement.product.quantity}</p></div><button type="button" className="close" onClick={() => setMovement(null)}>×</button></div><label>Quantité *<input required min="1" max={movement.kind === 'sale' ? movement.product.quantity : undefined} type="number" value={moveQty} onChange={e => setMoveQty(e.target.value)}/></label>{error && <p className="form-error">{error}</p>}<div className="dialog-actions"><button type="button" className="secondary" onClick={() => setMovement(null)}>Annuler</button><button className="primary" disabled={busy}>{busy ? 'Traitement…' : 'Confirmer'}</button></div></form></div>}
  </main>
}
export default App
