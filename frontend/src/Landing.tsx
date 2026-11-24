import { useState } from 'react'
import './Landing.css'
import { FREE_LIMITS, PRO_LIMITS } from './api'

const FEATURES = [
  { icon: '▦', title: 'Catalogue et stock', text: 'Produits, références, prix d’achat et de vente : les quantités se mettent à jour à chaque vente et à chaque entrée.' },
  { icon: '↘', title: 'Alertes de stock faible', text: 'Un seuil par produit : vous voyez tout de suite ce qu’il faut racheter.' },
  { icon: '⇅', title: 'Historique des mouvements', text: 'Chaque vente et chaque entrée est gardée, filtrable par produit, fournisseur, type et date.' },
  { icon: '◔', title: 'Tableau de bord', text: 'Ventes, valeur du stock et alertes en un coup d’œil, pour le gérant.' },
  { icon: '◎', title: 'Gérants et vendeurs', text: 'Le vendeur enregistre les ventes ; le gérant gère le catalogue, les prix et les fournisseurs.' },
  { icon: '⧉', title: 'Plusieurs boutiques', text: 'Un seul compte pour toutes vos boutiques, chacune avec ses données, bien séparées des autres.' },
]

const YEAR = new Date().getFullYear()

const FAQ = [
  { q: 'Mes données sont-elles visibles par les autres boutiques ?', a: 'Non. Chaque boutique a ses propres produits, fournisseurs et mouvements ; personne d’autre ne peut les lire, ni même savoir qu’ils existent.' },
  { q: 'Puis-je gérer plusieurs boutiques avec un seul compte ?', a: 'Oui. Un gérant peut créer d’autres boutiques et passer de l’une à l’autre sans se déconnecter, avec un rôle différent dans chacune si besoin.' },
  { q: 'Que voit un vendeur ?', a: 'Le catalogue, les quantités et les prix de vente, pour enregistrer les ventes. Les prix d’achat, le tableau de bord et la gestion des fournisseurs sont réservés au gérant.' },
  { q: 'Que se passe-t-il quand j’atteins la limite du plan gratuit ?', a: 'Rien n’est supprimé. Vous ne pouvez simplement plus ajouter de produit actif ou de membre ; désactivez un produit pour libérer une place, ou passez au plan Pro.' },
  { q: 'Et si je repasse du plan Pro au plan gratuit ?', a: 'Toutes vos données restent consultables. Seules les nouvelles créations au-delà des limites du plan gratuit sont refusées.' },
  { q: 'Comment passer au plan Pro ?', a: 'Depuis votre boutique, ouvrez le menu du plan et choisissez « Passer au plan Pro » : il vous indique comment contacter l’administrateur.' },
  { q: 'Puis-je l’utiliser sur mon téléphone ?', a: 'Oui, l’application s’adapte au téléphone et à la tablette : il suffit d’un navigateur.' },
]

/** Page publique (présentation du service), vue par les visiteurs non connectés. */
export default function Landing({ onLogin, onSignup }: { onLogin: () => void; onSignup: () => void }) {
  const [open, setOpen] = useState<number | null>(0)
  const fr = (n: number) => n.toLocaleString('fr-FR')

  return <div className="landing">
    <header className="landing-nav">
      <div className="brand"><span className="brand-mark">S</span><span>Stock<span className="brand-light">Boutique</span></span></div>
      <nav className="landing-links"><a href="#fonctionnalites">Fonctionnalités</a><a href="#tarifs">Tarifs</a><a href="#questions">Questions</a></nav>
      <div className="landing-actions"><button className="secondary" onClick={onLogin}>Se connecter</button><button className="primary" onClick={onSignup}>Créer ma boutique</button></div>
    </header>

    <main>
      <section className="landing-hero">
        <div className="landing-hero-text">
          <p className="eyebrow">GESTION DE STOCK POUR BOUTIQUES</p>
          <h1>Gérez le stock de vos boutiques, simplement.</h1>
          <p className="landing-lead">Produits, ventes, entrées de stock et alertes : StockBoutique suit tout pour vous, pour une ou plusieurs boutiques, depuis l’ordinateur ou le téléphone.</p>
          <div className="landing-cta"><button className="primary" onClick={onSignup}>Créer ma boutique gratuitement</button><button className="link-button" onClick={onLogin}>J’ai déjà un compte →</button></div>
          <p className="landing-note">Plan gratuit, sans carte bancaire. Votre boutique est prête en une minute.</p>
        </div>
        <div className="landing-preview" aria-hidden="true">
          <div className="preview-head"><span className="brand-mark">S</span><b>Ma boutique</b><span className="role-badge manager">Gérant</span></div>
          <div className="preview-stats"><div><p>Produits actifs</p><strong>18</strong></div><div><p>Stock faible</p><strong className="warn">3</strong></div><div><p>Ventes du jour</p><strong>42 500 FC</strong></div></div>
          <ul className="preview-rows">
            <li><span>Savon</span><span className="badge success"><i/> En stock</span></li>
            <li><span>Riz 25 kg</span><span className="badge warning"><i/> Stock faible</span></li>
            <li><span>Huile 5 L</span><span className="badge success"><i/> En stock</span></li>
          </ul>
        </div>
      </section>

      <section className="landing-section" id="fonctionnalites">
        <h2>Tout ce qu’il faut pour tenir votre stock</h2>
        <p className="landing-section-lead">Pensé pour les boutiques : simple à prendre en main, sans rien installer.</p>
        <div className="landing-features">{FEATURES.map(f => <article key={f.title}><span className="landing-icon">{f.icon}</span><h3>{f.title}</h3><p>{f.text}</p></article>)}</div>
      </section>

      <section className="landing-section" id="tarifs">
        <h2>Deux plans, sans surprise</h2>
        <p className="landing-section-lead">Commencez gratuitement ; passez au Pro quand votre boutique grandit.</p>
        <div className="landing-plans">
          <article className="plan">
            <h3>Gratuit</h3><p className="plan-price">0 FC</p><p className="plan-desc">Pour démarrer une petite boutique.</p>
            <ul><li>{fr(FREE_LIMITS.products)} produits actifs</li><li>{FREE_LIMITS.members} membres (vous compris)</li><li>Toutes les fonctionnalités</li><li>Plusieurs boutiques possibles</li></ul>
            <button className="secondary" onClick={onSignup}>Commencer gratuitement</button>
          </article>
          <article className="plan featured">
            <span className="plan-tag">Pour grandir</span>
            <h3>Pro</h3><p className="plan-price">Nous contacter</p><p className="plan-desc">Pour un grand catalogue et une équipe.</p>
            <ul><li>{fr(PRO_LIMITS.products)} produits actifs</li><li>{PRO_LIMITS.members} membres (vous compris)</li><li>Toutes les fonctionnalités</li><li>Passage depuis votre boutique, sans perte de données</li></ul>
            <button className="primary" onClick={onSignup}>Créer ma boutique</button>
            <p className="plan-foot">Créez d’abord votre boutique, puis demandez le passage au Pro depuis le menu du plan.</p>
          </article>
        </div>
      </section>

      <section className="landing-section" id="questions">
        <h2>Questions fréquentes</h2>
        <div className="landing-faq">{FAQ.map((item, i) => <div key={item.q} className={`faq-item ${open === i ? 'open' : ''}`}>
          <button aria-expanded={open === i} onClick={() => setOpen(open === i ? null : i)}><span>{item.q}</span><span className="plan-chevron">▾</span></button>
          {open === i && <p>{item.a}</p>}
        </div>)}</div>
      </section>

      <section className="landing-final">
        <h2>Prêt à mettre de l’ordre dans votre stock ?</h2>
        <button className="primary" onClick={onSignup}>Créer ma boutique gratuitement</button>
      </section>
    </main>

    <footer className="landing-footer"><span>© {YEAR} StockBoutique</span><button className="link-button" onClick={onLogin}>Se connecter</button></footer>
  </div>
}
