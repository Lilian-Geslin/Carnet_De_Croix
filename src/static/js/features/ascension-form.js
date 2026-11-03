// Formulaire d'ascension : construction du HTML, formulaire des longueurs d'une grande voie, collecte des données.
//
// Utilisé par la fenêtre d'ajout / modification (ascension-modal.js) et par les pages Projets et Tick List.
// Le formulaire change selon le type d'ascension (bloc, voie, grande voie…) et le statut (log, projet, ticklist).
// Les valeurs saisies sont renvoyées à l'API /api/ascension (routes/api_ascensions.py) par collectPayload().

// ─── FORM BUILDER ──────────────────────────────────────────────────────────────

// Construit le HTML du formulaire (étape 2 de la fenêtre d'ajout).
//   type    : bloc, voie, grande_voie, trad_voie, trad_gv ou psychobloc
//   statut  : log (réalisée), projet ou ticklist (envie) ; change les champs proposés
//   prefill : valeurs à pré-remplir (modification d'une ascension existante)
// Règles : départ/arrivée seulement pour les blocs ; « en tête / moulinette » pour tout ce qui se grimpe
// sur corde (obligatoire pour un log) ; fourchette de cotations pour les grandes voies ; nombre d'essais, date,
// pieds nus et note de beauté seulement pour un log ; essais déjà faits et date de séance pour un projet.
function buildForm(type, statut, prefill = {}) {
    const isProjet   = statut === 'projet';
    const isTicklist = statut === 'ticklist';
    const isGV       = type === 'grande_voie' || type === 'trad_gv';
    const isBloc     = type === 'bloc' || type === 'psychobloc';
    const isVoie     = !isBloc;

    const gradeOpts = gradeOptionsHtml(prefill.cotation);
    const gradeOptsPerso = gradeOptionsHtml(prefill.cotation_perso);

    // Choix du nombre d'essais pour les blocs et les voies (valeurs = clés de STYLE_ORDER côté serveur).
    const essaisOpts = (sel) => `
        <option value="">—</option>
        <option value="a_vue" ${sel==='a_vue'?'selected':''}>À vue</option>
        <option value="flash" ${sel==='flash'?'selected':''}>Flash</option>
        <option value="essais_1" ${sel==='essais_1'?'selected':''}>1 essai</option>
        <option value="essais_2" ${sel==='essais_2'?'selected':''}>2 essais</option>
        <option value="essais_3" ${sel==='essais_3'?'selected':''}>3 essais</option>
        <option value="essais_4" ${sel==='essais_4'?'selected':''}>4 essais</option>
        <option value="essais_5" ${sel==='essais_5'?'selected':''}>5 essais</option>
        <option value="plus_5" ${sel==='plus_5'?'selected':''}>Plus de 5 essais</option>`;

    // Choix du nombre d'essais, version simplifiée pour une grande voie (essais_2 = « Plusieurs essais », plus_5 = « Après travail »).
    const essaisOptsGV = (sel) => `
        <option value="">—</option>
        <option value="a_vue" ${sel==='a_vue'?'selected':''}>À vue</option>
        <option value="flash" ${sel==='flash'?'selected':''}>Flash</option>
        <option value="essais_1" ${sel==='essais_1'?'selected':''}>1 essai</option>
        <option value="essais_2" ${sel==='essais_2'?'selected':''}>Plusieurs essais</option>
        <option value="plus_5" ${sel==='plus_5'?'selected':''}>Après travail</option>`;

    let html = `<h3>Informations</h3>`;
    html += `<div class="form-row"><label>Nom</label><input type="text" id="fNom" placeholder="Nom de l'ascension" value="${escHtml(prefill.nom)}" list="listNoms" autocomplete="off" required><datalist id="listNoms">${NOMS_CACHE.ascensions.map(n => `<option value="${escHtml(n)}">`).join('')}</datalist></div>`;

    if (isBloc) {
        const td = prefill.type_depart || 'normal';
        html += `<div class="form-row"><label>Type de départ</label>
        <select id="fTypeDepart">
            <option value="normal" ${td==='normal'?'selected':''}>Normal</option>
            <option value="assis"    ${td==='assis'?'selected':''}>Départ assis</option>
            <option value="jete"     ${td==='jete'?'selected':''}>Jeté</option>
            <option value="run_jump" ${td==='run_jump'?'selected':''}>Run & Jump</option>
        </select></div>`;
        const ta = prefill.type_arrivee || 'normal';
        html += `<div class="form-row"><label>Type d'arrivée</label>
        <select id="fTypeArrivee">
            <option value="normal" ${ta==='normal'?'selected':''}>Normal top</option>
            <option value="reta"   ${ta==='reta'?'selected':''}>Reta</option>
        </select></div>`;
    }

    // Grande voie : cotation sur une plage basse → haute (la cotation alpine s'en déduit) ; sinon une seule cotation.
    if (isGV) {
        html += cotationRangeHtml(prefill.cotation, prefill.cotation_haute);
        html += `<div class="form-row"><label>Ma cotation</label><select id="fCotationPerso"><option value="">—</option>${gradeOptsPerso}</select></div>`;
    } else {
        html += `<div class="form-row"><label>Cotation</label><select id="fCotation"><option value="">—</option>${gradeOpts}</select></div>`;
        html += `<div class="form-row"><label>Ma cotation</label><select id="fCotationPerso"><option value="">—</option>${gradeOptsPerso}</select></div>`;
    }

    // Tick list : catégorie facultative (Performance, Beauté, Majeure) ; ENVIE_CATS est défini par la page Tick List.
    if (isTicklist) {
        const cats = (typeof ENVIE_CATS !== 'undefined' ? ENVIE_CATS : {});
        html += `<div class="form-row"><label>Catégorie <span class="optional-tag">(optionnel)</span></label>
        <select id="fEnvieCat"><option value="">—</option>${Object.entries(cats).map(([k, v]) => `<option value="${k}" ${prefill.envie_categorie === k ? 'selected' : ''}>${v}</option>`).join('')}</select></div>`;
    }

    // Voies, grandes voies et trad : mode de grimpe. Il est obligatoire pour un log (le serveur le vérifie aussi) car seules les ascensions « en tête » comptent dans les stats.
    if (isVoie) {
        const gr = prefill.grimpe || '';
        html += `<div class="form-row"><label>En tête / Moulinette${statut === 'log' ? ' <span class="req-star" title="Obligatoire">*</span>' : ''}</label>
        <select id="fGrimpe">
            <option value="">—</option>
            <option value="tete"       ${gr==='tete'?'selected':''}>En tête</option>
            <option value="moulinette" ${gr==='moulinette'?'selected':''}>Moulinette</option>
        </select></div>`;
    }

    if (isGV) {
        html += `<div class="form-row"><label>Nb. longueurs</label><input type="number" id="fNbLongueurs" min="1" max="50" value="${prefill.nb_longueurs || ''}"></div>`;
        html += `<div id="longeursContainer" class="longueurs-form-container"></div>`;
    }

    if (!isProjet && !isTicklist) {
        html += `<div class="form-row"><label>Nombre d'essais</label>
        <select id="fStyle">${isGV ? essaisOptsGV(prefill.style) : essaisOpts(prefill.style)}</select></div>`;
        html += `<div class="form-row"><label>Date</label><input type="date" id="fDate" value="${prefill.date || ''}"></div>`;
        html += `<div class="form-row checkbox-row"><label><input type="checkbox" id="fPiedsNus" ${prefill.pieds_nus ? 'checked' : ''}> Pieds nus</label></div>`;
        html += `<div class="form-row"><label>Note beauté</label><div class="star-input" id="fStars" data-val="${prefill.note_beaute || 0}"></div></div>`;
    } else if (isProjet) {
        html += `<div class="form-row"><label>Essais déjà faits</label><input type="number" id="fNbEssaisProjet" min="0" max="999" value="${prefill.nb_essais_projet || 0}" title="S'ils sont supérieurs à 0, ils forment la séance n°1 du projet"></div>`;
        html += `<div class="form-row"><label>Date de la séance</label><input type="date" id="fDateSeance" title="Date de ces essais (séance n°1). Laisse vide si tu ne la connais pas."></div>`;
    }

    html += `<div class="form-row"><label>Hauteur (m)</label><input type="number" id="fHauteur" step="0.5" min="0" value="${prefill.hauteur || ''}"></div>`;
    html += `<div class="form-row"><label>Commentaire</label><textarea id="fCommentaire" rows="2">${escHtml(prefill.commentaire)}</textarea></div>`;

    return html;
}

// Construit un bloc de saisie par longueur d'une grande voie (cotation, mode, essais, hauteur, pieds nus, note).
//   n                 : nombre de longueurs (champ « Nb. longueurs »)
//   prefillLongueurs  : longueurs existantes à pré-remplir en modification
function buildLongueursForm(n, prefillLongueurs = []) {
    const container = document.getElementById('longeursContainer');
    if (!container) return;
    container.innerHTML = '';
    const gradeOpts = gradeOptionsHtml();
    const essaisOpts = `
        <option value="">—</option>
        <option value="a_vue">À vue</option>
        <option value="flash">Flash</option>
        <option value="essais_1">1 essai</option>
        <option value="essais_2">2 essais</option>
        <option value="essais_3">3 essais</option>
        <option value="essais_4">4 essais</option>
        <option value="essais_5">5 essais</option>
        <option value="plus_5">Plus de 5</option>`;

    for (let i = 0; i < n; i++) {
        const pf = prefillLongueurs[i] || {};
        container.innerHTML += `
        <div class="longueur-form-block">
            <h4>Longueur ${i+1}</h4>
            <div class="form-row"><label>Cotation</label><select class="l-cotation"><option value="">—</option>${gradeOpts.replace(`value="${pf.cotation}"`, `value="${pf.cotation}" selected`)}</select></div>
            <div class="form-row"><label>Ma cotation</label><select class="l-cotation-perso"><option value="">—</option>${gradeOpts.replace(`value="${pf.cotation_perso}"`, `value="${pf.cotation_perso}" selected`)}</select></div>
            <div class="form-row"><label>En tête / Moulinette</label>
            <select class="l-grimpe">
                <option value="">—</option>
                <option value="tete" ${pf.grimpe==='tete'?'selected':''}>En tête</option>
                <option value="moulinette" ${pf.grimpe==='moulinette'?'selected':''}>Moulinette</option>
            </select></div>
            <div class="form-row"><label>Nombre d'essais</label><select class="l-style">${essaisOpts}</select></div>
            <div class="form-row"><label>Hauteur (m)</label><input class="l-hauteur" type="number" step="0.5" min="0" value="${pf.hauteur || ''}"></div>
            <div class="form-row checkbox-row"><label><input class="l-pieds" type="checkbox" ${pf.pieds_nus?'checked':''}> Pieds nus</label></div>
            <div class="form-row"><label>Note beauté</label><div class="star-input l-stars" data-val="${pf.note_beaute || 0}"></div></div>
        </div>`;
    }
    container.querySelectorAll('.l-stars').forEach(el => initStarInput(el));
    // Sélectionner le style de chaque longueur après injection
    container.querySelectorAll('.longueur-form-block').forEach((block, i) => {
        const pf = prefillLongueurs[i] || {};
        const sel = block.querySelector('.l-style');
        if (sel && pf.style) sel.value = pf.style;
    });
}

// Nombre d'essais correspondant à un style : à vue / flash = 1, essais_N = N, plus_5 = 6 (> 5)
// Correspondance style → nombre d'essais, utilisée pour pré-remplir les essais d'une répétition ou d'un projet.
function essaisFromStyle(style) {
    if (style === 'a_vue' || style === 'flash') return 1;
    if (style === 'plus_5') return 6;
    const m = /^essais_(\d)$/.exec(style || '');
    return m ? parseInt(m[1]) : 0;
}
// Inverse : nombre d'essais → style (plus de 5 essais = « plus_5 ») ; null si aucun essai.
function essaisToStyle(n) {
    if (n <= 0) return null;
    return n > 5 ? 'plus_5' : 'essais_' + n;
}

// Lit le formulaire (lieu + ascension + longueurs) et renvoie l'objet JSON envoyé au serveur.
// Les champs vides deviennent null ; localisation et secteur valent « Principale » / « Principal » par défaut.
function collectPayload(type, statut, editId = null) {
    const starsEl = document.getElementById('fStars');
    const isGV = type === 'grande_voie' || type === 'trad_gv';
    const payload = {
        pays:             document.getElementById('inputPays')?.value.trim()        || '',
        departement:      document.getElementById('inputDepartement')?.value.trim() || '',
        localisation:     document.getElementById('inputLocalisation')?.value.trim() || 'Principale',
        site:             document.getElementById('inputSite')?.value.trim()        || '',
        secteur:          document.getElementById('inputSecteur')?.value.trim()     || 'Principal',
        sous_secteur:     document.getElementById('inputSousSecteur')?.value.trim() || null,
        ressenti:         document.getElementById('inputRessenti')?.value          || null,
        type, statut,
        nom:              document.getElementById('fNom')?.value.trim()             || '',
        cotation:         isGV
                              ? (document.getElementById('fCotationBasse')?.value || null)
                              : (document.getElementById('fCotation')?.value      || null),
        cotation_haute:   isGV ? (document.getElementById('fCotationHaute')?.value || null) : null,
        cotation_perso:   document.getElementById('fCotationPerso')?.value          || null,
        style:            document.getElementById('fStyle')?.value                  || null,
        grimpe:           document.getElementById('fGrimpe')?.value                 || null,
        envie_categorie:  document.getElementById('fEnvieCat')?.value               || null,
        pieds_nus:        document.getElementById('fPiedsNus')?.checked             || false,
        hauteur:          parseFloat(document.getElementById('fHauteur')?.value)    || null,
        note_beaute:      starsEl ? parseInt(starsEl.dataset.val) || null : null,
        date:             document.getElementById('fDate')?.value                   || null,
        commentaire:      document.getElementById('fCommentaire')?.value            || null,
        type_depart:      document.getElementById('fTypeDepart')?.value             || null,
        type_arrivee:     document.getElementById('fTypeArrivee')?.value            || null,
        nb_longueurs:     parseInt(document.getElementById('fNbLongueurs')?.value)  || null,
        nb_essais_projet: parseInt(document.getElementById('fNbEssaisProjet')?.value) || 0,
        date_seance:      document.getElementById('fDateSeance')?.value || null,
    };
    // Grande voie : on joint la liste des longueurs saisies (numérotées dans l'ordre par le serveur).
    const longeursContainer = document.getElementById('longeursContainer');
    if (longeursContainer && longeursContainer.children.length > 0) {
        const blocks = longeursContainer.querySelectorAll('.longueur-form-block');
        payload.longueurs = Array.from(blocks).map(b => {
            const s = b.querySelector('.l-stars');
            return {
                cotation:       b.querySelector('.l-cotation')?.value       || null,
                cotation_perso: b.querySelector('.l-cotation-perso')?.value || null,
                style:          b.querySelector('.l-style')?.value           || null,
                grimpe:         b.querySelector('.l-grimpe')?.value          || null,
                pieds_nus:      b.querySelector('.l-pieds')?.checked         || false,
                hauteur:        parseFloat(b.querySelector('.l-hauteur')?.value) || null,
                note_beaute:    s ? parseInt(s.dataset.val) || null : null,
            };
        });
    }
    return payload;
}
