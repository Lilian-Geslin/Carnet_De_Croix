// Saisie de la note de beauté sous forme d'étoiles cliquables.
//
// Le conteneur (div) mémorise la note dans `data-val` (0 = pas de note) ; les formulaires lisent cette valeur
// à l'enregistrement. Utilisé par les fenêtres d'ajout, de répétition et de passage au carnet.

// ─── STAR INPUT ────────────────────────────────────────────────────────────────

// Remplit `container` avec 5 étoiles : clic = choisir la note, survol = aperçu. Sans effet si le conteneur est absent.
function initStarInput(container) {
    if (!container) return;
    container.innerHTML = '';
    for (let i = 1; i <= 5; i++) {
        const span = document.createElement('span');
        span.className = 'star';
        span.textContent = '★';
        span.dataset.val = i;
        span.addEventListener('click', () => { container.dataset.val = i; updateStars(container); });
        span.addEventListener('mouseenter', () => highlightStars(container, i));
        span.addEventListener('mouseleave', () => updateStars(container));
        container.appendChild(span);
    }
    updateStars(container);
}

// Affiche en « allumées » les étoiles jusqu'à la note enregistrée dans `data-val`.
function updateStars(container) {
    const val = parseInt(container.dataset.val) || 0;
    container.querySelectorAll('.star').forEach((s, i) => s.classList.toggle('active', i < val));
}

// Aperçu au survol : allume les `n` premières étoiles sans modifier la note enregistrée.
function highlightStars(container, n) {
    container.querySelectorAll('.star').forEach((s, i) => s.classList.toggle('active', i < n));
}
