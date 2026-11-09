const API = '/api'
const TOKEN_KEY = 'stock-boutique-token'

export type User = { id: number; username: string; first_name: string; last_name: string; is_staff: boolean }

export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}
export function setToken(token: string) {
  try { localStorage.setItem(TOKEN_KEY, token) } catch { /* stockage indisponible : la session durera jusqu'au rechargement */ }
  memoryToken = token
}
export function clearToken() {
  try { localStorage.removeItem(TOKEN_KEY) } catch { /* rien à effacer */ }
  memoryToken = null
}

// Copie en mémoire, pour que les appels fonctionnent même si le navigateur bloque localStorage.
let memoryToken: string | null = null

let onUnauthorized: (() => void) | null = null
/** Enregistre ce qu'il faut faire quand l'API refuse le jeton (session expirée). */
export function setUnauthorizedHandler(handler: (() => void) | null) { onUnauthorized = handler }

export async function request(path: string, init?: RequestInit) {
  const token = getToken() ?? memoryToken
  const headers = { 'Content-Type': 'application/json', ...(token ? { Authorization: `Token ${token}` } : {}), ...init?.headers }
  const response = await fetch(`${API}${path}`, { ...init, headers })
  const data = await response.json().catch(() => ({}))
  if (response.status === 401) {
    clearToken()
    onUnauthorized?.()
    throw new Error('Votre session a expiré. Veuillez vous reconnecter.')
  }
  if (!response.ok) throw new Error(data.detail || Object.values(data).flat().join(' ') || 'Une erreur est survenue.')
  return data
}

export const money = (v: string | number) => `${Number(v).toLocaleString('fr-FR', { maximumFractionDigits: 0 })} FC`

export const MOVEMENT_LABELS: Record<string, string> = { initial: 'Stock initial', entry: 'Entrée', sale: 'Vente', adjustment: 'Ajustement' }

export type Movement = { id: number; product: number; product_name: string; product_reference: string; movement_type: string; quantity: number; unit_price: string | null; note: string; created_at: string }
