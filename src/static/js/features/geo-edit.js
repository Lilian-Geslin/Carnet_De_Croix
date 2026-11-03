// Renommage et suppression des lieux (pays, département, localisation, site, secteur, sous-secteur) dans l'arbre du Carnet.
//
// Les boutons crayon (.btn-node-edit) et corbeille (.btn-node-del) de chaque nœud portent data-table, data-id et
// data-name. L'API correspondante est /api/geo/<table>/<id> (PUT pour renommer, DELETE pour supprimer ;
// voir routes/api_geo.py). Après une modification réussie, la page est rechargée.

// Branche les boutons de renommage / suppression (délégation d'événements : un seul écouteur sur la page).
function initGeoEdit() {
    // ── RENOMMAGE / SUPPRESSION GEO ──
    document.addEventListener('click', e => {
        // Clic sur le crayon : pré-remplit et ouvre la fenêtre de renommage. Le « ressenti de cotation » n'existe que pour un secteur ou un sous-secteur.
        const editBtn = e.target.closest('.btn-node-edit');
        if (editBtn) {
            e.stopPropagation();
            const table = editBtn.dataset.table;
            document.getElementById('renameTable').value = table;
            document.getElementById('renameId').value    = editBtn.dataset.id;
            document.getElementById('renameInput').value = editBtn.dataset.name;
            document.getElementById('renameModalTitle').textContent = `Renommer « ${editBtn.dataset.name} »`;

            const ressentiRow = document.getElementById('renameRessentiRow');
            const ressentiSel = document.getElementById('renameRessenti');
            if (table === 'secteur' || table === 'sous_secteur') {
                ressentiRow.style.display = '';
                ressentiSel.value = editBtn.dataset.ressenti || '';
            } else {
                ressentiRow.style.display = 'none';
                ressentiSel.value = '';
            }

            openModal('renameModalOverlay');
        }
    });

    document.addEventListener('click', async e => {
        // Clic sur la corbeille : après confirmation, supprime le lieu avec tout ce qu'il contient (sous-lieux et ascensions).
        const delBtn = e.target.closest('.btn-node-del');
        if (delBtn) {
            e.stopPropagation();
            const name  = delBtn.dataset.name;
            const table = delBtn.dataset.table;
            const id    = delBtn.dataset.id;
            if (!confirm(`Supprimer « ${name} » et tout ce qu'il contient ?`)) return;
            const res  = await fetch(`/api/geo/${table}/${id}`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                // Nettoie l'état mémorisé de l'accordéon pour ce nœud supprimé
                try {
                    const key = `${table}-node-${id}`;
                    const openNodes = new Set(JSON.parse(localStorage.getItem('carnet_open_nodes') || '[]'));
                    openNodes.delete(key);
                    localStorage.setItem('carnet_open_nodes', JSON.stringify([...openNodes]));
                } catch { /* ignore */ }
                location.reload();
            }
        }
    });

    // Fermeture de la fenêtre de renommage : bouton ×, ou clic à côté de la fenêtre.
    const btnCloseRename  = document.getElementById('btnCloseRenameModal');
    const renameModalOverlay = document.getElementById('renameModalOverlay');
    if (btnCloseRename)      btnCloseRename.addEventListener('click', () => closeModal('renameModalOverlay'));
    if (renameModalOverlay)  renameModalOverlay.addEventListener('click', e => { if (e.target === renameModalOverlay) closeModal('renameModalOverlay'); });

    // Validation du renommage : un nom déjà pris au même endroit est refusé par le serveur (erreur 409) et affiché.
    const btnSubmitRename = document.getElementById('btnSubmitRename');
    if (btnSubmitRename) {
        btnSubmitRename.addEventListener('click', async () => {
            const table   = document.getElementById('renameTable').value;
            const id      = document.getElementById('renameId').value;
            const newName = document.getElementById('renameInput').value.trim();
            if (!newName) { alert('Le nom ne peut pas être vide.'); return; }
            const payload = { name: newName };
            if (table === 'secteur' || table === 'sous_secteur') {
                payload.ressenti = document.getElementById('renameRessenti').value || null;
            }
            const res  = await fetch(`/api/geo/${table}/${id}`, {
                method: 'PUT',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) { closeModal('renameModalOverlay'); location.reload(); }
            else if (data.error) alert(data.error);
        });
    }
}
