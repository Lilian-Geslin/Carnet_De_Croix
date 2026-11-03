// Répétitions d'une ascension (refaire une voie ou un bloc déjà fait) et suppression d'ascensions / de répétitions.
//
// Fenêtre #repModalOverlay (partials/modal_repetition.html). Une répétition n'est pas une nouvelle ascension : elle
// n'ajoute que des mètres dans les stats (et seulement si elle compte : en tête pour les voies et le trad (voie)).
// API : POST /api/repetition, DELETE /api/repetition/<id> et DELETE /api/ascension/<id>.

// Branche l'ouverture, l'envoi et la suppression des répétitions, ainsi que la suppression d'une ascension.
function initRepetitions() {
    // ── MODAL RÉPÉTITION ──
    const repModalOverlay = document.getElementById('repModalOverlay');
    const btnCloseRep     = document.getElementById('btnCloseRepModal');

    if (repModalOverlay) {
        // Mode de grimpe d'une répétition : obligatoire pour les voies (pas pour les blocs)
        // Types qui se grimpent sur corde : ils demandent « en tête / moulinette ».
        const ROPE = ['voie', 'grande_voie', 'trad_voie', 'trad_gv'];
        // Affiche (ou cache) la ligne « en tête / moulinette » selon le type, et y met la valeur donnée.
        const setRepGrimpe = (type, value) => {
            const row = document.getElementById('repGrimpeRow');
            if (!row) return;
            row.dataset.needed = ROPE.includes(type) ? '1' : '';
            row.style.display = ROPE.includes(type) ? 'flex' : 'none';
            document.getElementById('repGrimpe').value = value || '';
        };
        // Ouvre le questionnaire de répétition, éventuellement pré-rempli (doublon détecté à l'ajout)
        // Utilisée par la fenêtre d'ajout quand elle détecte un doublon : ouvre la répétition avec les données déjà saisies
        // (essaisMap convertit le style de l'ascension en nombre d'essais de la répétition).
        window.openRepModalPrefilled = (ascId, p = {}) => {
            const essaisMap = { a_vue:'1', flash:'1', essais_1:'1', essais_2:'2', essais_3:'3', essais_4:'4', essais_5:'5', plus_5:'plus_5' };
            document.getElementById('repAscId').value      = ascId;
            document.getElementById('repDate').value       = p.date || '';
            document.getElementById('repEssais').value     = essaisMap[p.style] || '';
            document.getElementById('repCotPerso').value   = p.cotation_perso || '';
            document.getElementById('repPiedsNus').checked = !!p.pieds_nus;
            document.getElementById('repComment').value    = p.commentaire || '';
            setRepGrimpe(p.type, p.grimpe);
            const s = document.getElementById('repStars');
            if (s) { s.dataset.val = p.note_beaute || 0; updateStars(s); }
            openModal('repModalOverlay');
        };

        // Bouton « répétition » d'une ascension : ouvre la fenêtre vide pour cette ascension.
        document.addEventListener('click', e => {
            const btn = e.target.closest('.btn-rep');
            if (!btn) return;
            document.getElementById('repAscId').value    = btn.dataset.ascId;
            document.getElementById('repDate').value     = '';
            document.getElementById('repEssais').value   = '';
            document.getElementById('repCotPerso').value = '';
            document.getElementById('repPiedsNus').checked = false;
            document.getElementById('repComment').value  = '';
            setRepGrimpe(btn.dataset.type, '');
            const s = document.getElementById('repStars');
            if (s) { s.dataset.val = 0; updateStars(s); }
            openModal('repModalOverlay');
        });

        if (btnCloseRep) btnCloseRep.addEventListener('click', () => closeModal('repModalOverlay'));
        repModalOverlay.addEventListener('click', e => { if (e.target === repModalOverlay) closeModal('repModalOverlay'); });

        // Envoi de la répétition : la date est obligatoire, et le mode en tête / moulinette pour les voies.
        const btnSubmitRep = document.getElementById('btnSubmitRep');
        if (btnSubmitRep) {
            btnSubmitRep.addEventListener('click', async () => {
                const ascId = document.getElementById('repAscId').value;
                const date  = document.getElementById('repDate').value;
                if (!date) { alert('La date est requise.'); return; }
                const needGrimpe = document.getElementById('repGrimpeRow')?.dataset.needed === '1';
                const grimpeRep  = document.getElementById('repGrimpe')?.value || null;
                if (needGrimpe && !grimpeRep) { alert("Indique si c'est grimpé en tête ou en moulinette."); return; }
                const s   = document.getElementById('repStars');
                const res = await fetch('/api/repetition', {
                    method: 'POST',
                    headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({
                        ascension_id:   parseInt(ascId),
                        date,
                        nb_essais:      document.getElementById('repEssais').value    || null,
                        cotation_perso: document.getElementById('repCotPerso').value  || null,
                        pieds_nus:      document.getElementById('repPiedsNus').checked,
                        note_beaute:    s ? parseInt(s.dataset.val) || null : null,
                        commentaire:    document.getElementById('repComment').value   || null,
                        grimpe:         needGrimpe ? grimpeRep : null,
                    })
                });
                const data = await res.json();
                if (data.success) { closeModal('repModalOverlay'); location.reload(); }
                else if (data.error) alert(data.error);
            });
        }
    }

    // ── SUPPRESSION RÉPÉTITION ──
    document.addEventListener('click', async e => {
        // Corbeille d'une répétition (la même ligne se retrouve dans l'historique de l'ascension).
        const btn = e.target.closest('.btn-del-rep');
        if (!btn) return;
        if (!confirm('Supprimer cette répétition ?')) return;
        const res  = await fetch(`/api/repetition/${btn.dataset.repId}`, {method:'DELETE'});
        const data = await res.json();
        if (data.success) location.reload();
    });

    // ── SUPPRESSION ASCENSION ──
    document.addEventListener('click', async e => {
        const btn = e.target.closest('.btn-del');
        if (!btn) return;
        if (!confirm('Supprimer cette ascension ?')) return;
        const res  = await fetch(`/api/ascension/${btn.dataset.ascId}`, {method:'DELETE'});
        const data = await res.json();
        if (data.success) location.reload();
    });
}
