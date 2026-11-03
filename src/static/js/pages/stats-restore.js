// Page Stats : bouton « Restaurer une sauvegarde » de la base de données.
//
// Envoie le fichier .db choisi à POST /restore (routes/exports.py → services/backup.py), qui le vérifie puis remplace
// la base en gardant une copie de secours. Opération irréversible côté navigateur : une confirmation est demandée.

// Branche le bouton et le sélecteur de fichier (cachés), s'ils existent sur la page.
function initRestoreDb() {
    // ── RESTAURATION DE LA BASE (page Stats) ──
    const btnRestoreDb    = document.getElementById('btnRestoreDb');
    const restoreFileInput = document.getElementById('restoreFileInput');
    if (btnRestoreDb && restoreFileInput) {
        btnRestoreDb.addEventListener('click', () => restoreFileInput.click());

        restoreFileInput.addEventListener('change', async () => {
            const file = restoreFileInput.files[0];
            if (!file) return;

            const confirmed = confirm(
                `Restaurer « ${file.name} » va remplacer TOUTE la base actuelle (tous les comptes). ` +
                `Cette action est irréversible (une copie de secours de l'ancienne base sera tout de même gardée sur le serveur). Continuer ?`
            );
            if (!confirmed) {
                restoreFileInput.value = '';
                return;
            }

            const formData = new FormData();
            formData.append('dbfile', file);

            btnRestoreDb.disabled = true;
            btnRestoreDb.textContent = 'Restauration en cours…';

            try {
                const res  = await fetch('/restore', { method: 'POST', body: formData });
                const data = await res.json();
                if (data.success) {
                    alert('Base restaurée avec succès. La page va se recharger.');
                    location.reload();
                } else {
                    alert(data.error || 'Erreur lors de la restauration.');
                    btnRestoreDb.disabled = false;
                    btnRestoreDb.textContent = '⬆ Restaurer une sauvegarde';
                }
            } catch (err) {
                alert('Erreur réseau lors de la restauration.');
                btnRestoreDb.disabled = false;
                btnRestoreDb.textContent = '⬆ Restaurer une sauvegarde';
            }
            restoreFileInput.value = '';
        });
    }
}
