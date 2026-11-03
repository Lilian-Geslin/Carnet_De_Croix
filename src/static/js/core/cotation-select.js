// Sélecteurs de cotation : bouton « / » pour la cotation « entre deux ».

// ─── COTATION « ENTRE DEUX » : petit bouton « / » à côté des sélecteurs de cotation ────────────
// Le sélecteur garde toujours la valeur complète (7a/+) : tout le reste du code lit simplement .value.
// Liste des sélecteurs CSS des <select> de cotation à enrichir.
const COTATION_SELECTORS = '#fCotation, #fCotationPerso, #fCotationBasse, #fCotationHaute, .l-cotation, .l-cotation-perso, #logCotPerso, #repCotPerso';
// Accès à la propriété .value d'origine d'un <select> (on la surcharge plus bas).
const nativeSelectValue = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');

// Ajoute le bouton « / » à un sélecteur : bascule entre cotations simples (7a) et « entre deux » (7a/+).
function enhanceCotationSelect(sel) {
    if (sel._cot) return;
    const lastBase = GRADE_ORDER_JS[GRADE_ORDER_JS.length - 1];
    let between = (nativeSelectValue.get.call(sel) || '').includes('/');
    sel._cot = true;

    const btn = document.createElement('button');
    btn.type = 'button'; btn.className = 'cot-slash'; btn.textContent = '/';
    btn.title = 'Cotation entre deux (ex. 7a/+ ou 7a+/b)';
    btn.setAttribute('aria-label', 'Cotation entre deux');
    const wrap = document.createElement('span'); wrap.className = 'cot-wrap';
    sel.parentNode.insertBefore(wrap, sel);
    wrap.append(sel, btn);

    const ph = [...sel.options].find(o => o.value === '');
    const phHtml = ph ? ph.outerHTML : '<option value="">—</option>';
    // Reconstruit la liste d'options selon le mode (simple ou entre deux).
    const renderOptions = () => {
        const list = between ? GRADE_BETWEEN_JS : GRADE_ORDER_JS;
        sel.innerHTML = phHtml + list.map(g => `<option value="${g}">${g}</option>`).join('');
    };
    // Met à jour l'état du bouton ; désactivé pour la plus haute cotation (rien au-dessus).
    const sync = () => {
        const v = nativeSelectValue.get.call(sel);
        const base = v.split('/')[0];
        btn.classList.toggle('on', between);
        btn.setAttribute('aria-pressed', between ? 'true' : 'false');
        btn.disabled = base === lastBase;                 // 9c : pas de cotation au-dessus
    };
    // Les affectations en JS (sel.value = '7a/+') choisissent aussi le bon mode
    Object.defineProperty(sel, 'value', {
        configurable: true,
        get() { return nativeSelectValue.get.call(sel); },
        set(v) {
            v = v || '';
            const wantBetween = v.includes('/');
            if (wantBetween !== between || ![...sel.options].some(o => o.value === v)) { between = wantBetween; renderOptions(); }
            nativeSelectValue.set.call(sel, v); sync();
        }
    });
    // Clic : change de mode en convertissant la valeur déjà choisie.
    btn.addEventListener('click', () => {
        const v = nativeSelectValue.get.call(sel);
        between = !between; renderOptions();
        if (v) {
            const next = between ? betweenGrade(v) : v.split('/')[0];
            nativeSelectValue.set.call(sel, next || '');
        }
        sync();
        sel.dispatchEvent(new Event('change', { bubbles: true }));
    });
    sel.addEventListener('change', sync);
    const initial = nativeSelectValue.get.call(sel);
    renderOptions(); nativeSelectValue.set.call(sel, initial); sync();
}
// Enrichit un élément et tous ses descendants qui sont des sélecteurs de cotation.
function enhanceCotationIn(root) {
    if (root.nodeType !== 1) return;
    if (root.matches && root.matches(COTATION_SELECTORS)) enhanceCotationSelect(root);
    root.querySelectorAll && root.querySelectorAll(COTATION_SELECTORS).forEach(enhanceCotationSelect);
}
// Au chargement, enrichit la page, puis surveille les éléments ajoutés plus tard (fenêtres, lignes dynamiques).
(function initCotationEnhancer() {
    const start = () => {
        enhanceCotationIn(document.body);
        new MutationObserver(muts => muts.forEach(m => m.addedNodes.forEach(enhanceCotationIn)))
            .observe(document.body, { childList: true, subtree: true });
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
