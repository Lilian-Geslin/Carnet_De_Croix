// Cotations côté navigateur : échelle technique, cotation « entre deux » et cotation alpine.
//
// Reproduit les règles de src/services/grades.py (le serveur reste la référence ; les tests vérifient le côté Python).
// Fournit aussi le HTML du double sélecteur « cotation basse → haute » des grandes voies.

// ─── COTATION ALPINE (Grande Voie / Trad GV) ───────────────────────────────────
// La cotation générale d'une grande voie se choisit comme une PLAGE (basse → haute)
// sur l'échelle technique classique. La cotation alpine (F, PD, AD-...) en est
// déduite automatiquement à partir de la cotation haute (le passage obligé).

// Échelle des cotations de 3a à 9c, de la plus facile à la plus dure (même ordre que GRADE_ORDER côté Python).
const GRADE_ORDER_JS = [
    '3a', '3a+', '3b', '3b+', '3c', '3c+',
    '4a', '4a+', '4b', '4b+', '4c', '4c+',
    '5a', '5a+', '5b', '5b+', '5c', '5c+',
    '6a', '6a+', '6b', '6b+', '6c', '6c+',
    '7a', '7a+', '7b', '7b+', '7c', '7c+',
    '8a', '8a+', '8b', '8b+', '8c', '8c+',
    '9a', '9a+', '9b', '9b+', '9c'
];

// Points de repère cotation alpine ↔ cotation technique : à partir de l'ancre, on est dans la cotation alpine indiquée
// (ex. 5a et plus = « D- », 6b et plus = « TD »). En dessous de 3a on reste à « PD ».
const ALPINE_ANCHORS = [
    ['PD',   '3a'],
    ['AD-',  '4a'],
    ['AD',   '4b'],
    ['AD+',  '4c'],
    ['D-',   '5a'],
    ['D',    '5b'],
    ['D+',   '5c'],
    ['TD-',  '6a'],
    ['TD',   '6b'],
    ['TD+',  '6c'],
    ['ED-',  '7a'],
    ['ED',   '7b'],
    ['ED+',  '7c'],
    ['ABO-', '8a'],
    ['ABO',  '8b'],
    ['ABO+', '8c'],
];

// Cotation « entre deux » d'une cotation : 7a → 7a/+, 7a+ → 7a+/b, 7c+ → 7c+/8a. Renvoie null pour la dernière (9c)
// ou pour une valeur inconnue. Si `g` est déjà « entre deux » (7a/+), seule la partie avant « / » est lue.
// Cotation « entre deux » : 7a -> 7a/+ ; 7a+ -> 7a+/b ; 7c+ -> 7c+/8a. La dernière cotation n'en a pas.
function betweenGrade(g) {
    const i = GRADE_ORDER_JS.indexOf(String(g || '').split('/')[0]);
    if (i < 0 || i >= GRADE_ORDER_JS.length - 1) return null;
    const base = GRADE_ORDER_JS[i], next = GRADE_ORDER_JS[i + 1];
    if (!base.endsWith('+')) return base + '/+';
    return base + '/' + (next[0] === base[0] ? next.slice(1) : next);
}
// Toutes les cotations « entre deux » possibles, dans l'ordre.
const GRADE_BETWEEN_JS = GRADE_ORDER_JS.map(betweenGrade).filter(Boolean);
// Liste complète proposée dans les sélecteurs : chaque cotation suivie de sa version « entre deux » (7a, 7a/+, 7a+, 7a+/b…).
const GRADE_FULL_JS = GRADE_ORDER_JS.flatMap(g => { const b = betweenGrade(g); return b ? [g, b] : [g]; });
// HTML des <option> de la liste complète, avec `selected` coché sur la cotation déjà choisie.
const gradeOptionsHtml = (selected) => GRADE_FULL_JS
    .map(g => `<option value="${g}" ${selected === g ? 'selected' : ''}>${g}</option>`).join('');

// Cotation alpine (PD, AD-, …, ABO+) déduite d'une cotation technique ; null si elle est vide ou inconnue.
// Une cotation « entre deux » (7a/+) compte comme son niveau avant le « / ».
function alpineFromClassic(grade) {
    if (!grade) return null;
    const idx = GRADE_ORDER_JS.indexOf(String(grade).split('/')[0]);   // 7a/+ compte comme 7a
    if (idx === -1) return null;
    let result = 'PD';
    for (const [label, anchor] of ALPINE_ANCHORS) {
        if (GRADE_ORDER_JS.indexOf(anchor) <= idx) result = label;
        else break;
    }
    return result;
}

/**
 * Construit le bloc "Cotation générale" pour une Grande Voie : deux sélecteurs
 * (basse / haute) sur l'échelle classique, plus un badge qui affiche en direct
 * la cotation alpine correspondante (déduite de la cotation haute).
 */
function cotationRangeHtml(basseSel, hauteSel) {
    const opts = gradeOptionsHtml;
    const alpine = alpineFromClassic(hauteSel) || '—';
    return `
    <div class="form-row">
        <label>Cotation générale (basse → haute)</label>
        <div class="cotation-range-row">
            <select id="fCotationBasse"><option value="">—</option>${opts(basseSel)}</select>
            <span class="cotation-range-arrow">→</span>
            <select id="fCotationHaute"><option value="">—</option>${opts(hauteSel)}</select>
            <span class="cotation-range-alpine" id="fCotationAlpinePreview">${alpine}</span>
        </div>
    </div>`;
}

/** Branche la mise à jour en direct du badge alpin quand basse/haute changent. */
function wireCotationRangePreview() {
    const basse  = document.getElementById('fCotationBasse');
    const haute  = document.getElementById('fCotationHaute');
    const preview = document.getElementById('fCotationAlpinePreview');
    if (!basse || !haute || !preview) return;
    const update = () => { preview.textContent = alpineFromClassic(haute.value) || '—'; };
    basse.addEventListener('change', update);
    haute.addEventListener('change', update);
}
