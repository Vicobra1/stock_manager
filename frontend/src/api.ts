const API = '/api'
// Décision F-1 (option N3) : le jeton « compte » est partagé entre les onglets (localStorage, on reste connecté) ;
// le jeton de boutique est propre à chaque onglet (sessionStorage) : deux onglets peuvent travailler dans deux
// boutiques différentes sans que l'un fasse basculer l'autre.
const ACCOUNT_TOKEN_KEY = 'stock-boutique-token'
const SHOP_TOKEN_KEY = 'stock-boutique-shop-token'
const SHOP_ID_KEY = 'stock-boutique-shop-id'

export type Role = 'manager' | 'seller'
export const ROLE_LABELS: Record<Role, string> = { manager: 'Gérant', seller: 'Vendeur' }
export type User = { id: number; username: string; first_name: string; last_name: string; is_staff: boolean; role: Role | null }
export type Plan = 'free' | 'pro'
export const PLAN_LABELS: Record<Plan, string> = { free: 'Gratuit', pro: 'Pro' }
export type ShopSummary = { id: number; name: string; plan: Plan; role: Role }

// Copies en mémoire, pour que les appels fonctionnent même si le navigateur bloque le stockage.
const memory: Record<string, string | null> = {}
function read(storage: () => Storage, key: string) {
  try { return storage().getItem(key) ?? memory[key] ?? null } catch { return memory[key] ?? null }
}
function write(storage: () => Storage, key: string, value: string | null) {
  memory[key] = value
  try { if (value === null) storage().removeItem(key); else storage().setItem(key, value) } catch { /* stockage indisponible */ }
}
const local = () => localStorage
const session = () => sessionStorage

/** Jeton « compte » (connexion), partagé entre les onglets. */
export function getToken() { return read(local, ACCOUNT_TOKEN_KEY) }
export function setToken(token: string) { write(local, ACCOUNT_TOKEN_KEY, token) }

/** Jeton de la boutique choisie dans CET onglet. */
export function getShopToken() { return read(session, SHOP_TOKEN_KEY) }
export function getShopId() { const id = read(session, SHOP_ID_KEY); return id ? Number(id) : null }
export function setShopSession(token: string, shopId: number) {
  write(session, SHOP_TOKEN_KEY, token)
  write(session, SHOP_ID_KEY, String(shopId))
}
export function clearShopSession() {
  write(session, SHOP_TOKEN_KEY, null)
  write(session, SHOP_ID_KEY, null)
}

/** Déconnexion : tout est effacé dans le navigateur (le serveur, lui, supprime tous les jetons). */
export function clearToken() {
  write(local, ACCOUNT_TOKEN_KEY, null)
  clearShopSession()
}

let onUnauthorized: (() => void) | null = null
/** Enregistre ce qu'il faut faire quand l'API refuse le jeton (session expirée). */
export function setUnauthorizedHandler(handler: (() => void) | null) { onUnauthorized = handler }

let onForbidden: (() => void) | null = null
/** Enregistre ce qu'il faut faire quand l'API refuse une action faute de droits (rôle retiré en cours de session). */
export function setForbiddenHandler(handler: (() => void) | null) { onForbidden = handler }

let onNotFound: (() => void) | null = null
/** Enregistre ce qu'il faut faire après un « introuvable » : peut-être l'accès à la boutique a-t-il été retiré. */
export function setNotFoundHandler(handler: (() => void) | null) { onNotFound = handler }

let onShopRequired: (() => void) | null = null
/** Enregistre ce qu'il faut faire quand l'API demande de choisir une boutique (jeton de boutique absent ou expiré). */
export function setShopRequiredHandler(handler: (() => void) | null) { onShopRequired = handler }

const CHOOSE_SHOP = "Choisissez d'abord une boutique."

export async function request(path: string, init?: RequestInit) {
  // Le jeton de boutique s'il y en a un (API métier) ; sinon le jeton « compte » (choix de la boutique).
  const token = getShopToken() ?? getToken()
  const headers = { 'Content-Type': 'application/json', ...(token ? { Authorization: `Token ${token}` } : {}), ...init?.headers }
  const response = await fetch(`${API}${path}`, { ...init, headers })
  const data = await response.json().catch(() => ({}))
  if (response.status === 401) {
    clearToken()
    onUnauthorized?.()
    throw new Error('Votre session a expiré. Veuillez vous reconnecter.')
  }
  if (response.status === 403 && data.detail === CHOOSE_SHOP) {
    clearShopSession()
    onShopRequired?.()
  } else if (response.status === 403 && data.code !== 'quota_exceeded') onForbidden?.()
  if (response.status === 404) onNotFound?.()
  if (!response.ok) throw new Error(data.detail || Object.values(data).flat().join(' ') || 'Une erreur est survenue.')
  return data
}

export const money = (v: string | number) => `${Number(v).toLocaleString('fr-FR', { maximumFractionDigits: 0 })} FC`

export const MOVEMENT_LABELS: Record<string, string> = { initial: 'Stock initial', entry: 'Entrée', sale: 'Vente', adjustment: 'Ajustement' }

export type Movement = { id: number; product: number; product_name: string; product_reference: string; movement_type: string; quantity: number; unit_price: string | null; note: string; created_at: string }
