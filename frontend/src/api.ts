const API = '/api'

export async function request(path: string, init?: RequestInit) {
  const response = await fetch(`${API}${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || Object.values(data).flat().join(' ') || 'Une erreur est survenue.')
  return data
}

export const money = (v: string | number) => `${Number(v).toLocaleString('fr-FR', { maximumFractionDigits: 0 })} FC`

export const MOVEMENT_LABELS: Record<string, string> = { initial: 'Stock initial', entry: 'Entrée', sale: 'Vente', adjustment: 'Ajustement' }

export type Movement = { id: number; product: number; product_name: string; product_reference: string; movement_type: string; quantity: number; unit_price: string | null; note: string; created_at: string }
