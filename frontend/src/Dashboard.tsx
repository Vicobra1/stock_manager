import { useEffect, useState } from 'react'
import { MOVEMENT_LABELS, money, request, type Movement } from './api'

type DashboardData = {
  products: { active: number; low_stock: number; out_of_stock: number }
  stock_value: { at_cost: string; at_retail: string }
  today: { revenue: string; profit: string; units: number }
  last_7_days: { date: string; revenue: string; profit: string; units: number }[]
  low_stock_products: { id: number; name: string; reference: string; supplier_name: string; quantity: number; low_stock_threshold: number }[]
  top_products: { product: number; name: string; reference: string; units: number; revenue: string }[]
  recent_movements: Movement[]
}

const dayLabel = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric' })
const dateTime = (iso: string) => new Date(iso).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })

export default function Dashboard({ onShowMovements }: { onShowMovements: () => void }) {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    request('/dashboard/').then(setData).catch(e => setError(e instanceof Error ? e.message : 'API indisponible.'))
  }, [])

  if (error) return <div className="message error">{error}</div>
  if (!data) return <p className="subtitle">Chargement…</p>

  const maxRevenue = Math.max(...data.last_7_days.map(d => Number(d.revenue)), 1)
  const weekRevenue = data.last_7_days.reduce((sum, d) => sum + Number(d.revenue), 0)

  return <>
    <div className="stats stats-4">
      <article className="stat-card"><span className="stat-icon green">$</span><div><p>Ventes du jour</p><strong>{money(data.today.revenue)}</strong><small>{data.today.units} unité{data.today.units !== 1 ? 's' : ''} · bénéfice {money(data.today.profit)}</small></div></article>
      <article className="stat-card"><span className="stat-icon purple">▦</span><div><p>Valeur du stock (achat)</p><strong>{money(data.stock_value.at_cost)}</strong><small>à la vente : {money(data.stock_value.at_retail)}</small></div></article>
      <article className="stat-card"><span className="stat-icon amber">↘</span><div><p>Stock faible</p><strong>{data.products.low_stock}</strong><small>dont {data.products.out_of_stock} en rupture</small></div></article>
      <article className="stat-card"><span className="stat-icon purple">▤</span><div><p>Produits actifs</p><strong>{data.products.active}</strong></div></article>
    </div>

    <div className="dash-grid">
      <section className="panel">
        <div className="panel-head"><div><h2>Ventes des 7 derniers jours</h2><p>{money(weekRevenue)} de chiffre d’affaires</p></div></div>
        <div className="bars">{data.last_7_days.map(d => <div className="bar-col" key={d.date} title={`${money(d.revenue)} · ${d.units} unité(s)`}>
          <span className="bar-value">{Number(d.revenue) ? money(d.revenue) : ''}</span>
          <div className="bar" style={{ height: `${(Number(d.revenue) / maxRevenue) * 100}%` }} />
          <span className="bar-label">{dayLabel(d.date)}</span>
        </div>)}</div>
      </section>

      <section className="panel">
        <div className="panel-head"><div><h2>Meilleures ventes</h2><p>30 derniers jours, en unités</p></div></div>
        <ul className="list">{data.top_products.map(p => <li key={p.product}><div><div className="product-name">{p.name}</div><div className="ref">{p.reference}</div></div><div className="list-end"><b>{p.units}</b><span className="unit"> · {money(p.revenue)}</span></div></li>)}
          {!data.top_products.length && <li className="empty-li">Aucune vente sur la période.</li>}</ul>
      </section>

      <section className="panel">
        <div className="panel-head"><div><h2>Produits à réapprovisionner</h2><p>Les plus urgents en premier</p></div></div>
        <ul className="list">{data.low_stock_products.map(p => <li key={p.id}><div><div className="product-name">{p.name}</div><div className="ref">{p.reference} · {p.supplier_name}</div></div><div className="list-end"><span className={`badge ${p.quantity === 0 ? 'danger' : 'warning'}`}><i />{p.quantity === 0 ? 'Rupture' : `${p.quantity} / seuil ${p.low_stock_threshold}`}</span></div></li>)}
          {!data.low_stock_products.length && <li className="empty-li">Aucun produit sous le seuil d’alerte.</li>}</ul>
      </section>

      <section className="panel">
        <div className="panel-head"><div><h2>Derniers mouvements</h2></div><button className="secondary" onClick={onShowMovements}>Tout voir</button></div>
        <ul className="list">{data.recent_movements.map(m => <li key={m.id}><div><div className="product-name">{m.product_name}</div><div className="ref">{dateTime(m.created_at)}</div></div><div className="list-end"><span className={`badge move-${m.movement_type}`}>{MOVEMENT_LABELS[m.movement_type]}</span> <b>{m.movement_type === 'sale' ? '−' : '+'}{m.quantity}</b></div></li>)}
          {!data.recent_movements.length && <li className="empty-li">Aucun mouvement pour le moment.</li>}</ul>
      </section>
    </div>
  </>
}
