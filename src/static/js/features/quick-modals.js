// Petites fenêtres rapides : « Marquer comme grimpé » (projet ou envie → log), bouton « ⚡ Projet » de la Tick List
// (qui ouvre la fenêtre des séances, voir seances.js) et suggestions de la barre de recherche.
//
// Fenêtre #logModalOverlay (partials/modal_log.html).
// API : POST /api/ascension/<id>/log (routes/api_ascensions.py).

// Branche la fenêtre « Marquer comme grimpé », le bouton « ⚡ Projet » et la liste de suggestions de la recherche.
function initQuickModals() {
    // ── LOG DEPUIS PROJET / TICKLIST ──
    const logModalOverlay = document.getElementById('logModalOverlay');
    const btnCloseLog     = document.getElementById('btnCloseLogModal');

    if (logModalOverlay) {
        // Ouvre le formulaire « Marquer comme grimpé », éventuellement pré-rempli (doublon détecté à l'ajout)
        // Utilisée par la fenêtre d'ajout quand l'ascension existe déjà comme projet ou envie : ouvre « Marquer comme grimpé »
        // pré-rempli, avec une phrase (`hint`) qui rappelle les essais déjà faits.
        window.openLogModalPrefilled = (ascId, type, p = {}) => {
            document.getElementById('logAscId').value      = ascId;
            document.getElementById('logDate').value       = p.date || '';
            document.getElementById('logStyle').value      = p.style || '';
            document.getElementById('logCotPerso').value   = p.cotation_perso || '';
            const hintEl = document.getElementById('logEssaisHint');
            if (hintEl) { hintEl.textContent = p.hint || ''; hintEl.style.display = p.hint ? 'block' : 'none'; }
            document.getElementById('logPiedsNus').checked = !!p.pieds_nus;
            const grimpRow = document.getElementById('logGrimpeRow');
            if (grimpRow) {
                grimpRow.style.display = ['voie','grande_voie','trad_voie','trad_gv'].includes(type) ? 'flex' : 'none';
                const g = document.getElementById('logGrimpe');
                if (g) g.value = p.grimpe || '';
            }
            const s = document.getElementById('logStars');
            if (s) { s.dataset.val = p.note_beaute || 0; updateStars(s); }
            openModal('logModalOverlay');
        };

        // Bouton « grimpé » d'un projet ou d'une envie : ouvre la fenêtre vide (la ligne « en tête / moulinette » n'apparaît que pour les voies).
        document.addEventListener('click', e => {
            const btn = e.target.closest('.btn-log');
            if (!btn) return;
            document.getElementById('logAscId').value    = btn.dataset.ascId;
            const hintEl0 = document.getElementById('logEssaisHint');
            if (hintEl0) { hintEl0.textContent = ''; hintEl0.style.display = 'none'; }
            document.getElementById('logDate').value     = '';
            document.getElementById('logStyle').value    = '';
            document.getElementById('logCotPerso').value = '';
            document.getElementById('logPiedsNus').checked = false;
            const grimpRow = document.getElementById('logGrimpeRow');
            if (grimpRow) {
                const t = btn.dataset.type || '';
                grimpRow.style.display = ['voie','grande_voie','trad_voie','trad_gv'].includes(t) ? 'flex' : 'none';
            }
            const s = document.getElementById('logStars');
            if (s) { s.dataset.val = 0; updateStars(s); }
            openModal('logModalOverlay');
        });

        if (btnCloseLog) btnCloseLog.addEventListener('click', () => closeModal('logModalOverlay'));
        logModalOverlay.addEventListener('click', e => { if (e.target === logModalOverlay) closeModal('logModalOverlay'); });

        // Envoi : date obligatoire, et mode en tête / moulinette obligatoire pour une voie ; l'ascension passe alors au statut « log ».
        const btnSubmitLog = document.getElementById('btnSubmitLog');
        if (btnSubmitLog) {
            btnSubmitLog.addEventListener('click', async () => {
                const ascId = document.getElementById('logAscId').value;
                const date  = document.getElementById('logDate').value;
                if (!date) { alert('La date est requise.'); return; }
                const grimpeRow = document.getElementById('logGrimpeRow');
                if (grimpeRow && grimpeRow.style.display !== 'none' && !document.getElementById('logGrimpe')?.value) {
                    alert("Indique si c'est grimpé en tête ou en moulinette."); return;
                }
                const s   = document.getElementById('logStars');
                const res = await fetch(`/api/ascension/${ascId}/log`, {
                    method: 'POST',
                    headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({
                        date,
                        style:          document.getElementById('logStyle')?.value    || null,
                        cotation_perso: document.getElementById('logCotPerso')?.value || null,
                        pieds_nus:      document.getElementById('logPiedsNus')?.checked,
                        note_beaute:    s ? parseInt(s.dataset.val) || null : null,
                        grimpe:         document.getElementById('logGrimpe')?.value   || null,
                    })
                });
                const data = await res.json();
                if (data.success) {
                    closeModal('logModalOverlay');
                    // Sur la Tick List, la ligne se coche (animation) avant le rechargement.
                    const done = document.querySelector(`.tl-item[data-id="${ascId}"]`);
                    if (done) { done.classList.add('tl-done'); setTimeout(() => location.reload(), 500); }   // tick list : la ligne se coche puis disparaît
                    else location.reload();
                }
                else if (data.error) alert(data.error);
            });
        }
    }

    // ── TICK LIST → PROJET ──
    // Envie → projet : « ⚡ Projet » ouvre directement le formulaire de séance complet (date, essais, mini-journal) de
    // features/seances.js, en mode « Passer en projet » : l'envie ne devient projet qu'à l'enregistrement de la séance.
    document.addEventListener('click', e => {
        const btn = e.target.closest('.btn-to-projet');
        if (!btn || !window.openSeanceModal) return;
        window.openSeanceModal(btn.dataset.ascId, btn.dataset.type, btn.dataset.nom, { fromTicklist: true });
    });

    // ── Suggestions de noms pour la recherche (ascensions + lieux) ──
    // Remplit la liste de suggestions de la barre de recherche avec les noms d'ascensions et de lieux déjà saisis.
    const listRecherche = document.getElementById('listRecherche');
    if (listRecherche) {
        NOMS_PROMISE.then(d => {
            const all = [...new Set([...(d.ascensions || []), ...(d.lieux || [])])];
            listRecherche.innerHTML = all.map(n => `<option value="${escHtml(n)}">`).join('');
        });
    }
}
