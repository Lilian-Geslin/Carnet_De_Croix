// Page Projets : recherche, filtres, tri et regroupement des cartes de projets, entièrement côté navigateur.
//
// Les cartes (.projet-card, rendues par pages/projets.html) portent des data-attributes (data-cot, data-essais, data-seances,
// data-last, data-site-id…). Ce script les filtre et les trie puis les range dans des groupes repliables.
// Les choix de tri / regroupement / discipline sont mémorisés dans localStorage.

// Démarre la page Projets ; sans effet ailleurs.
function initPageProjets() {
    // ═══ PAGE PROJETS : regroupement, tri et filtres ═══
    const projetsPool = document.getElementById('projetsCards');
    if (projetsPool) {
        const $ = id => document.getElementById(id);
        // Texte sans accents ni majuscules, pour comparer et trier sans tenir compte de la casse ni des accents.
        const norm = v => (v || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
        const cards = Array.from(projetsPool.querySelectorAll('.projet-card'));
        const root  = $('projetsGroups');
        const closed = new Set();      // groupes repliés (le temps de la visite)

        // Menu « site » : les sites qui ont au moins un projet
        const sites = new Map();
        cards.forEach(c => sites.set(c.dataset.siteId, c.dataset.siteLabel));
        [...sites.entries()].sort((a, b) => norm(a[1]).localeCompare(norm(b[1]))).forEach(([id, label]) => {
            const o = document.createElement('option'); o.value = id; o.textContent = label; $('pfSite').append(o);
        });

        // Mémorise tri / regroupement / discipline entre deux visites (facultatif : peut échouer sans gravité)
        // Clé localStorage des préférences (tri, regroupement, discipline).
        const KEY = 'carnet_projets_prefs';
        const saved = (() => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } })();
        ['pfSort', 'pfGroup', 'pfType'].forEach(id => {
            if (saved[id] && [...$(id).options].some(o => o.value === saved[id])) $(id).value = saved[id];
        });
        const savePrefs = () => {
            try { localStorage.setItem(KEY, JSON.stringify({ pfSort: $('pfSort').value, pfGroup: $('pfGroup').value, pfType: $('pfType').value })); } catch (e) {}
        };

        // Valeur numérique d'un data-attribute de carte (0 si absent).
        const num = (c, k) => parseInt(c.dataset[k]) || 0;
        const byName = (a, b) => norm(a.dataset.nom).localeCompare(norm(b.dataset.nom));
        // Fonctions de tri disponibles (choisies par le menu #pfSort) ; à égalité on trie par nom.
        const SORTS = {
            cot_desc:     (a, b) => num(b, 'cot') - num(a, 'cot') || byName(a, b),
            cot_asc:      (a, b) => num(a, 'cot') - num(b, 'cot') || byName(a, b),
            last_desc:    (a, b) => (b.dataset.last || '').localeCompare(a.dataset.last || '') || byName(a, b),
            last_asc:     (a, b) => (a.dataset.last || '').localeCompare(b.dataset.last || '') || byName(a, b),
            essais_desc:  (a, b) => num(b, 'essais') - num(a, 'essais') || byName(a, b),
            seances_desc: (a, b) => num(b, 'seances') - num(a, 'seances') || byName(a, b),
            nom:          byName,
        };

        // Applique recherche + filtres + tri, puis reconstruit l'affichage : une grille à plat, ou des groupes repliables par site / par secteur.
        // Met aussi à jour le compteur de projets et le message « aucun projet ».
        function render() {
            const q = norm($('pfSearch').value.trim());
            const type = $('pfType').value, site = $('pfSite').value;
            const cotMin = $('pfCot').value === '' ? null : parseInt($('pfCot').value);
            const mode = $('pfGroup').value;
            const list = cards.filter(c =>
                (!q || norm(c.dataset.search).includes(q)) &&
                (!type || c.dataset.type === type) &&
                (!site || c.dataset.siteId === site) &&
                (cotMin === null || num(c, 'cot') >= cotMin)
            ).sort(SORTS[$('pfSort').value] || SORTS.cot_desc);

            root.innerHTML = '';
            if (mode === 'none') {
                const grid = document.createElement('div');
                grid.className = 'projet-grid';
                list.forEach(c => grid.append(c));
                root.append(grid);
            } else {
                const groups = new Map();
                list.forEach(c => {
                    const key = mode === 'site' ? 'site' + c.dataset.siteId : 'sec' + c.dataset.secId;
                    if (!groups.has(key)) groups.set(key, {
                        key,
                        label: mode === 'site' ? c.dataset.siteLabel : c.dataset.secLabel,
                        sub:   mode === 'site' ? c.dataset.siteSub   : c.dataset.secSub,
                        cards: []
                    });
                    groups.get(key).cards.push(c);
                });
                [...groups.values()].sort((a, b) => norm(a.label).localeCompare(norm(b.label))).forEach(g => {
                    const det = document.createElement('details');
                    det.className = 'pg';
                    det.open = !closed.has(g.key);
                    det.addEventListener('toggle', () => { det.open ? closed.delete(g.key) : closed.add(g.key); });
                    const sum = document.createElement('summary');
                    sum.className = 'pg-head';
                    const title = document.createElement('span'); title.className = 'pg-title'; title.textContent = g.label;
                    const sub = document.createElement('span'); sub.className = 'pg-sub'; sub.textContent = g.sub || '';
                    const count = document.createElement('span'); count.className = 'pg-count'; count.textContent = g.cards.length;
                    sum.append(title, sub, count);
                    const grid = document.createElement('div');
                    grid.className = 'projet-grid';
                    g.cards.forEach(c => grid.append(c));
                    det.append(sum, grid);
                    root.append(det);
                });
            }
            $('pfCount').textContent = `${list.length} projet${list.length > 1 ? 's' : ''}` + (list.length !== cards.length ? ` sur ${cards.length}` : '');
            $('pfEmpty').style.display = list.length ? 'none' : 'block';
        }

        // La recherche réagit à chaque frappe ; les autres filtres à chaque changement (et sont alors mémorisés).
        ['pfSearch'].forEach(id => $(id).addEventListener('input', render));
        ['pfType', 'pfSite', 'pfCot', 'pfSort', 'pfGroup'].forEach(id => $(id).addEventListener('change', () => { savePrefs(); render(); }));
        render();
    }
}
