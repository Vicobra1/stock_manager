import { useEffect, useRef, useState } from 'react'
import App from './App'
import Login from './Login'
import NoRole from './NoRole'
import ShopChooser from './ShopChooser'
import {
  clearShopSession, clearToken, getShopId, getShopToken, getToken, request, setForbiddenHandler,
  setNotFoundHandler, setShopRequiredHandler, setShopSession, setToken, setUnauthorizedHandler, type ShopSummary, type User,
} from './api'

/** Connexion en deux temps (décision D2) : la connexion au compte, puis le choix de la boutique de cet onglet. */
export default function AuthGate() {
  const [user, setUser] = useState<User | null>(null)
  const [shops, setShops] = useState<ShopSummary[] | null>(null)
  const [shop, setShop] = useState<ShopSummary | null>(null)
  const [checking, setChecking] = useState(() => getToken() !== null)
  const [notice, setNotice] = useState('')
  const started = useRef(false)

  async function chooseShop(target: ShopSummary) {
    clearShopSession()  // la demande du jeton de boutique se fait avec le jeton « compte »
    const data = await request('/auth/shop-token/', { method: 'POST', body: JSON.stringify({ shop: target.id }) })
    setShopSession(data.token, data.shop.id)
    setNotice('')
    setShop(data.shop)
  }

  /** Changer de boutique sans se déconnecter (sélecteur de l'en-tête) : l'application repart de zéro dans la nouvelle. */
  async function switchShop(target: ShopSummary) {
    try { await chooseShop(target) } catch (err) {
      setShop(null)  // retour au choix de la boutique, avec la raison
      setNotice(err instanceof Error ? err.message : 'Impossible d’ouvrir cette boutique.')
    }
  }

  /** Après un « introuvable » : si la boutique de l'onglet n'est plus dans ma liste, l'accès m'a été retiré. */
  function checkStillMember() {
    request('/auth/shops/').then((list: ShopSummary[]) => {
      setShops(list)
      setShop(current => {
        if (!current || list.some(s => s.id === current.id)) return current
        clearShopSession()
        setNotice(`Vous n’avez plus accès à la boutique « ${current.name} ».`)
        return null
      })
    }).catch(() => { /* 401 déjà géré, sinon on garde l'état */ })
  }

  /** Charge le compte et ses boutiques ; reprend la boutique de cet onglet, ou la choisit seule s'il n'y en a qu'une. */
  async function loadSession() {
    const [me, list]: [User, ShopSummary[]] = await Promise.all([request('/auth/me/'), request('/auth/shops/')])
    setUser(me)
    setShops(list)
    const current = list.find(s => s.id === getShopId())
    if (current && getShopToken()) setShop(current)
    else if (list.length === 1) await chooseShop(list[0])
    else { clearShopSession(); setShop(null) }
  }

  useEffect(() => {
    setUnauthorizedHandler(() => { setUser(null); setShop(null); setNotice('Votre session a expiré. Veuillez vous reconnecter.') })
    // Jeton de boutique expiré ou absent : retour au choix de la boutique.
    setShopRequiredHandler(() => { setShop(null); setNotice('Choisissez à nouveau votre boutique.') })
    // Un refus « pas les droits » peut venir d'un rôle modifié entre-temps : on relit ses boutiques et ses rôles.
    setForbiddenHandler(() => {
      request('/auth/shops/').then((list: ShopSummary[]) => {
        setShops(list)
        setShop(current => current && (list.find(s => s.id === current.id) ?? null))
      }).catch(() => { /* 401 déjà géré, sinon on garde l'état */ })
    })
    // Au rechargement de la page, le jeton « compte » conservé permet de restaurer la session.
    if (getToken() && !started.current) {
      started.current = true
      loadSession()
        .catch(() => setNotice(current => current || 'Impossible de vérifier votre session. Vérifiez que Django est démarré.'))
        .finally(() => setChecking(false))
    }
    // Un membre retiré de la boutique reçoit « introuvable » partout : on le détecte et on le ramène au choix.
    setNotFoundHandler(checkStillMember)
    return () => { setUnauthorizedHandler(null); setForbiddenHandler(null); setShopRequiredHandler(null); setNotFoundHandler(null) }
  }, [])

  async function onLogin(token: string) {
    clearShopSession()  // un ancien jeton de boutique de cet onglet ne doit pas être réutilisé
    setToken(token)
    setNotice('')
    setChecking(true)
    try { await loadSession() } catch (err) {
      setNotice(err instanceof Error ? err.message : 'Connexion impossible.')
    } finally { setChecking(false) }
  }

  async function logout() {
    // Même si l'appel échoue (API injoignable, jeton déjà invalide), l'utilisateur doit être déconnecté de cet écran.
    try { await request('/auth/logout/', { method: 'POST' }) } catch { /* rien de plus à faire */ }
    clearToken()
    setUser(null); setShops(null); setShop(null)
    setNotice('')
  }

  if (checking) return <main className="login-page"><p className="login-subtitle">Chargement…</p></main>
  if (!user || !shops) return <Login notice={notice} onLogin={token => void onLogin(token)} />
  if (shops.length === 0) return <NoRole user={user} onLogout={() => void logout()} />
  if (!shop) return <ShopChooser user={user} shops={shops} notice={notice} onChoose={chooseShop} onLogout={() => void logout()} />
  // L'application reçoit le rôle de la boutique en cours.
  // La clé fait repartir l'application de zéro à chaque changement de boutique (pages, données, formulaires).
  return <App key={shop.id} user={{ ...user, role: shop.role }} shop={shop} shops={shops}
    onSwitchShop={s => void switchShop(s)} onLogout={() => void logout()} />
}
