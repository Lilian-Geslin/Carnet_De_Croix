// Suggestions de noms déjà saisis (ascensions, lieux, ouvreurs, topos) pour les champs de saisie.
//
// Les noms sont chargés une seule fois par page depuis /api/noms (routes/api_infos.py) puis servis aux
// autres scripts via NOMS_PROMISE. Sur les pages sans champ de nom, rien n'est demandé au serveur.

// ─── SUGGESTIONS DE NOMS (datalist) ────────────────────────────────────────────
// Noms déjà saisis (ascensions + lieux), chargés une fois par page.
// Échappe les caractères spéciaux HTML d'une valeur avant de l'insérer dans du HTML (évite d'interpréter un nom comme du code).
const escHtml = v => String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
// Derniers noms connus ; sert aussi de valeur de repli si le serveur ne répond pas.
let NOMS_CACHE = { ascensions: [], lieux: [] };
// Promesse résolue avec les noms chargés ; les scripts font `NOMS_PROMISE.then(...)`.
const NOMS_PROMISE = (!document.getElementById('modalOverlay') && !document.getElementById('listRecherche'))
    ? Promise.resolve(NOMS_CACHE)          // pages sans champ de nom : rien à charger
    : fetch('/api/noms').then(r => r.ok ? r.json() : NOMS_CACHE).then(d => { NOMS_CACHE = d; return d; }).catch(() => NOMS_CACHE);
