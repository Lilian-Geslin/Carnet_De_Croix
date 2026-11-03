// Listes de suggestions des champs de lieu (pays → sous-secteur) et ressenti de cotation hérité du lieu.
//
// Les champs de lieu des formulaires sont liés à des <datalist> (#listPays, #listDepartements…). Chaque fonction
// load*Options redescend la hiérarchie depuis le pays en appelant l'API /api/geo/... (voir routes/api_geo.py),
// retrouve l'identifiant du niveau saisi par son nom, puis remplit la liste du niveau suivant.
// Si un niveau saisi est inconnu (nouveau lieu), la fonction s'arrête : il n'y a rien à suggérer.
// Les noms viennent de la base : ils sont échappés (escHtml, défini dans noms.js) avant d'entrer dans le HTML.

// ─── GEO AUTOCOMPLETE ──────────────────────────────────────────────────────────

// Remplit la liste des pays déjà enregistrés.
async function loadPaysOptions() {
    const res  = await fetch('/api/geo/pays');
    const data = await res.json();
    const dl   = document.getElementById('listPays');
    if (dl) dl.innerHTML = data.map(p => `<option value="${escHtml(p.name)}">`).join('');
}

// Identifiant du pays de ce nom (null s'il n'existe pas encore).
async function fetchPaysId(name) {
    const res  = await fetch('/api/geo/pays');
    const data = await res.json();
    const p    = data.find(p => p.name === name);
    return p ? p.id : null;
}

// Remplit la liste des départements du pays saisi.
async function loadDepartementOptions(paysName) {
    const pid = await fetchPaysId(paysName);
    if (!pid) return;
    const res  = await fetch(`/api/geo/departements/${pid}`);
    const data = await res.json();
    const dl   = document.getElementById('listDepartements');
    if (dl) dl.innerHTML = data.map(r => `<option value="${escHtml(r.name)}">`).join('');
}

// Remplit la liste des localisations du département saisi (pays + département).
async function loadLocalisationOptions(paysName, depName) {
    const pid = await fetchPaysId(paysName);
    if (!pid) return;
    const r1   = await fetch(`/api/geo/departements/${pid}`);
    const deps = await r1.json();
    const dep  = deps.find(r => r.name === depName);
    if (!dep) return;
    const r2   = await fetch(`/api/geo/localisations/${dep.id}`);
    const data = await r2.json();
    const dl   = document.getElementById('listLocalisations');
    if (dl) dl.innerHTML = data.map(l => `<option value="${escHtml(l.name)}">`).join('');
}

// Remplit la liste des sites de la localisation saisie.
async function loadSiteOptions(paysName, depName, localisationName) {
    const pid = await fetchPaysId(paysName);
    if (!pid) return;
    const r1   = await fetch(`/api/geo/departements/${pid}`);
    const deps = await r1.json();
    const dep  = deps.find(r => r.name === depName);
    if (!dep) return;
    const r2   = await fetch(`/api/geo/localisations/${dep.id}`);
    const localisations = await r2.json();
    const loc  = localisations.find(l => l.name === localisationName);
    if (!loc) return;
    const r3   = await fetch(`/api/geo/sites/${loc.id}`);
    const data = await r3.json();
    const dl   = document.getElementById('listSites');
    if (dl) dl.innerHTML = data.map(s => `<option value="${escHtml(s.name)}">`).join('');
}

// Remplit la liste des secteurs du site saisi.
async function loadSecteurOptions(paysName, depName, localisationName, siteName) {
    const pid = await fetchPaysId(paysName);
    if (!pid) return;
    const r1   = await fetch(`/api/geo/departements/${pid}`);
    const deps = await r1.json();
    const dep  = deps.find(r => r.name === depName);
    if (!dep) return;
    const r2   = await fetch(`/api/geo/localisations/${dep.id}`);
    const localisations = await r2.json();
    const loc  = localisations.find(l => l.name === localisationName);
    if (!loc) return;
    const r3    = await fetch(`/api/geo/sites/${loc.id}`);
    const sites = await r3.json();
    const site  = sites.find(s => s.name === siteName);
    if (!site) return;
    const r4   = await fetch(`/api/geo/secteurs/${site.id}`);
    const data = await r4.json();
    const dl   = document.getElementById('listSecteurs');
    if (dl) dl.innerHTML = data.map(s => `<option value="${escHtml(s.name)}">`).join('');
}

// Remplit la liste des sous-secteurs du secteur saisi.
async function loadSousSecteurOptions(paysName, depName, localisationName, siteName, secteurName) {
    const pid = await fetchPaysId(paysName);
    if (!pid) return;
    const r1   = await fetch(`/api/geo/departements/${pid}`);
    const deps = await r1.json();
    const dep  = deps.find(r => r.name === depName);
    if (!dep) return;
    const r2   = await fetch(`/api/geo/localisations/${dep.id}`);
    const localisations = await r2.json();
    const loc  = localisations.find(l => l.name === localisationName);
    if (!loc) return;
    const r3    = await fetch(`/api/geo/sites/${loc.id}`);
    const sites = await r3.json();
    const site  = sites.find(s => s.name === siteName);
    if (!site) return;
    const r4       = await fetch(`/api/geo/secteurs/${site.id}`);
    const secteurs = await r4.json();
    const sec      = secteurs.find(s => s.name === secteurName);
    if (!sec) return;
    const r5   = await fetch(`/api/geo/sous_secteurs/${sec.id}`);
    const data = await r5.json();
    const dl   = document.getElementById('listSousSecteurs');
    if (dl) dl.innerHTML = data.map(ss => `<option value="${escHtml(ss.name)}">`).join('');
}

// Retrouve le ressenti déjà enregistré pour le secteur / sous-secteur saisi
// (sous-secteur prioritaire s'il est renseigné). Renvoie '' si inconnu.
async function lookupRessenti(paysName, depName, localisationName, siteName, secteurName, sousSecteurName) {
    if (!paysName || !depName || !localisationName || !siteName || !secteurName) return '';
    const pid = await fetchPaysId(paysName);
    if (!pid) return '';
    const deps = await (await fetch(`/api/geo/departements/${pid}`)).json();
    const dep  = deps.find(r => r.name === depName);
    if (!dep) return '';
    const locs = await (await fetch(`/api/geo/localisations/${dep.id}`)).json();
    const loc  = locs.find(l => l.name === localisationName);
    if (!loc) return '';
    const sites = await (await fetch(`/api/geo/sites/${loc.id}`)).json();
    const site  = sites.find(s => s.name === siteName);
    if (!site) return '';
    const secteurs = await (await fetch(`/api/geo/secteurs/${site.id}`)).json();
    const sec      = secteurs.find(s => s.name === secteurName);
    if (!sec) return '';
    if (sousSecteurName) {
        const sss = await (await fetch(`/api/geo/sous_secteurs/${sec.id}`)).json();
        const ss  = sss.find(s => s.name === sousSecteurName);
        return ss ? (ss.ressenti || '') : '';
    }
    return sec.ressenti || '';
}

// Numéro de la dernière demande de ressenti : permet d'ignorer les réponses arrivées en retard.
// Remet à jour le menu « ressenti de cotation » (#inputRessenti) quand le lieu saisi change : on pré-remplit
// avec le ressenti déjà enregistré pour ce secteur / sous-secteur.
let _ressentiToken = 0;
async function refreshRessentiFromGeo() {
    const sel = document.getElementById('inputRessenti');
    if (!sel) return;
    const val = id => (document.getElementById(id)?.value || '').trim();
    const token = ++_ressentiToken;
    let r = '';
    try {
        r = await lookupRessenti(val('inputPays'), val('inputDepartement'), val('inputLocalisation'),
                                 val('inputSite'), val('inputSecteur'), val('inputSousSecteur'));
    } catch (e) { r = ''; }
    if (token !== _ressentiToken) return;   // une saisie plus récente a pris le relais
    sel.value = r;
}
