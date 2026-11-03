// Fenêtre « Plus d'informations » d'une ascension (carnet, recherche).
// Deux modes : fiche en lecture (par défaut) et formulaire d'édition.
// Contenu : ouverture/rééquipements, topo (papier ou PDF ; le PDF se choisit dans la bibliothèque de topos du site ou s'ajoute une seule fois), séances liées, et
// pastilles par catégorie (type de grimpe, roche, fixations, coinceurs).
// API : GET/PUT /api/ascension/<id>/infos ; GET/POST /api/topos (bibliothèque de topos PDF) ; GET/POST/DELETE /api/options.

function initInfosModal() {
    // ═══ « PLUS D'INFORMATIONS » (carnet, recherche) : séances, topo, équipement, roche, type de grimpe, ouverture ═══
    const infoOverlay = document.getElementById('infoModalOverlay');
    if (infoOverlay) {
        // Raccourci d'accès par identifiant.
        const $ = id => document.getElementById(id);
        // Accord du pluriel : « 1 essai », « 3 essais ».
        const plur = (n, w) => `${n} ${w}${n > 1 ? 's' : ''}`;
        // Comparaison de deux noms sans tenir compte de la casse.
        const same = (a, b) => a.toLowerCase() === b.toLowerCase();
        // Textes affichés par chaque barre déroulante, selon la catégorie.
        const COMBO_TXT = {
            grimpe:   { ph: 'Choisir ou ajouter un type de grimpe…', none: 'Aucun type de grimpe choisi',   new: 'un nouveau type de grimpe' },
            roche:    { ph: 'Choisir ou ajouter un type de roche…',  none: 'Aucun type de roche choisi',    new: 'un nouveau type de roche' },
            fixation: { ph: 'Choisir ou ajouter une fixation…',      none: 'Aucune fixation choisie',       new: 'une nouvelle fixation' },
            coinceur: { ph: 'Choisir ou ajouter un coinceur…',       none: 'Aucun coinceur choisi',         new: 'un nouveau type de coinceur' },
        };
        // État de la fenêtre : ascension ouverte, propositions, choix en cours, modifications non enregistrées.
        const st = { ascId: null, options: {}, tags: {}, dirty: false };

        // Message d'état (succès ou erreur) sous le formulaire ; le succès disparaît seul.
        const flash = (msg, isError) => {
            const f = $('infoFlash');
            f.textContent = msg || ''; f.classList.toggle('error', !!isError);
            if (msg && !isError) setTimeout(() => { if (f.textContent === msg) f.textContent = ''; }, 2500);
        };
        // Remplit une liste de suggestions (datalist) avec les noms déjà utilisés.
        const fillDatalist = (id, arr) => { $(id).innerHTML = (arr || []).map(n => `<option value="${escHtml(n)}">`).join(''); };

        // Lien de topo : on n'ouvre que du http(s) (même règle que le serveur)
        const normLink = v => {
            v = (v || '').trim();
            if (!v || /\s/.test(v)) return '';
            if (/^https?:\/\//i.test(v)) return v;
            if (/^[a-zA-Z][a-zA-Z0-9+.-]*:(?!\d)/.test(v)) return '';
            return 'https://' + v;
        };
        // Affiche ou masque le bouton « ouvrir » selon que le lien saisi est valide.
        const refreshLink = () => {
            const open = $('infoTopoOpen'), l = normLink($('infoTopoLien').value);
            open.style.display = l ? '' : 'none';
            if (l) open.href = l; else open.removeAttribute('href');
        };
        // Type de topo coché : 'papier', 'pdf' ou '' (aucun).
        const topoType = () => (document.querySelector('input[name=infoTopoType]:checked') || {}).value || '';
        // N'affiche que les champs correspondant au type de topo choisi.
        const showTopoFields = () => {
            const t = topoType();
            $('topoPapier').style.display = t === 'papier' ? '' : 'none';
            $('topoPdf').style.display    = t === 'pdf' ? '' : 'none';
        };

        // ── Topo PDF enregistré dans le site : choisi dans la bibliothèque (st.topos), envoyé une seule fois ──
        const PDF_MAX = 20 * 1024 * 1024;   // même limite que le serveur (constants.TOPO_PDF_MAX_BYTES)
        // Taille lisible : « 340 Ko », « 1,2 Mo ».
        const fmtSize = n => n >= 1048576 ? (n / 1048576).toFixed(1).replace('.', ',') + ' Mo' : Math.max(1, Math.round(n / 1024)) + ' Ko';
        // Adresse d'un topo de la bibliothèque (ouvert dans le lecteur du navigateur).
        const pdfUrl = id => `/api/topos/${id}/pdf`;
        // Remplit la liste déroulante : « Aucun », puis les topos de ce site, puis les autres ; `selectedId` est présélectionné.
        const renderTopoSelect = selectedId => {
            const sel = $('infoTopoId');
            sel.innerHTML = '';
            const opt = (t) => { const o = document.createElement('option'); o.value = t.id; o.textContent = `${t.nom} (${fmtSize(t.taille)})`; return o; };
            const none = document.createElement('option'); none.value = ''; none.textContent = '— Aucun PDF choisi —'; sel.append(none);
            const groups = [['Topos de ce site', (st.topos || []).filter(t => t.local)], ['Autres topos enregistrés', (st.topos || []).filter(t => !t.local)]];
            groups.forEach(([label, list]) => {
                if (!list.length) return;
                const g = document.createElement('optgroup'); g.label = label;
                list.forEach(t => g.append(opt(t)));
                sel.append(g);
            });
            sel.value = selectedId ? String(selectedId) : '';
            refreshTopoOpen();
        };
        // Identifiant du topo choisi (nombre) ou null.
        const selectedTopoId = () => { const v = $('infoTopoId').value; return v ? Number(v) : null; };
        // Affiche « Ouvrir » seulement si un topo est choisi.
        function refreshTopoOpen() {
            const id = selectedTopoId(), open = $('topoFichierOpen');
            open.style.display = id ? '' : 'none';
            if (id) open.href = pdfUrl(id); else open.removeAttribute('href');
        }
        // Envoie un nouveau PDF à la bibliothèque (une seule fois, même s'il sert à 20 ascensions) et le sélectionne.
        // Il est rattaché au lieu de l'ascension ; il sera associé à l'ascension quand on clique sur « Enregistrer ».
        async function uploadFichier(file) {
            if (!file) return;
            if (!/\.pdf$/i.test(file.name) && file.type !== 'application/pdf') { flash('Ce fichier n\'est pas un PDF.', true); return; }
            if (file.size > PDF_MAX) { flash('Le PDF dépasse 20 Mo.', true); return; }
            flash('Envoi du PDF…');
            const fd = new FormData();
            fd.append('fichier', file);
            fd.append('ascension_id', st.ascId);
            try {
                const res  = await fetch('/api/topos', { method: 'POST', body: fd });
                const data = await res.json();
                if (!data.success) { flash(data.error || 'Erreur lors de l\'envoi du PDF.', true); return; }
                const t = Object.assign({}, data.topo, { local: true });
                const k = st.topos.findIndex(x => x.id === t.id);
                if (k >= 0) st.topos[k] = t; else st.topos.push(t);
                st.topos.sort((a, b) => a.nom.localeCompare(b.nom, 'fr', { sensitivity: 'base' }));
                renderTopoSelect(t.id);
                st.dirty = true;
                flash(data.existait ? 'Ce PDF était déjà enregistré : il est sélectionné. Clique sur Enregistrer.'
                                    : '✓ PDF ajouté à tes topos. Clique sur Enregistrer pour l\'associer à cette ascension.');
            } catch (err) {
                flash('Erreur lors de l\'envoi du PDF.', true);
            }
        }

        // ── Barre déroulante (type de grimpe, roche, fixations, coinceurs). Les propositions (avec ✕ = les supprimer de la liste) s'ouvrent
        //    au clic ; choisir une proposition la place en pastille dessous (✕ = la retirer seulement de CETTE ascension) ──
        const normTxt = v => (v || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

        function buildComboPicker(c) {
            const key = c.key;
            const sec = document.createElement('section');
            sec.className = 'info-block info-picker full';
            sec.dataset.cat = key;
            const h = document.createElement('h3'); h.textContent = c.label;

            const wrap = document.createElement('div'); wrap.className = 'combo';
            const inp = document.createElement('input');
            inp.type = 'text'; inp.className = 'combo-input'; inp.maxLength = 40; inp.autocomplete = 'off';
            const T = COMBO_TXT[key] || { ph: 'Choisir ou ajouter…', none: 'Aucun choix', new: 'un nouveau choix' };
            inp.placeholder = T.ph;
            inp.setAttribute('role', 'combobox'); inp.setAttribute('aria-expanded', 'false');
            const toggle = document.createElement('button');
            toggle.type = 'button'; toggle.className = 'combo-toggle'; toggle.textContent = '▾';
            toggle.setAttribute('aria-label', 'Afficher les propositions');
            const panel = document.createElement('div'); panel.className = 'combo-panel'; panel.style.display = 'none';
            wrap.append(inp, toggle, panel);

            const chips = document.createElement('div'); chips.className = 'chips';
            sec.append(h, wrap, chips);

            let active = -1, rows = [];
            const selected = () => (st.tags[key] = st.tags[key] || []);
            const isOpen = () => panel.style.display !== 'none';
            const open  = () => { (st.combos || []).forEach(o => { if (o.wrap !== wrap) o.close(); }); panel.style.display = ''; inp.setAttribute('aria-expanded', 'true'); renderPanel(); };
            const close = () => { panel.style.display = 'none'; inp.setAttribute('aria-expanded', 'false'); active = -1; };
            (st.combos = st.combos || []).push({ wrap, close });

            function renderChips() {
                chips.innerHTML = '';
                if (!selected().length) {
                    const e = document.createElement('span'); e.className = 'chips-empty'; e.textContent = T.none;
                    chips.append(e); return;
                }
                selected().forEach(nom => {
                    const chip = document.createElement('span'); chip.className = 'chip selected static';
                    const main = document.createElement('span'); main.className = 'chip-main'; main.textContent = nom;
                    const x = document.createElement('button');
                    x.type = 'button'; x.className = 'chip-x'; x.textContent = '✕';
                    x.title = 'Retirer de cette ascension (reste dans les propositions)';
                    x.setAttribute('aria-label', `Retirer « ${nom} » de cette ascension`);
                    x.addEventListener('click', () => {
                        st.tags[key] = selected().filter(n => !same(n, nom));
                        st.dirty = true; renderChips(); if (isOpen()) renderPanel();
                    });
                    chip.append(main, x); chips.append(chip);
                });
            }

            function choose(nom) {
                if (!selected().some(n => same(n, nom))) { selected().push(nom); st.dirty = true; }
                inp.value = ''; renderChips(); renderPanel(); inp.focus();
            }
            async function create(nom) {
                const res = await fetch('/api/options', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                                                           body: JSON.stringify({ categorie: key, nom }) });
                const data = await res.json();
                if (!data.success) { flash(data.error || 'Erreur.', true); return; }
                if (!(st.options[key] || []).some(o => same(o, data.nom))) (st.options[key] = st.options[key] || []).push(data.nom);
                choose(data.nom);
            }
            async function removeOption(nom) {
                const res = await fetch('/api/options', { method: 'DELETE', headers: { 'Content-Type': 'application/json' },
                                                           body: JSON.stringify({ categorie: key, nom }) });
                const data = await res.json();
                if (!data.success) { flash(data.error || 'Erreur.', true); return; }
                st.options[key] = (st.options[key] || []).filter(o => !same(o, nom));
                renderPanel();
            }

            function renderPanel() {
                panel.innerHTML = ''; rows = [];
                const typed = inp.value.trim(), q = normTxt(typed);
                const avail = (st.options[key] || []).filter(o => !selected().some(n => same(n, o)) && (!q || normTxt(o).includes(q)));
                avail.forEach(nom => {
                    const row = document.createElement('div'); row.className = 'combo-item'; row.setAttribute('role', 'option');
                    const pick = document.createElement('button'); pick.type = 'button'; pick.className = 'combo-pick'; pick.textContent = nom;
                    const del = document.createElement('button'); del.type = 'button'; del.className = 'combo-del'; del.textContent = '✕';
                    del.title = 'Supprimer cette proposition de la liste'; del.setAttribute('aria-label', `Supprimer « ${nom} » des propositions`);
                    row.addEventListener('mousedown', e => e.preventDefault());       // garde le focus dans la barre
                    pick.addEventListener('click', () => choose(nom));
                    del.addEventListener('click', e => { e.stopPropagation(); removeOption(nom); });
                    row.append(pick, del); panel.append(row);
                    rows.push({ el: row, run: () => choose(nom) });
                });
                const known = (st.options[key] || []).some(o => same(o, typed));
                if (typed && !known) {
                    const row = document.createElement('div'); row.className = 'combo-item combo-create';
                    const pick = document.createElement('button'); pick.type = 'button'; pick.className = 'combo-pick';
                    pick.textContent = `+ Ajouter « ${typed} »`;
                    row.addEventListener('mousedown', e => e.preventDefault());
                    pick.addEventListener('click', () => create(typed));
                    row.append(pick); panel.append(row);
                    rows.push({ el: row, run: () => create(typed) });
                }
                if (!rows.length) {
                    const e = document.createElement('div'); e.className = 'combo-empty';
                    e.textContent = typed ? 'Aucune proposition' : 'Plus aucune proposition : écris ' + T.new;
                    panel.append(e);
                }
                active = Math.min(active, rows.length - 1);
                rows.forEach((r, i) => r.el.classList.toggle('active', i === active));
            }

            inp.addEventListener('focus', open);
            inp.addEventListener('click', () => { if (!isOpen()) open(); });
            inp.addEventListener('input', () => { active = -1; open(); });
            toggle.addEventListener('click', () => { if (isOpen()) close(); else { open(); inp.focus(); } });
            inp.addEventListener('keydown', e => {
                if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                    e.preventDefault(); if (!isOpen()) open();
                    if (rows.length) {
                        active = (active + (e.key === 'ArrowDown' ? 1 : -1) + rows.length) % rows.length;
                        rows.forEach((r, i) => r.el.classList.toggle('active', i === active));
                        rows[active].el.scrollIntoView({ block: 'nearest' });
                    }
                } else if (e.key === 'Enter') {
                    e.preventDefault();
                    const typed = inp.value.trim();
                    if (active >= 0 && rows[active]) rows[active].run();
                    else if (typed) {
                        const known = (st.options[key] || []).find(o => same(o, typed));
                        if (known) choose(known); else create(typed);
                    }
                } else if (e.key === 'Escape') {
                    if (isOpen()) { e.stopPropagation(); close(); }
                }
            });
            renderChips();
            return sec;
        }


        // ── Fiche en lecture : tout ce qui a été renseigné, présenté comme un texte ──
        const el = (tag, cls, txt) => { const n = document.createElement(tag); if (cls) n.className = cls; if (txt != null) n.textContent = txt; return n; };
        const vide = () => el('p', 'iv-vide', 'Non renseigné');
        // Bloc titré de la fiche en lecture.
        function vSection(titre, ...contenus) {
            const sec = el('section', 'iv-section');
            sec.append(el('h3', '', titre), ...contenus);
            return sec;
        }
        // Ligne « libellé : valeur » de la fiche en lecture.
        function vRow(label, value) {
            const r = el('div', 'iv-row'); r.append(el('span', 'iv-label', label), el('span', 'iv-value', value)); return r;
        }
        // Liste de pastilles en lecture seule.
        function vTags(names) {
            const box = el('div', 'iv-tags');
            names.forEach(n => box.append(el('span', 'iv-tag', n)));
            return box;
        }

        // Construit la fiche en lecture à partir des données chargées (st.data) et des choix en mémoire.
        function renderView() {
            const d = st.data, pane = $('infoViewPane');
            pane.innerHTML = '';
            $('infoNom').textContent = d.nom;

            // Ouverture
            const o = d.ouverture || {};
            // Ouverture : l'année sur sa ligne ; l'ouvreur sur la sienne, avec les rééquipements à droite (même ligne)
            const ouv = [];
            if (o.annee) ouv.push(vRow("Année d'ouverture", String(o.annee)));
            const reeq = d.reequipements || [];
            const reeqTxt = reeq.map(r => r.nom ? (r.annee ? `${r.nom} (${r.annee})` : r.nom) : `en ${r.annee}`).join(' · ');
            const reeqLabel = reeq.length > 1 ? 'Rééquipements' : (reeq.length && reeq[0].nom ? 'Rééquipé par' : 'Rééquipé');
            if (o.ouvreur || reeq.length) {
                const r = el('div', 'iv-row iv-wrap');
                r.append(el('span', 'iv-label', 'Ouvreur'), el('span', 'iv-value', o.ouvreur || '—'));
                if (reeq.length) {
                    const side = el('span', 'iv-side');
                    side.append(el('span', 'iv-label', reeqLabel), el('span', 'iv-value', reeqTxt));
                    r.append(side);
                }
                ouv.push(r);
            }
            // Séances
            const seBlock = [];
            if (d.nb_seances) {
                seBlock.push(el('p', 'iv-resume', `${plur(d.nb_seances, 'séance')} · ${plur(d.total_essais, 'essai')} au total`));
                const ul = el('div', 'iv-seances');
                d.seances.forEach(sc => {
                    const it = el('div', 'iv-seance');
                    const head = el('div', 'iv-seance-head');
                    head.append(el('strong', '', `Séance n°${sc.numero}`), el('span', '', `${sc.date_fmt || 'date non renseignée'} · ${plur(sc.nb_essais, 'essai')}`));
                    it.append(head);
                    if (sc.commentaire) it.append(el('p', 'iv-note', sc.commentaire));
                    ul.append(it);
                });
                seBlock.push(ul);
            }
            // Topo
            const t = d.topo || {}, topoBlock = [];
            if (t.topo_type === 'papier') {
                topoBlock.push(vRow('Support', '📖 Topo papier'));
                if (t.topo_nom)     topoBlock.push(vRow('Titre', t.topo_nom));
                if (t.topo_edition) topoBlock.push(vRow('Édition', t.topo_edition));
                if (t.topo_annee)   topoBlock.push(vRow('Année de publication', String(t.topo_annee)));
                if (t.topo_page)    topoBlock.push(vRow('Page', String(t.topo_page)));
            } else if (t.topo_type === 'pdf') {
                topoBlock.push(vRow('Support', '📄 PDF / en ligne'));
                if (t.topo_nom) topoBlock.push(vRow('Titre', t.topo_nom));
                const l = normLink(t.topo_lien);
                if (l) {
                    const a = el('a', 'iv-link', 'Ouvrir le topo ↗'); a.href = l; a.target = '_blank'; a.rel = 'noopener noreferrer';
                    const r = el('div', 'iv-row'); r.append(el('span', 'iv-label', 'Lien'), a); topoBlock.push(r);
                }
            }

            // Topo PDF choisi dans la bibliothèque : lien vers le lecteur du navigateur
            if (d.topo_pdf) {
                const a = el('a', 'iv-link', `📎 ${d.topo_pdf.nom} (${fmtSize(d.topo_pdf.taille)})`);
                a.href = pdfUrl(d.topo_pdf.id); a.target = '_blank'; a.rel = 'noopener noreferrer';
                const r = el('div', 'iv-row'); r.append(el('span', 'iv-label', 'PDF enregistré'), a); topoBlock.push(r);
            }

            let rempli = ouv.length || seBlock.length || topoBlock.length;
            pane.append(
                vSection('Ouverture', ...(ouv.length ? ouv : [vide()])),
                vSection('Séances', ...(seBlock.length ? seBlock : [el('p', 'iv-vide', "Aucune séance enregistrée : cette ascension n'est pas passée par les projets.")])),
                vSection('Topo consulté', ...(topoBlock.length ? topoBlock : [vide()]))
            );
            (d.cats || []).forEach(c => {
                const names = (st.tags[c.key] || []);
                if (names.length) rempli = true;
                pane.append(vSection(c.label, names.length ? vTags(names) : vide()));
            });
            if (!rempli) {
                pane.prepend(el('p', 'iv-intro', "Rien n'a encore été renseigné pour cette ascension. Utilise le bouton ci-dessous pour ajouter l'ouverture, le topo, le type de roche, etc."));
            }
        }

        // Bascule entre fiche (view) et formulaire (edit) en adaptant les boutons du pied de fenêtre.
        function setMode(mode) {
            st.mode = mode;
            const edit = mode === 'edit';
            $('infoViewPane').style.display = edit ? 'none' : '';
            $('infoFormPane').style.display = edit ? '' : 'none';
            $('btnInfoClose').style.display = edit ? 'none' : '';
            $('btnInfoEdit').style.display  = edit ? 'none' : '';
            $('btnInfoBack').style.display  = edit ? '' : 'none';
            $('btnInfoSave').style.display  = edit ? '' : 'none';
            $('infoModalOverlay').querySelector('.modal-body').scrollTop = 0;
        }

        // ── Rééquipements : « rééquipé par … » + année, plusieurs possibles ──
        // Ajoute une ligne « rééquipé par … / année » au formulaire.
        function addReeqRow(nom, annee, focus) {
            const row = document.createElement('div'); row.className = 'reeq-row';
            const n = document.createElement('input');
            n.type = 'text'; n.className = 'reeq-nom'; n.maxLength = 100; n.autocomplete = 'off'; n.setAttribute('list', 'listOuvreurs');
            n.placeholder = 'Nom'; n.setAttribute('aria-label', 'Rééquipé par'); n.value = nom || '';
            const a = document.createElement('input');
            a.type = 'number'; a.className = 'reeq-annee'; a.min = 1800; a.max = 2100; a.placeholder = '2021';
            a.setAttribute('aria-label', 'Année de rééquipement'); a.value = annee || '';
            const x = document.createElement('button');
            x.type = 'button'; x.className = 'reeq-x'; x.textContent = '✕'; x.title = 'Retirer ce rééquipement'; x.setAttribute('aria-label', 'Retirer ce rééquipement');
            x.addEventListener('click', () => {
                const rows = $('infoReeq').querySelectorAll('.reeq-row');
                if (rows.length > 1) row.remove(); else { n.value = ''; a.value = ''; }   // la première ligne reste, vidée
                st.dirty = true;
            });
            row.append(n, a, x);
            $('infoReeq').append(row);
            if (focus) n.focus();
        }
        // Lit les lignes de rééquipement saisies, en ignorant les lignes vides.
        const collectReeq = () => [...$('infoReeq').querySelectorAll('.reeq-row')]
            .map(r => ({ nom: r.querySelector('.reeq-nom').value.trim(), annee: r.querySelector('.reeq-annee').value.trim() }))
            .filter(r => r.nom || r.annee);

        // Affiche, dans le formulaire, les séances liées (lecture seule, dépliables).
        function renderSeances(data) {
            const box = $('infoSeances');
            box.innerHTML = '';
            $('infoResume').textContent = data.nb_seances
                ? `${plur(data.nb_seances, 'séance')} · ${plur(data.total_essais, 'essai')} au total. Clique sur une séance pour lire son mini-journal.`
                : "Aucune séance enregistrée : cette ascension n'est pas passée par les projets.";
            data.seances.forEach(sc => {
                const det = document.createElement('details');
                det.className = 'info-seance';
                const sum = document.createElement('summary');
                sum.textContent = `Séance n°${sc.numero} · ${sc.date_fmt || 'date non renseignée'} · ${plur(sc.nb_essais, 'essai')}`;
                const p = document.createElement('p');
                if (sc.commentaire) { p.textContent = sc.commentaire; }
                else { p.textContent = 'Pas de commentaire pour cette séance.'; p.className = 'info-vide'; }
                det.append(sum, p);
                box.append(det);
            });
        }

        // Remplit le formulaire avec les dernières valeurs enregistrées.
        function fillForm(data) {
            $('infoNom').textContent = data.nom;
            renderSeances(data);
            const t = data.topo || {};
            document.querySelectorAll('input[name=infoTopoType]').forEach(r => { r.checked = r.value === (t.topo_type || ''); });
            $('infoTopoNom').value      = t.topo_type === 'papier' ? (t.topo_nom || '') : '';
            $('infoTopoEdition').value  = t.topo_edition || '';
            $('infoTopoAnnee').value    = t.topo_annee || '';
            $('infoTopoPage').value     = t.topo_page || '';
            $('infoTopoNomPdf').value   = t.topo_type === 'pdf' ? (t.topo_nom || '') : '';
            $('infoTopoLien').value     = t.topo_lien || '';
            showTopoFields(); refreshLink();
            st.topos = data.topos || [];                       // bibliothèque de topos PDF (ceux du site d'abord)
            renderTopoSelect(data.topo_pdf ? data.topo_pdf.id : null);   // topo PDF déjà choisi, ou aucun
            $('infoOuvAnnee').value = (data.ouverture || {}).annee || '';
            $('infoOuvreur').value  = (data.ouverture || {}).ouvreur || '';
            $('infoReeq').innerHTML = '';
            const reeq = data.reequipements || [];
            if (reeq.length) reeq.forEach(r => addReeqRow(r.nom, r.annee)); else addReeqRow('', '');
            fillDatalist('listTopos', NOMS_CACHE.topos);
            fillDatalist('listOuvreurs', NOMS_CACHE.ouvreurs);
            st.options = data.options || {};
            st.tags = {};
            (data.cats || []).forEach(c => { st.tags[c.key] = [...(data.tags[c.key] || [])]; });
            document.querySelectorAll('#infoGrid .info-picker').forEach(n => n.remove());
            st.combos = [];
            (data.cats || []).forEach(c => $('infoGrid').append(buildComboPicker(c)));
        }

        // Ouvre la fenêtre : charge les informations de l'ascension puis affiche la fiche.
        async function openInfo(ascId) {
            st.ascId = ascId; st.dirty = false;
            flash('');
            $('infoNom').textContent = '';
            $('infoSeances').innerHTML = '';
            $('infoResume').textContent = 'Chargement…';
            $('infoViewPane').append(el('p', 'iv-vide', 'Chargement…'));
            document.querySelectorAll('#infoGrid .info-picker').forEach(n => n.remove());
            st.combos = []; st.data = null;
            $('infoViewPane').innerHTML = '';
            setMode('view');
            openModal('infoModalOverlay');
            await NOMS_PROMISE;
            try {
                const res  = await fetch(`/api/ascension/${ascId}/infos`);
                const data = await res.json();
                if (data.error) { $('infoViewPane').textContent = data.error; return; }
                st.data = data;
                st.tags = {};
                (data.cats || []).forEach(c => { st.tags[c.key] = [...(data.tags[c.key] || [])]; });
                st.options = data.options || {};
                renderView(); setMode('view');
            } catch (err) {
                $('infoViewPane').textContent = 'Erreur de chargement.';
            }
        }

        // Passe en mode édition.
        function startEdit() {
            if (!st.data) return;
            flash('');
            fillForm(st.data);        // repart toujours des dernières valeurs enregistrées
            st.dirty = false;
            setMode('edit');
        }
        // Quitte l'édition sans enregistrer (après confirmation s'il y a des modifications).
        function backToView() {
            if (st.dirty && !confirm('Des modifications ne sont pas enregistrées. Les abandonner ?')) return;
            st.dirty = false;
            st.data.options = st.options;     // les suppressions de propositions, elles, sont déjà faites côté serveur
            // les choix non enregistrés sont abandonnés
            st.tags = {}; (st.data.cats || []).forEach(c => { st.tags[c.key] = [...(st.data.tags[c.key] || [])]; });
            renderView(); setMode('view'); flash('');
        }
        // Ferme la fenêtre (après confirmation s'il y a des modifications non enregistrées).
        function closeInfo() {
            if (st.dirty && !confirm('Des modifications ne sont pas enregistrées. Fermer quand même ?')) return;
            closeModal('infoModalOverlay');
        }

        // Envoie le formulaire au serveur ; en cas de succès, met à jour la fiche et les suggestions de noms.
        async function saveInfo() {
            const t = topoType();
            const body = {
                topo_type:       t,
                topo_nom:        t === 'papier' ? $('infoTopoNom').value : (t === 'pdf' ? $('infoTopoNomPdf').value : ''),
                topo_edition:    $('infoTopoEdition').value,
                topo_annee:      $('infoTopoAnnee').value,
                topo_page:       $('infoTopoPage').value,
                topo_lien:       $('infoTopoLien').value,
                topo_id:         t === 'pdf' ? selectedTopoId() : null,
                annee_ouverture: $('infoOuvAnnee').value,
                ouvreur:         $('infoOuvreur').value,
                reequipements:   collectReeq(),
                tags:            st.tags,
            };
            const res  = await fetch(`/api/ascension/${st.ascId}/infos`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
            const data = await res.json();
            if (!data.success) { flash(data.error || "Erreur lors de l'enregistrement.", true); return; }
            st.dirty = false;
            // la fiche en lecture reprend les valeurs enregistrées
            Object.assign(st.data, {
                topo: { topo_type: t, topo_nom: body.topo_nom, topo_edition: body.topo_edition, topo_annee: body.topo_annee,
                        topo_page: body.topo_page, topo_lien: normLink(body.topo_lien) },
                ouverture: { annee: body.annee_ouverture, ouvreur: (body.ouvreur || '').trim() },
                topo_pdf: (t === 'pdf' && body.topo_id) ? ((st.topos || []).find(x => x.id === body.topo_id) || null) : null,
                reequipements: body.reequipements,
                tags: JSON.parse(JSON.stringify(st.tags)), options: st.options
            });
            // les nouveaux noms deviennent des suggestions pour les prochaines saisies
            const addName = (arr, v) => { v = (v || '').trim(); if (v && !arr.some(x => same(x, v))) arr.push(v); };
            NOMS_CACHE.ouvreurs = NOMS_CACHE.ouvreurs || []; NOMS_CACHE.topos = NOMS_CACHE.topos || [];
            addName(NOMS_CACHE.ouvreurs, body.ouvreur);
            body.reequipements.forEach(r => addName(NOMS_CACHE.ouvreurs, r.nom)); addName(NOMS_CACHE.topos, body.topo_nom);
            fillDatalist('listTopos', NOMS_CACHE.topos); fillDatalist('listOuvreurs', NOMS_CACHE.ouvreurs);
            renderView(); setMode('view');
            flash('✓ Informations enregistrées');
        }

        // Ouverture : clic sur un bouton « i » d'une ascension.
        document.addEventListener('click', e => {
            const btn = e.target.closest('.btn-asc-info');
            if (btn) openInfo(btn.dataset.ascId);
        });
        document.querySelectorAll('input[name=infoTopoType]').forEach(r => r.addEventListener('change', () => { showTopoFields(); st.dirty = true; }));
        $('infoTopoLien').addEventListener('input', refreshLink);
        // Topo PDF : choix dans la bibliothèque, ou envoi d'un nouveau fichier
        $('infoTopoFichier').addEventListener('change', e => { uploadFichier(e.target.files[0]); e.target.value = ''; });
        $('infoTopoId').addEventListener('change', () => { refreshTopoOpen(); st.dirty = true; });
        // toute saisie dans un champ du formulaire = modification non enregistrée
        infoOverlay.addEventListener('input', e => { if (e.target.closest('.info-fields')) st.dirty = true; });
        document.addEventListener('mousedown', e => { (st.combos || []).forEach(o => { if (!o.wrap.contains(e.target)) o.close(); }); });
        $('btnInfoSave').addEventListener('click', saveInfo);
        $('btnInfoEdit').addEventListener('click', startEdit);
        $('btnReeqAdd').addEventListener('click', () => { addReeqRow('', '', true); st.dirty = true; });
        $('btnInfoBack').addEventListener('click', backToView);
        $('btnInfoClose').addEventListener('click', closeInfo);
        $('btnCloseInfoModal').addEventListener('click', closeInfo);
        infoOverlay.addEventListener('click', e => { if (e.target === infoOverlay) closeInfo(); });
    }
}
