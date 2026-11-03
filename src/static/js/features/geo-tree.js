// Arbre géographique de la page Carnet (Pays › Département › Localisation › Site › Secteur › Ascension).
//
// Chaque niveau est un <details class="node X-node" data-id="…"> rendu par carnet.html. Ce fichier :
//   - mémorise dans localStorage les niveaux ouverts, pour les retrouver après un changement de page ;
//   - ouvre automatiquement le chemin d'un secteur juste après un ajout (variable OPEN_PATH fournie par carnet.html) ;
//   - branche les étoiles des fenêtres de répétition et de passage au carnet.

// Démarre l'arbre : état mémorisé, ouverture après ajout, étoiles. Sans effet sur une page sans arbre.
function initGeoTree() {
    // ── MÉMORISATION DES ACCORDÉONS OUVERTS (persiste entre les changements d'onglet) ──
    // Chaque <details class="X-node" data-id="Y"> sauvegarde son état dans localStorage,
    // pour rester ouvert même après un rechargement complet de la page (changement d'onglet).
    const geoTree = document.querySelector('.geo-tree');
    if (geoTree) {
        // Clé localStorage de la liste des nœuds ouverts (« type-node-id »).
        const STORAGE_KEY = 'carnet_open_nodes';

        // Identifiant unique d'un nœud, ex. « site-node-12 », fabriqué avec sa classe `X-node` et son data-id.
        function nodeKey(el) {
            const cls = [...el.classList].find(c => c.endsWith('-node'));
            return `${cls}-${el.dataset.id}`;
        }

        // Relit l'ensemble des nœuds ouverts ; ensemble vide si le stockage est absent ou illisible.
        function loadOpenNodes() {
            try {
                return new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'));
            } catch {
                return new Set();
            }
        }

        // Enregistre l'ensemble des nœuds ouverts.
        function saveOpenNodes(set) {
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify([...set]));
            } catch { /* stockage indisponible, on ignore silencieusement */ }
        }

        const openNodes = loadOpenNodes();

        geoTree.querySelectorAll('details.node').forEach(el => {
            // Rouvre les nœuds mémorisés
            if (openNodes.has(nodeKey(el))) el.open = true;

            // Sauvegarde à chaque bascule (ouverture ou fermeture manuelle)
            el.addEventListener('toggle', () => {
                const key = nodeKey(el);
                if (el.open) {
                    openNodes.add(key);
                } else {
                    openNodes.delete(key);
                    // En fermant ce nœud, referme aussi tous ses descendants
                    // et oublie leur état mémorisé (sinon ils réapparaîtraient
                    // tous ouverts la prochaine fois qu'on rouvre ce nœud).
                    el.querySelectorAll('details.node').forEach(child => {
                        child.open = false;
                        openNodes.delete(nodeKey(child));
                    });
                }
                saveOpenNodes(openNodes);
            });
        });
    }

    // ── OUVERTURE AUTOMATIQUE DU CHEMIN APRÈS AJOUT ──
    // OPEN_PATH vaut {pays_id, …, secteur_id} quand on arrive avec ?open_secteur=… (après un ajout) ; sinon il est vide.
    if (typeof OPEN_PATH !== 'undefined' && OPEN_PATH && OPEN_PATH.secteur_id) {
        const mapping = [
            { cls: 'pays-node',        id: OPEN_PATH.pays_id },
            { cls: 'departement-node', id: OPEN_PATH.departement_id },
            { cls: 'localisation-node', id: OPEN_PATH.localisation_id },
            { cls: 'site-node',        id: OPEN_PATH.site_id },
            { cls: 'secteur-node',     id: OPEN_PATH.secteur_id },
        ];
        mapping.forEach(({ cls, id }) => {
            const el = document.querySelector(`details.${cls}[data-id="${id}"]`);
            if (el) {
                el.open = true;
                // Scroll vers le secteur
                if (cls === 'secteur-node') {
                    setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'center' }), 150);
                }
            }
        });
        // Nettoie l'URL sans recharger la page
        window.history.replaceState({}, '', '/carnet');
    }

    // Étoiles des fenêtres « répétition » et « passer au carnet ».
    ['repStars', 'logStars'].forEach(id => {
        const el = document.getElementById(id);
        if (el) initStarInput(el);
    });
}
