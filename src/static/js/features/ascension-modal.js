// Fenêtre d'ajout / modification d'une ascension (#modalOverlay), en deux étapes :
//   étape 1 : lieu (pays › … › sous-secteur), type d'escalade et statut (log / projet / tick list) ;
//   étape 2 : formulaire détaillé fabriqué par buildForm() (ascension-form.js).
//
// Sert sur les pages Carnet, Projets et Tick List (celles-ci imposent le statut via un champ caché #forcedStatut).
// Envoie les données à /api/ascension (POST pour créer, PUT /api/ascension/<id> pour modifier) et gère le cas
// où l'ascension existe déjà (doublon : proposer une répétition ou le passage au carnet).

// Branche tous les boutons et champs de la fenêtre ; sans effet sur une page qui n'a pas la fenêtre.
function initAscensionModal() {
    // ── MODAL PRINCIPAL OPEN/CLOSE ──
    const modalOverlay = document.getElementById('modalOverlay');
    const btnAdd       = document.getElementById('btnAddAscension');
    const btnClose     = document.getElementById('btnCloseModal');
    const step1        = document.getElementById('step1');
    const step2        = document.getElementById('step2');
    // Identifiant de l'ascension en cours de modification ; null quand on en ajoute une nouvelle.
    let   editAscId    = null;

    // Remet la fenêtre en mode « Nouvelle ascension » : champs vidés, étape 1 affichée, statut « log » coché.
    function resetModalToAdd() {
        editAscId = null;
        document.getElementById('modalTitle').textContent = 'Nouvelle ascension';
        // Réaffiche le choix de statut (masqué en mode édition)
        const statutSection = document.getElementById('statutSection');
        if (statutSection) statutSection.style.display = '';
        // Reset champs géo
        ['inputPays','inputDepartement','inputLocalisation','inputSite','inputSecteur','inputSousSecteur','inputRessenti'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        // Reset type
        document.querySelectorAll('input[name="typeEsc"]').forEach(r => r.checked = false);
        const statutLog = document.querySelector('input[name="statut"][value="log"]');
        if (statutLog) statutLog.checked = true;
        step1.style.display = 'block';
        step2.style.display = 'none';
    }

    // Bouton « + Ajouter » du haut de page : ouvre la fenêtre vide.
    if (btnAdd && modalOverlay) {
        btnAdd.addEventListener('click', async () => {
            resetModalToAdd();
            openModal('modalOverlay');
            await loadPaysOptions();
        });
    }

    // ── BOUTON + SUR CHAQUE NIVEAU GÉO ──
    // Bouton « + » présent sur chaque niveau de l'arbre : ouvre la fenêtre avec le lieu déjà rempli (data-pays, data-dep, …).
    document.addEventListener('click', async e => {
        const btn = e.target.closest('.btn-node-add');
        if (!btn) return;
        e.stopPropagation();

        resetModalToAdd();

        // Pré-rempli les champs géo selon les data-attributes du bouton
        const pays        = btn.dataset.pays        || '';
        const dep         = btn.dataset.dep         || '';
        const localisation = btn.dataset.localisation || '';
        const site        = btn.dataset.site        || '';
        const secteur     = btn.dataset.secteur     || '';
        const sousSecteur = btn.dataset.sousSecteur || '';

        const iPays        = document.getElementById('inputPays');
        const iDep         = document.getElementById('inputDepartement');
        const iLocalisation = document.getElementById('inputLocalisation');
        const iSite        = document.getElementById('inputSite');
        const iSecteur     = document.getElementById('inputSecteur');
        const iSousSecteur = document.getElementById('inputSousSecteur');
        const iRessenti    = document.getElementById('inputRessenti');

        if (iPays)        iPays.value        = pays;
        if (iDep)         iDep.value         = dep;
        if (iLocalisation) iLocalisation.value = localisation;
        if (iSite)        iSite.value        = site;
        if (iSecteur)     iSecteur.value     = secteur;
        if (iSousSecteur) iSousSecteur.value = sousSecteur;
        if (iRessenti)    iRessenti.value    = '';

        // Charge les autocomplete pour les niveaux déjà remplis
        await loadPaysOptions();
        if (pays)         await loadDepartementOptions(pays);
        if (dep)          await loadLocalisationOptions(pays, dep);
        if (localisation) await loadSiteOptions(pays, dep, localisation);
        if (site)         await loadSecteurOptions(pays, dep, localisation, site);
        if (secteur)      await loadSousSecteurOptions(pays, dep, localisation, site, secteur);
        if (secteur)      await refreshRessentiFromGeo();

        openModal('modalOverlay');
    });
    if (btnClose) btnClose.addEventListener('click', () => closeModal('modalOverlay'));
    if (modalOverlay) modalOverlay.addEventListener('click', e => { if (e.target === modalOverlay) closeModal('modalOverlay'); });

    // ── GEO CASCADE ──
    // Cascade : quand un niveau change, on recharge les suggestions du niveau suivant.
    const inputPays        = document.getElementById('inputPays');
    const inputDep         = document.getElementById('inputDepartement');
    const inputLocalisation = document.getElementById('inputLocalisation');
    const inputSite        = document.getElementById('inputSite');
    const inputSecteurEl   = document.getElementById('inputSecteur');

    if (inputPays)         inputPays.addEventListener('change',    () => loadDepartementOptions(inputPays.value));
    if (inputDep)          inputDep.addEventListener('change',     () => loadLocalisationOptions(inputPays.value, inputDep.value));
    if (inputLocalisation) inputLocalisation.addEventListener('change', () => loadSiteOptions(inputPays.value, inputDep.value, inputLocalisation.value));
    if (inputSite)         inputSite.addEventListener('change',    () => loadSecteurOptions(inputPays.value, inputDep.value, inputLocalisation.value, inputSite.value));
    if (inputSecteurEl)    inputSecteurEl.addEventListener('change', () => loadSousSecteurOptions(inputPays.value, inputDep.value, inputLocalisation.value, inputSite.value, inputSecteurEl.value));

    // Pré-remplit / réinitialise le ressenti dès que la chaîne géo change
    ['inputPays','inputDepartement','inputLocalisation','inputSite','inputSecteur','inputSousSecteur'].forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener('change', refreshRessentiFromGeo);
        if (id === 'inputSecteur' || id === 'inputSousSecteur') el.addEventListener('input', refreshRessentiFromGeo);
    });

    // ── STEP 1 → 2 ──
    // Étape 1 → 2 : vérifie le type, le pays, le département et le site, puis affiche le formulaire de l'étape 2.
    const btnStep1Next = document.getElementById('btnStep1Next');
    if (btnStep1Next) {
        btnStep1Next.addEventListener('click', () => {
            const typeEl = document.querySelector('input[name="typeEsc"]:checked');
            if (!typeEl) { alert('Choisis un type d\'escalade.'); return; }
            if (!document.getElementById('inputPays')?.value.trim())        { alert('Indique un pays.'); return; }
            if (!document.getElementById('inputDepartement')?.value.trim()) { alert('Indique un département.'); return; }
            if (!document.getElementById('inputSite')?.value.trim())        { alert('Indique un site.'); return; }

            const type     = typeEl.value;
            const forcedEl = document.getElementById('forcedStatut');
            const statutEl = document.querySelector('input[name="statut"]:checked');
            const statut   = forcedEl ? forcedEl.value : (statutEl ? statutEl.value : 'log');

            document.getElementById('formContent').innerHTML = buildForm(type, statut);
            const starsEl = document.getElementById('fStars');
            if (starsEl) initStarInput(starsEl);
            wireCotationRangePreview();

            const nbInput = document.getElementById('fNbLongueurs');
            if (nbInput) {
                nbInput.addEventListener('change', () => {
                    const n = parseInt(nbInput.value);
                    if (n > 0) buildLongueursForm(n);
                });
            }
            step1.style.display = 'none';
            step2.style.display = 'block';
        });
    }

    // Retour à l'étape 1.
    const btnStep2Prev = document.getElementById('btnStep2Prev');
    if (btnStep2Prev) btnStep2Prev.addEventListener('click', () => {
        step1.style.display = 'block';
        step2.style.display = 'none';
    });

    // ── SUBMIT (AJOUT) ──
    // Enregistrement (création ou modification, selon editAscId).
    // Un log sur corde exige le mode en tête / moulinette (le serveur le revérifie).
    const btnSubmit = document.getElementById('btnSubmit');
    if (btnSubmit) {
        btnSubmit.addEventListener('click', async () => {
            const typeEl = document.querySelector('input[name="typeEsc"]:checked');
            if (!typeEl) return;
            const type     = typeEl.value;
            const forcedEl = document.getElementById('forcedStatut');
            const statutEl = document.querySelector('input[name="statut"]:checked');
            const statut   = forcedEl ? forcedEl.value : (statutEl ? statutEl.value : 'log');
            const payload  = collectPayload(type, statut);
            if (!payload.nom) { alert('Le nom est requis.'); return; }
            if (statut === 'log' && type !== 'bloc' && type !== 'psychobloc' && !payload.grimpe) {
                alert("Indique si c'est grimpé en tête ou en moulinette."); return;
            }

            let res;
            if (editAscId) {
                // MODE ÉDITION
                payload.type = type;
                res = await fetch(`/api/ascension/${editAscId}`, {
                    method: 'PUT',
                    headers: {'Content-Type':'application/json'},
                    body: JSON.stringify(payload)
                });
            } else {
                // MODE AJOUT
                res = await fetch('/api/ascension', {
                    method: 'POST',
                    headers: {'Content-Type':'application/json'},
                    body: JSON.stringify(payload)
                });
            }
            const data = await res.json();
            if (data.error) { alert(data.error); return; }
            // Doublon détecté par le serveur (même nom, cotation, type… dans le même secteur) : rien n'a été créé.
            // Selon ce qui existe déjà et ce qu'on voulait ajouter, on propose une répétition, le passage au carnet, ou on refuse.
            if (data.duplicate) {
                const ex = data.existing;
                const where = { log: 'dans ton carnet', projet: 'dans tes projets', ticklist: 'dans ta tick list' }[ex.statut] || 'déjà';
                if (statut === 'log' && ex.statut === 'log') {
                    // Déjà gravie : on propose d'ajouter une répétition
                    if (!confirm(`« ${ex.nom} » existe déjà ${where}.\n\nVeux-tu l'ajouter comme répétition ?`)) {
                        closeModal('modalOverlay');
                        return;
                    }
                    closeModal('modalOverlay');
                    window.openRepModalPrefilled?.(ex.id, payload);
                } else if (statut === 'log') {
                    // Existe en projet / tick list : on la logue avec le formulaire « Marquer comme grimpé ».
                    // Les essais déjà faits sur le projet s'ajoutent à ceux qu'on vient de saisir.
                    // Un projet a déjà des essais : on les additionne à ceux qui viennent d'être saisis pour pré-remplir le style (nombre d'essais).
                    const before = parseInt(ex.nb_essais_projet) || 0;
                    const added  = essaisFromStyle(payload.style);          // 0 si rien saisi
                    let style = payload.style, hint = '';
                    if (before > 0) {
                        const total = before + added;
                        style = essaisToStyle(total);
                        const plur = n => `${n} essai${n > 1 ? 's' : ''}`;
                        hint = added > 0
                            ? `Tu avais déjà ${plur(before)} sur ce projet + ${plur(added)} saisi${added > 1 ? 's' : ''} à l'instant = ${total > 5 ? 'plus de 5 essais' : plur(total)}.`
                            : `Tu avais déjà ${plur(before)} sur ce projet.`;
                    }
                    const msg = `« ${ex.nom} » existe déjà ${where}.` + (hint ? `\n${hint}` : '') + `\n\nVeux-tu la marquer comme grimpée ?`;
                    if (!confirm(msg)) {
                        closeModal('modalOverlay');
                        return;
                    }
                    closeModal('modalOverlay');
                    window.openLogModalPrefilled?.(ex.id, ex.type, { ...payload, style, hint });
                } else {
                    // Ajout en projet / tick list d'une ascension déjà présente : on ne crée pas de doublon
                    alert(`« ${ex.nom} » existe déjà ${where}.`);
                }
                return;
            }
            // Succès : on recharge la bonne page (Projets, Tick List, ou le Carnet avec le secteur ouvert sur la nouvelle ascension).
            if (data.success) {
                closeModal('modalOverlay');
                if (editAscId) {
                    location.reload();
                } else if (payload.statut === 'projet') {
                    // Un projet ajouté : on propose de détailler la séance (date, commentaire…) ; dans tous les cas on arrive sur la page Projets.
                    const detail = confirm('Projet ajouté !\n\nVeux-tu détailler la séance maintenant (date, nombre d\'essais, mini-journal) ?');
                    location.href = detail ? `/projets?seance=${data.id}` : '/projets';
                } else if (payload.statut === 'ticklist') {
                    location.href = '/ticklist';         // une envie ajoutée : on arrive sur la Tick List
                } else {
                    // Ouvre le secteur de la nouvelle ascension au rechargement
                    location.href = '/carnet?open_secteur=' + data.secteur_id;
                }
            }
        });
    }

    // Bouton crayon d'une ascension : charge ses données (GET /api/ascension/<id>) et ouvre le formulaire pré-rempli à l'étape 2.
    // ── ÉDITION ASCENSION ──
    document.addEventListener('click', async e => {
        const btn = e.target.closest('.btn-edit-asc');
        if (!btn) return;
        const ascId = btn.dataset.ascId;

        // Charge les données existantes
        const res  = await fetch(`/api/ascension/${ascId}`);
        const data = await res.json();
        if (data.error) return;

        const a  = data.ascension;
        editAscId = parseInt(ascId);

        // Pré-rempli l'étape 1 géo
        document.getElementById('inputPays').value          = a.pays_name          || '';
        document.getElementById('inputDepartement').value   = a.departement_name   || '';
        document.getElementById('inputLocalisation').value  = a.localisation_name  || '';
        document.getElementById('inputSite').value          = a.site_name          || '';
        document.getElementById('inputSecteur').value       = a.secteur_name       || '';
        document.getElementById('inputSousSecteur').value   = a.sous_secteur_name  || '';
        const iRessentiEdit = document.getElementById('inputRessenti');
        if (iRessentiEdit) iRessentiEdit.value = a.ressenti || '';

        // Sélectionne le type
        document.querySelectorAll('input[name="typeEsc"]').forEach(r => {
            r.checked = r.value === a.type;
        });

        // Cache le choix de statut en mode édition
        const statutSection = document.getElementById('statutSection');
        if (statutSection) statutSection.style.display = 'none';

        document.getElementById('modalTitle').textContent = 'Modifier l\'ascension';
        step1.style.display = 'none';
        step2.style.display = 'block';

        // Construit le form avec préremplissage
        const statut = a.statut || 'log';
        document.getElementById('formContent').innerHTML = buildForm(a.type, statut, a);
        const starsEl = document.getElementById('fStars');
        if (starsEl) initStarInput(starsEl);
        wireCotationRangePreview();

        // Longueurs GV
        if ((a.type === 'grande_voie' || a.type === 'trad_gv') && a.nb_longueurs) {
            buildLongueursForm(a.nb_longueurs, data.longueurs);
            const nbInput = document.getElementById('fNbLongueurs');
            if (nbInput) {
                nbInput.addEventListener('change', () => {
                    const n = parseInt(nbInput.value);
                    if (n > 0) buildLongueursForm(n);
                });
            }
        }

        openModal('modalOverlay');
    });
}
