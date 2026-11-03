// Page Tick List : liste d'envies à cocher, avec filtres, tri, regroupement et vue « Paliers ».
//
// Les envies viennent du serveur sous forme de tableau JSON (variable ENVIES, fournie par pages/ticklist.html, produite par
// services/ticklist.py), ainsi que ENVIE_CATS (Performance, Beauté, Majeure). Tout le rendu est fait ici côté navigateur.
// Les actions passent par les autres scripts : la case à cocher ouvre « Marquer comme grimpé » (quick-modals.js), « ⚡ Projet »
// ouvre « Passer en projet », ✕ supprime l'envie (repetition.js). API propre à ce fichier : POST /api/ascension/<id>/categorie.

// Démarre la page Tick List ; sans effet ailleurs.
function initPageTicklist() {
    // ═══ PAGE TICK LIST : liste à cocher (regroupée par site / catégorie) et vue « Paliers » ═══
    const tlBody = document.getElementById('tlBody');
    if (tlBody && typeof ENVIES !== 'undefined') {
        const $ = id => document.getElementById(id);
        // Petit constructeur d'élément : h('div', 'classe', 'texte') (le texte est inséré comme texte, jamais comme HTML).
        const h = (tag, cls, txt) => { const n = document.createElement(tag); if (cls) n.className = cls; if (txt != null) n.textContent = txt; return n; };
        // Ordre d'affichage des catégories ; '' = sans catégorie.
        const CAT_ORDER = ['performance', 'beaute', 'majeure', ''];
        const catLabel = k => k ? (ENVIE_CATS[k] || k) : 'Sans catégorie';
        const plur = (n, w) => `${n} ${w}${n > 1 ? 's' : ''}`;
        const norm = v => (v || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
        // Clé localStorage des préférences d'affichage (vue, regroupement, tri, discipline, catégorie).
        const KEY = 'ticklist_prefs';
        const saved = (() => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } })();
        // État courant des filtres ; initialisé avec les préférences mémorisées. `q` = texte de recherche (non mémorisé).
        const state = { view: saved.view || 'liste', group: saved.group || 'site', sort: saved.sort || 'cot_desc', type: saved.type || '', cat: saved.cat === undefined ? 'all' : saved.cat, q: '' };
        const save = () => { try { localStorage.setItem(KEY, JSON.stringify({ view: state.view, group: state.group, sort: state.sort, type: state.type, cat: state.cat })); } catch (e) {} };

        // Menu « discipline » : seulement les disciplines qui ont au moins une envie.
        // Disciplines présentes dans la tick list
        const typeLabels = {}; ENVIES.forEach(e => { typeLabels[e.type] = e.type_label; });
        Object.entries(typeLabels).forEach(([k, v]) => { const o = document.createElement('option'); o.value = k; o.textContent = v; $('tlType').append(o); });
        if (!typeLabels[state.type]) state.type = '';
        $('tlType').value = state.type; $('tlGroup').value = state.group; $('tlSort').value = state.sort;

        // ── En-tête ──
        // Bandeau de résumé : nombre d'envies, répartition par discipline et par catégorie (cliquable = filtre),
        // et repère de niveau (« au-dessus de ton max actuel » = plus dure que ce qui a été réalisé dans la même discipline).
        function renderHead() {
            const head = $('tlHead'); head.innerHTML = '';
            const total = ENVIES.length;
            const big = h('div', 'tl-total'); big.append(h('strong', '', String(total)), h('span', '', total > 1 ? 'envies à cocher' : 'envie à cocher'));
            const parts = h('div', 'tl-head-parts');

            const byType = {}; ENVIES.forEach(e => { byType[e.type] = (byType[e.type] || 0) + 1; });
            const l1 = h('div', 'tl-head-line'); l1.append(h('span', 'tl-head-label', 'Disciplines'));
            Object.entries(byType).sort((a, b) => b[1] - a[1]).forEach(([k, n]) => l1.append(h('span', 'tl-head-chip', `${typeLabels[k]} · ${n}`)));

            const l2 = h('div', 'tl-head-line'); l2.append(h('span', 'tl-head-label', 'Catégories'));
            CAT_ORDER.forEach(k => {
                const n = ENVIES.filter(e => e.categorie === k).length;
                if (!n) return;
                const b = h('button', 'tl-head-chip tl-head-btn tl-c-' + (k || 'none'), `${catLabel(k)} · ${n}`);
                b.type = 'button'; b.title = 'Filtrer sur cette catégorie';
                b.addEventListener('click', () => { state.cat = k; save(); render(); });
                l2.append(b);
            });

            const above = ENVIES.filter(e => e.above_max === true).length;
            const within = ENVIES.filter(e => e.above_max === false).length;
            const l3 = h('div', 'tl-head-line'); l3.append(h('span', 'tl-head-label', 'Niveau'));
            if (above + within) {
                l3.append(h('span', 'tl-head-chip', `▲ ${plur(above, 'envie')} au-dessus de ton max actuel`));
                l3.append(h('span', 'tl-head-chip', `${within} à ton niveau ou en dessous`));
            } else l3.append(h('span', 'tl-head-chip', 'Pas encore de repère : aucune ascension réalisée dans ces disciplines'));
            parts.append(l1, l2, l3);
            head.append(big, parts);
        }

        // ── Filtres / tri ──
        // Pastilles de filtre par catégorie (« Toutes » + chaque catégorie).
        function renderCatChips() {
            const box = $('tlCats'); box.innerHTML = '';
            [['all', 'Toutes'], ...CAT_ORDER.map(k => [k, catLabel(k)])].forEach(([k, label]) => {
                const b = h('button', 'tl-cat-chip' + (state.cat === k ? ' active' : ''), label);
                b.type = 'button'; b.setAttribute('aria-pressed', state.cat === k ? 'true' : 'false');
                b.addEventListener('click', () => { state.cat = k; save(); render(); });
                box.append(b);
            });
        }
        // Position d'une catégorie dans CAT_ORDER.
        const catIdx = k => CAT_ORDER.indexOf(k || '');
        // Rang de cotation d'une envie, ou null si elle n'a pas de cotation.
        const rankKey = e => (e.rank >= 0 ? e.rank : null);
        function byNom(a, b) { return norm(a.nom).localeCompare(norm(b.nom)); }
        // Fonction de tri selon le choix : par nom, ou par cotation croissante / décroissante (sans cotation toujours à la fin).
        function sorter() {
            if (state.sort === 'nom') return byNom;
            const dir = state.sort === 'cot_asc' ? 1 : -1;
            return (a, b) => {
                const ra = rankKey(a), rb = rankKey(b);
                if (ra === null && rb !== null) return 1;        // sans cotation : toujours en dernier
                if (rb === null && ra !== null) return -1;
                if (ra !== rb) return (ra - rb) * dir;
                return byNom(a, b);
            };
        }
        // Envies qui passent les filtres : discipline, catégorie et recherche (nom, lieu, chemin, commentaire).
        function filtered() {
            const q = norm(state.q.trim());
            return ENVIES.filter(e =>
                (!state.type || e.type === state.type) &&
                (state.cat === 'all' || e.categorie === state.cat) &&
                (!q || norm([e.nom, e.site, e.secteur, e.sous_secteur, e.chemin, e.commentaire].join(' ')).includes(q))
            );
        }

        // ── Une ligne de la liste à cocher ──
        // Construit la ligne d'une envie : case à cocher, nom, départ, cotation, ▲ si au-dessus du niveau,
        // lieu, type, hauteur, commentaire, menu de catégorie, bouton « Projet » et suppression.
        //   opts.compact : version resserrée (vue Paliers) ;  opts.where : quel morceau du lieu afficher.
        function itemEl(e, opts) {
            const row = h('div', 'tl-item' + (opts.compact ? ' tl-compact' : ''));
            row.dataset.id = e.id;
            const chk = h('button', 'tl-check btn-log');
            chk.type = 'button'; chk.dataset.ascId = e.id; chk.dataset.type = e.type;
            chk.title = 'Cocher : marquer comme grimpé'; chk.setAttribute('role', 'checkbox'); chk.setAttribute('aria-checked', 'false');
            chk.setAttribute('aria-label', `Marquer « ${e.nom} » comme grimpé`);
            chk.append(h('span', 'tl-tick', '✓'));

            const main = h('div', 'tl-main');
            const l1 = h('div', 'tl-line1');
            l1.append(h('span', 'tl-nom', e.nom));
            if (e.depart) l1.append(h('span', 'tl-depart', e.depart));
            if (e.cotation) l1.append(h('span', 'tl-cot', e.cotation));
            if (e.above_max === true) { const up = h('span', 'tl-up', '▲'); up.title = 'Au-dessus de ton max actuel dans cette discipline'; l1.append(up); }
            main.append(l1);

            const bits = [];
            if (opts.where === 'site') bits.push(e.site + (e.secteur ? ' › ' + e.secteur : '') + (e.sous_secteur ? ' › ' + e.sous_secteur : ''));
            else if (opts.where === 'inside') bits.push([e.secteur, e.sous_secteur].filter(Boolean).join(' › '));
            if (!opts.compact || true) bits.push(e.type_label);
            if (e.hauteur) bits.push(e.hauteur + ' m');
            if (e.nb_longueurs) bits.push(e.nb_longueurs + ' longueurs');
            const l2 = h('div', 'tl-line2', bits.filter(Boolean).join(' · '));
            main.append(l2);
            if (e.commentaire) main.append(h('div', 'tl-comment', e.commentaire));

            const side = h('div', 'tl-side');
            const sel = h('select', 'tl-cat tl-c-' + (e.categorie || 'none'));
            sel.title = 'Catégorie de cette envie'; sel.setAttribute('aria-label', 'Catégorie');
            [['', 'Sans catégorie'], ...Object.entries(ENVIE_CATS)].forEach(([k, v]) => { const o = document.createElement('option'); o.value = k; o.textContent = v; sel.append(o); });
            sel.value = e.categorie || '';
            // Changer la catégorie enregistre tout de suite sur le serveur ; en cas d'erreur on remet l'ancienne valeur.
            sel.addEventListener('change', async () => {
                const res = await fetch(`/api/ascension/${e.id}/categorie`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ categorie: sel.value }) });
                const data = await res.json();
                if (data.success) { e.categorie = sel.value; renderHead(); render(); }
                else { alert(data.error || 'Erreur.'); sel.value = e.categorie || ''; }
            });
            const pj = h('button', 'btn-to-projet btn-secondary-sm', '⚡ Projet');
            pj.type = 'button'; pj.dataset.ascId = e.id; pj.dataset.nom = e.nom; pj.dataset.type = e.type; pj.title = "Je l'ai essayée sans la finir : la passer en projet";
            const del = h('button', 'btn-icon btn-del', '✕');
            del.type = 'button'; del.dataset.ascId = e.id; del.title = 'Supprimer de la tick list';
            side.append(sel, pj, del);
            row.append(chk, main, side);
            return row;
        }

        // ── Vue « Liste » : regroupée par site, par catégorie, ou à plat ──
        // Vue « Liste » : regroupée par site, par catégorie ou à plat ; à l'intérieur d'un groupe, tri choisi.
        function renderListe(items) {
            const sort = sorter();
            let groups;
            if (state.group === 'site') {
                const m = new Map();
                items.forEach(e => { const k = e.site_id + '|' + e.site; if (!m.has(k)) m.set(k, { title: e.site, sub: e.chemin.split(' › ').slice(0, -1).join(' › '), items: [] }); m.get(k).items.push(e); });
                groups = [...m.values()].sort((a, b) => norm(a.title).localeCompare(norm(b.title)));
            } else if (state.group === 'categorie') {
                groups = CAT_ORDER.map(k => ({ title: catLabel(k), cls: 'tl-c-' + (k || 'none'), items: items.filter(e => (e.categorie || '') === k) })).filter(g => g.items.length);
            } else groups = [{ title: '', items }];
            groups.forEach(g => {
                const sec = h('section', 'tl-group');
                if (g.title) {
                    const hd = h('div', 'tl-group-head ' + (g.cls || ''));
                    hd.append(h('h3', '', g.title), h('span', 'tl-group-count', plur(g.items.length, 'envie')));
                    if (g.sub) hd.append(h('span', 'tl-group-sub', g.sub));
                    sec.append(hd);
                }
                const list = h('div', 'tl-list');
                g.items.sort(sort).forEach(e => list.append(itemEl(e, { where: state.group === 'site' ? 'inside' : 'site' })));
                sec.append(list); tlBody.append(sec);
            });
        }

        // ── Vue « Paliers » : une colonne par palier de cotation ──
        // Vue « Paliers » : une colonne par palier de cotation (palier fourni par le serveur : key, label, order),
        // triée par catégorie puis par nom dans chaque colonne.
        function renderPaliers(items) {
            const cols = new Map();
            items.forEach(e => { const p = e.palier; if (!cols.has(p.key)) cols.set(p.key, { ...p, items: [] }); cols.get(p.key).items.push(e); });
            const wrap = h('div', 'tl-paliers');
            [...cols.values()].sort((a, b) => a.order - b.order).forEach(c => {
                const col = h('section', 'tl-col');
                const hd = h('div', 'tl-col-head');
                hd.append(h('span', 'tl-col-label', c.label), h('span', 'tl-col-count', String(c.items.length)));
                col.append(hd);
                c.items.sort((a, b) => catIdx(a.categorie) - catIdx(b.categorie) || byNom(a, b))
                       .forEach(e => col.append(itemEl(e, { compact: true, where: 'site' })));
                wrap.append(col);
            });
            tlBody.append(wrap);
        }

        // Redessine tout selon l'état : vues actives, filtres, compteur « x / n » et message « aucune envie ».
        function render() {
            // Branchement des commandes : changement de vue, recherche, discipline, regroupement, tri (les choix sont mémorisés).
            document.querySelectorAll('.tl-views button').forEach(b => b.classList.toggle('active', b.dataset.view === state.view));
            $('tlGroup').disabled = state.view === 'paliers';
            $('tlSort').disabled = state.view === 'paliers';
            renderCatChips();
            const items = filtered();
            tlBody.innerHTML = '';
            $('tlEmpty').style.display = items.length ? 'none' : '';
            $('tlCount').textContent = items.length === ENVIES.length ? '' : `${items.length} / ${ENVIES.length}`;
            if (!items.length) return;
            if (state.view === 'paliers') renderPaliers(items); else renderListe(items);
        }

        document.querySelectorAll('.tl-views button').forEach(b => b.addEventListener('click', () => { state.view = b.dataset.view; save(); render(); }));
        $('tlSearch').addEventListener('input', () => { state.q = $('tlSearch').value; render(); });
        $('tlType').addEventListener('change', () => { state.type = $('tlType').value; save(); render(); });
        $('tlGroup').addEventListener('change', () => { state.group = $('tlGroup').value; save(); render(); });
        $('tlSort').addEventListener('change', () => { state.sort = $('tlSort').value; save(); render(); });
        renderHead(); render();
    }
}
