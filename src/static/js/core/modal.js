// Fenêtres modales : ouverture, fermeture et blocage du défilement de la page.
//
// Une modale est un bloc `.modal-overlay` (défini dans les templates, cf. templates/partials) qu'on affiche en
// lui ajoutant la classe `open`. Toutes les fonctions de ce fichier sont globales : les autres scripts
// (features/*, pages/*) les appellent par leur id de modale.

// ─── MODAL HELPERS ─────────────────────────────────────────────────────────────

// Bloque (ou débloque) le défilement de la page selon qu'au moins une modale est ouverte.
// Appelée à chaque ouverture/fermeture ; la classe `modal-open` est utilisée par le CSS (layout.css).
// Tant qu'une fenêtre est ouverte, la page (carnet) derrière ne défile plus
function syncScrollLock() {
    const anyOpen = !!document.querySelector('.modal-overlay.open');
    const root = document.documentElement;
    if (anyOpen && !root.classList.contains('modal-open')) {
        const gap = window.innerWidth - root.clientWidth;       // évite le « saut » quand la barre de défilement disparaît
        root.style.setProperty('--scrollbar-gap', gap > 0 ? gap + 'px' : '0px');
        root.classList.add('modal-open');
    } else if (!anyOpen) {
        root.classList.remove('modal-open');
    }
}
// Affiche la modale d'identifiant `id` et bloque le défilement de la page.
function openModal(id) {
    document.getElementById(id).classList.add('open');
    syncScrollLock();
}
// Cache la modale d'identifiant `id` et rend le défilement si plus aucune n'est ouverte.
function closeModal(id) {
    document.getElementById(id).classList.remove('open');
    syncScrollLock();
}
