// Séances d'un projet : mini-journal de ce qu'on a fait à chaque session d'essais (date, nombre d'essais, commentaire).
//
// Fenêtre #seanceModalOverlay (partials/modal_seance.html), ouverte par le bouton « séances » d'une carte projet
// (.btn-seance) ou depuis la page Projets. Elle sert aussi de formulaire « Passer en projet » : sur la Tick List, « ⚡ Projet »
// l'ouvre en mode `fromTicklist` (l'envie ne devient projet qu'à l'enregistrement de la séance, ou avec « Passer en projet sans
// séance »). Une adresse /projets?seance=<id> l'ouvre aussi, sur la séance n°1 (pour la détailler) : c'est ce qu'on propose
// juste après l'ajout d'un projet. API : POST /api/ascension/<id>/projet pour le changement de statut. Les séances sont numérotées par le serveur (1, 2, 3…) et le total d'essais
// du projet est la somme de ses séances. API : /api/ascension/<id>/seances (GET, POST) et /api/seance/<id> (PUT, DELETE),
// voir routes/api_seances.py.

// Branche toute la fenêtre des séances ; sans effet sur une page qui ne l'a pas.
function initSeances() {
    // ═══ SÉANCES D'UN PROJET (formulaire : date, essais +1/−1, mini-journal) ═══
    const seanceOverlay = document.getElementById('seanceModalOverlay');
    if (seanceOverlay) {
        const $ = id => document.getElementById(id);
        // Pluriel simple : plur(3, 'essai') → « 3 essais ».
        const plur = (n, w) => `${n} ${w}${n > 1 ? 's' : ''}`;
        // Date du jour au format AAAA-MM-JJ (valeur par défaut du champ date d'une nouvelle séance).
        const todayIso = () => {
            const d = new Date();
            return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
        };
        // AAAA-MM-JJ → JJ/MM/AAAA.
        const fmtDate = iso => iso ? iso.split('-').reverse().join('/') : '';
        // État de la fenêtre : ascension ouverte, séances chargées, total d'essais, séance en cours de modification (editId),
        // et `dirty` = quelque chose a changé (on rechargera la page à la fermeture pour mettre à jour les cartes).
        // `fromTicklist` = l'ascension est encore une envie : elle passera en projet à l'enregistrement.
        const st = { ascId: null, type: null, seances: [], total: 0, editId: null, dirty: false, fromTicklist: false };

        // Petit message de confirmation ou d'erreur dans la fenêtre (une confirmation disparaît seule au bout de 2,5 s).
        const flash = (msg, isError) => {
            const f = $('seanceFlash');
            f.textContent = msg; f.classList.toggle('error', !!isError); f.style.display = msg ? 'block' : 'none';
            if (msg && !isError) setTimeout(() => { if (f.textContent === msg) f.style.display = 'none'; }, 2500);
        };
        // Nombre d'essais affiché dans le compteur + / −, ramené à un entier ≥ 0.
        const essaisVal = () => Math.max(0, parseInt($('seanceEssais').value) || 0);

        // Redessine l'historique : résumé (nombre de séances, total d'essais) puis une ligne par séance avec ses boutons modifier / supprimer.
        function renderHistory() {
            const box = $('seanceHistory');
            box.innerHTML = '';
            const nb = st.seances.length;
            $('seanceResume').textContent = nb
                ? `${plur(nb, 'séance')} · ${plur(st.total, 'essai')} au total`
                : 'Aucune séance enregistrée pour le moment.';
            st.seances.forEach(sc => {
                const row = document.createElement('div');
                row.className = 'sh-item' + (st.editId === sc.id ? ' editing' : '');
                const head = document.createElement('div');
                head.className = 'sh-head';
                const title = document.createElement('span');
                title.className = 'sh-title';
                title.textContent = `Séance n°${sc.numero}`;
                const meta = document.createElement('span');
                meta.className = 'sh-meta';
                meta.textContent = [sc.date_fmt || 'date non renseignée', plur(sc.nb_essais, 'essai')].join(' · ');
                const actions = document.createElement('span');
                actions.className = 'sh-actions';
                const be = document.createElement('button'); be.type = 'button'; be.className = 'btn-icon-sm'; be.title = 'Modifier'; be.textContent = '✏';
                const bd = document.createElement('button'); bd.type = 'button'; bd.className = 'btn-icon-sm'; bd.title = 'Supprimer'; bd.textContent = '✕';
                be.addEventListener('click', () => startEdit(sc));
                bd.addEventListener('click', () => deleteSeance(sc));
                actions.append(be, bd);
                head.append(title, meta, actions);
                row.append(head);
                if (sc.commentaire) {
                    const note = document.createElement('p');
                    note.className = 'sh-note';
                    note.textContent = sc.commentaire;
                    row.append(note);
                }
                box.append(row);
            });
        }

        // Prépare le formulaire pour une NOUVELLE séance : numéro suivant, rappel de la séance précédente, date du jour, compteur à 0.
        function resetForm() {
            st.editId = null;
            const n = st.seances.length;
            $('seanceFormTitle').textContent = `Séance n°${n + 1}`;
            const prev = st.seances[n - 1];
            $('seancePrevHint').textContent = prev
                ? `Séance précédente (n°${prev.numero}) : ${plur(prev.nb_essais, 'essai')}`
                : 'Première séance sur ce projet.';
            $('seanceDate').value = todayIso();
            $('seanceEssais').value = 0;
            $('seanceComment').value = '';
            $('btnSeanceSave').textContent = 'Enregistrer la séance';
            $('btnSeanceCancelEdit').style.display = 'none';
            renderHistory();
        }

        // Passe le formulaire en mode « modifier cette séance » avec ses valeurs actuelles.
        function startEdit(sc) {
            st.editId = sc.id;
            $('seanceFormTitle').textContent = `Modifier la séance n°${sc.numero}`;
            $('seancePrevHint').textContent = '';
            $('seanceDate').value = sc.date || '';
            $('seanceEssais').value = sc.nb_essais;
            $('seanceComment').value = sc.commentaire || '';
            $('btnSeanceSave').textContent = 'Enregistrer les modifications';
            $('btnSeanceCancelEdit').style.display = '';
            flash('');
            renderHistory();
            $('seanceFormTitle').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        // Recharge les séances depuis le serveur puis remet le formulaire à zéro. Renvoie false en cas d'erreur.
        async function loadSeances() {
            const res = await fetch(`/api/ascension/${st.ascId}/seances`);
            const data = await res.json();
            if (data.error) { flash(data.error, true); return false; }
            st.seances = data.seances; st.total = data.total_essais;
            resetForm();
            return true;
        }

        // Adapte la fenêtre au mode : « Passer en projet » (envie de la tick list) ou « Séances du projet ».
        function applyMode() {
            $('seanceModalTitle').textContent = st.fromTicklist ? 'Passer en projet' : 'Séances du projet';
            document.querySelector('.seance-finish').style.display = st.fromTicklist ? 'none' : '';
            $('btnSeanceSkip').style.display = st.fromTicklist ? '' : 'none';
        }

        // Ouvre la fenêtre pour une ascension (aussi appelée depuis d'autres scripts).
        // Options : fromTicklist (envie qui devient projet), editFirst (ouvre directement la séance n°1 en modification, pour la détailler).
        window.openSeanceModal = async (ascId, type, nom, opts = {}) => {
            Object.assign(st, { ascId, type, dirty: false, editId: null, fromTicklist: !!opts.fromTicklist });
            $('seanceAscId').value = ascId;
            $('seanceAscType').value = type;
            $('seanceNom').textContent = nom || '';
            flash('');
            applyMode();
            openModal('seanceModalOverlay');
            await loadSeances();
            if (opts.editFirst && st.seances.length) startEdit(st.seances[0]);
        };

        // Envie de la tick list : la passe en projet (sans séance) juste avant d'enregistrer. Renvoie false en cas d'erreur.
        async function ensureProjet() {
            if (!st.fromTicklist) return true;
            const res  = await fetch(`/api/ascension/${st.ascId}/projet`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nb_essais_projet: 0 }) });
            const data = await res.json();
            if (!data.success) { flash(data.error || 'Erreur lors du passage en projet.', true); return false; }
            st.fromTicklist = false; st.dirty = true;
            applyMode();
            return true;
        }

        function closeSeanceModal() {
            closeModal('seanceModalOverlay');
            if (st.dirty) location.reload();    // met à jour les cartes derrière le formulaire
        }

        // Enregistre (ou modifie) la séance du formulaire. Retourne true si tout s'est bien passé.
        async function saveSeance() {
            const date = $('seanceDate').value;
            const nb   = essaisVal();
            if (!date) { flash('La date de la séance est requise.', true); return false; }
            if (nb < 1) { flash("Indique au moins 1 essai avec les boutons + / −.", true); return false; }
            const body = JSON.stringify({ date, nb_essais: nb, commentaire: $('seanceComment').value });
            const wasTicklist = st.fromTicklist;
            if (!(await ensureProjet())) return false;       // envie : elle devient projet avec cette séance
            const url  = st.editId ? `/api/seance/${st.editId}` : `/api/ascension/${st.ascId}/seances`;
            const res  = await fetch(url, { method: st.editId ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body });
            const data = await res.json();
            if (!data.success) { flash(data.error || "Erreur lors de l'enregistrement.", true); return false; }
            st.dirty = true;
            const wasEdit = !!st.editId;
            if (wasTicklist) { closeSeanceModal(); return true; }     // l'envie est devenue projet : on recharge la Tick List
            await loadSeances();
            flash(wasEdit ? '✓ Séance modifiée' : '✓ Séance enregistrée');
            return true;
        }

        async function deleteSeance(sc) {
            if (!confirm(`Supprimer la séance n°${sc.numero} (${plur(sc.nb_essais, 'essai')}) et son commentaire ?`)) return;
            const res = await fetch(`/api/seance/${sc.id}`, { method: 'DELETE' });
            const data = await res.json();
            if (!data.success) { flash(data.error || 'Erreur lors de la suppression.', true); return; }
            st.dirty = true;
            await loadSeances();
        }

        // Clic sur le bouton « séances » d'une carte.
        document.addEventListener('click', e => {
            const btn = e.target.closest('.btn-seance');
            if (!btn) return;
            window.openSeanceModal(btn.dataset.ascId, btn.dataset.type, btn.dataset.nom);
        });
        $('seanceMinus').addEventListener('click', () => { $('seanceEssais').value = Math.max(0, essaisVal() - 1); });
        $('seancePlus').addEventListener('click',  () => { $('seanceEssais').value = Math.min(999, essaisVal() + 1); });
        $('seanceEssais').addEventListener('change', () => { $('seanceEssais').value = Math.min(999, essaisVal()); });
        $('btnSeanceSave').addEventListener('click', saveSeance);
        // Tick list : passe l'envie en projet sans enregistrer de séance, puis ferme (et recharge la liste).
        $('btnSeanceSkip').addEventListener('click', async () => { if (await ensureProjet()) closeSeanceModal(); });
        $('btnSeanceCancelEdit').addEventListener('click', () => { flash(''); resetForm(); });
        $('btnCloseSeanceModal').addEventListener('click', closeSeanceModal);
        seanceOverlay.addEventListener('click', e => { if (e.target === seanceOverlay) closeSeanceModal(); });

        // Projet réussi : on enregistre d'abord la séance en cours (si le compteur n'est pas à 0),
        // puis on ouvre « Marquer comme grimpé » avec le total d'essais du projet déjà rempli.
        $('btnSeanceFinish').addEventListener('click', async () => {
            if (!st.editId && essaisVal() > 0) {
                if (!(await saveSeance())) return;
            }
            const nb = st.seances.length;
            const hint = nb
                ? `Projet en ${plur(nb, 'séance')} : ${plur(st.total, 'essai')} au total${st.total > 5 ? ' (plus de 5 essais)' : ''}.`
                : '';
            window.openLogModalPrefilled?.(st.ascId, st.type, { date: todayIso(), style: essaisToStyle(st.total), hint });
        });

    // Adresse /projets?seance=<id> (après l'ajout d'un projet) : ouvre la séance n°1 de ce projet pour la détailler.
    const wanted = new URLSearchParams(location.search).get('seance');
    if (seanceOverlay && wanted) {
        fetch(`/api/ascension/${encodeURIComponent(wanted)}/seances`).then(r => r.json()).then(d => {
            if (d.error) return;
            window.openSeanceModal(wanted, d.type, d.nom, { editFirst: true });
        }).finally(() => window.history.replaceState({}, '', location.pathname));     // l'adresse redevient /projets
    }
    }
}
