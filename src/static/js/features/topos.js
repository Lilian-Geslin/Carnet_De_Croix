// Bouton « Topo » des lieux de l'arbre du Carnet (localisation, site, secteur, sous-secteur).
//
// Un clic ouvre la fenêtre #topoModalOverlay (définie dans pages/carnet.html) qui liste les topos du lieu :
//   - les PDF enregistrés dans le site (ouvrir, renommer, supprimer) — chacun n'est stocké qu'une seule fois, même s'il
//     sert à plusieurs ascensions ;
//   - les topos papier et les liens en ligne renseignés sur les ascensions du lieu (affichage seulement).
// Un site n'affiche que ses propres topos ; une localisation montre ceux de tous ses sites. « + Ajouter un topo PDF »
// enregistre un nouveau PDF et le rattache à ce lieu.
// API : GET /api/topos/lieu/<niveau>/<id> ; POST /api/topos ; GET /api/topos/<id>/pdf ; PUT / DELETE /api/topos/<id>.

function initTopos() {
    const overlay = document.getElementById('topoModalOverlay');
    if (!overlay) return;                       // page sans arbre (Stats, Projets…)

    const PDF_MAX = 20 * 1024 * 1024;           // même limite que le serveur (constants.TOPO_PDF_MAX_BYTES)
    const LABELS = { localisation: 'la localisation', site: 'le site', secteur: 'le secteur', sous_secteur: 'le sous-secteur' };
    const body = document.getElementById('topoModalBody');
    let cur = null;                             // lieu affiché : { niveau, id, name }

    // Taille lisible : « 340 Ko », « 1,2 Mo ».
    const fmtSize = n => n >= 1048576 ? (n / 1048576).toFixed(1).replace('.', ',') + ' Mo' : Math.max(1, Math.round(n / 1024)) + ' Ko';
    // « 3 ascensions » / « 1 ascension ».
    const nbAsc = n => `${n} ascension${n > 1 ? 's' : ''}`;
    // Crée un élément avec classe et texte (le texte est toujours inséré en texte brut, jamais en HTML).
    const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
    // Message d'erreur / d'information sous la liste.
    const flash = (msg, isError) => { let f = document.getElementById('topoFlash'); if (!f) { f = el('p', 'topo-flash'); f.id = 'topoFlash'; body.parentNode.insertBefore(f, body); } f.textContent = msg || ''; f.classList.toggle('error', !!isError); };

    // Un titre de section.
    const section = (title) => { const h = el('h3', 'topo-h', title); return h; };

    // Ligne d'un PDF de la bibliothèque : titre, taille, nombre d'ascensions et boutons Ouvrir / renommer / supprimer.
    function pdfRow(t) {
        const row = el('div', 'topo-row');
        const info = el('div', 'topo-info');
        const a = el('a', 'topo-link', `📎 ${t.nom}`);
        a.href = `/api/topos/${t.id}/pdf`; a.target = '_blank'; a.rel = 'noopener noreferrer';
        info.append(a, el('span', 'topo-meta', `${fmtSize(t.taille)} · ${t.nb ? nbAsc(t.nb) : 'aucune ascension ici'}`));
        const btns = el('div', 'topo-btns');
        const open = el('a', 'btn-secondary-sm', 'Ouvrir ↗'); open.href = a.href; open.target = '_blank'; open.rel = 'noopener noreferrer';
        const ren = el('button', 'btn-node-edit', '✏'); ren.type = 'button'; ren.title = 'Renommer';
        const del = el('button', 'btn-node-del', '✕'); del.type = 'button'; del.title = 'Supprimer ce topo';
        ren.addEventListener('click', () => renameTopo(t));
        del.addEventListener('click', () => deleteTopo(t));
        btns.append(open, ren, del);
        row.append(info, btns);
        return row;
    }

    // Ligne d'un topo papier : titre, édition, année, nombre d'ascensions.
    function papierRow(p) {
        const row = el('div', 'topo-row');
        const info = el('div', 'topo-info');
        info.append(el('span', 'topo-nom', `📖 ${p.nom || 'Topo papier (sans titre)'}`));
        const meta = [p.edition, p.annee, nbAsc(p.nb)].filter(Boolean).join(' · ');
        info.append(el('span', 'topo-meta', meta));
        row.append(info);
        return row;
    }

    // Ligne d'un topo en ligne (lien sans fichier enregistré).
    function enLigneRow(o) {
        const row = el('div', 'topo-row');
        const info = el('div', 'topo-info');
        if (o.lien) {
            const a = el('a', 'topo-link', `🔗 ${o.nom || o.lien}`);
            a.href = o.lien; a.target = '_blank'; a.rel = 'noopener noreferrer';
            info.append(a);
        } else {
            info.append(el('span', 'topo-nom', `🔗 ${o.nom}`));
        }
        info.append(el('span', 'topo-meta', nbAsc(o.nb)));
        row.append(info);
        return row;
    }

    // Affiche le contenu reçu du serveur.
    function render(data) {
        body.innerHTML = '';
        const vide = !data.pdf.length && !data.papier.length && !data.en_ligne.length;
        if (vide) {
            body.append(el('p', 'topo-vide', 'Aucun topo renseigné pour ce lieu. Ajoute un PDF ci-dessous, ou renseigne le topo dans « Plus d\'informations » d\'une ascension.'));
            return;
        }
        if (data.pdf.length)      { body.append(section('Topos PDF')); data.pdf.forEach(t => body.append(pdfRow(t))); }
        if (data.papier.length)   { body.append(section('Topos papier')); data.papier.forEach(p => body.append(papierRow(p))); }
        if (data.en_ligne.length) { body.append(section('Liens en ligne')); data.en_ligne.forEach(o => body.append(enLigneRow(o))); }
    }

    // (Re)charge la liste du lieu courant.
    async function load() {
        body.textContent = 'Chargement…';
        try {
            const res = await fetch(`/api/topos/lieu/${cur.niveau}/${cur.id}`);
            const data = await res.json();
            if (data.error) { body.textContent = ''; flash(data.error, true); return; }
            render(data);
        } catch (err) {
            body.textContent = ''; flash('Erreur de chargement des topos.', true);
        }
    }

    // Renomme un topo (le nouveau titre sert partout où ce topo est utilisé).
    async function renameTopo(t) {
        const nom = prompt('Titre du topo :', t.nom);
        if (nom === null || nom.trim() === '' || nom.trim() === t.nom) return;
        const res = await fetch(`/api/topos/${t.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nom }) });
        const data = await res.json();
        if (!data.success) { flash(data.error || 'Erreur lors du renommage.', true); return; }
        flash(''); load();
    }

    // Supprime un topo de la bibliothèque (après confirmation) ; les ascensions qui l'utilisaient perdent seulement ce lien.
    async function deleteTopo(t) {
        const n = t.nb ? ` ${nbAsc(t.nb)} l'utilise${t.nb > 1 ? 'nt' : ''} ici : elles n'auront plus de topo PDF.` : '';
        if (!confirm(`Supprimer le topo « ${t.nom} » de tous tes lieux ?${n}`)) return;
        const res = await fetch(`/api/topos/${t.id}`, { method: 'DELETE' });
        const data = await res.json();
        if (!data.success) { flash(data.error || 'Erreur lors de la suppression.', true); return; }
        flash('Topo supprimé'); load();
    }

    // Envoie un nouveau PDF, rattaché au lieu affiché.
    async function addTopo(file) {
        if (!file) return;
        if (!/\.pdf$/i.test(file.name) && file.type !== 'application/pdf') { flash('Ce fichier n\'est pas un PDF.', true); return; }
        if (file.size > PDF_MAX) { flash('Le PDF dépasse 20 Mo.', true); return; }
        flash('Envoi du PDF…');
        const fd = new FormData();
        fd.append('fichier', file); fd.append('niveau', cur.niveau); fd.append('lieu_id', cur.id);
        try {
            const res = await fetch('/api/topos', { method: 'POST', body: fd });
            const data = await res.json();
            if (!data.success) { flash(data.error || 'Erreur lors de l\'envoi du PDF.', true); return; }
            flash(data.existait ? 'Ce PDF était déjà enregistré : il est maintenant rattaché à ce lieu.' : '✓ Topo ajouté');
            load();
        } catch (err) {
            flash('Erreur lors de l\'envoi du PDF.', true);
        }
    }

    // Ouverture : clic sur un bouton « Topo » de l'arbre.
    document.addEventListener('click', e => {
        const btn = e.target.closest('.btn-node-topo');
        if (!btn) return;
        e.preventDefault(); e.stopPropagation();   // le bouton est dans un <summary> : ne pas plier / déplier le lieu
        cur = { niveau: btn.dataset.niveau, id: Number(btn.dataset.id), name: btn.dataset.name };
        document.getElementById('topoModalTitle').textContent = `Topos · ${cur.name}`;
        flash('');
        openModal('topoModalOverlay');
        load();
    });
    document.getElementById('topoAddFile').addEventListener('change', e => { addTopo(e.target.files[0]); e.target.value = ''; });
    document.getElementById('btnCloseTopoModal').addEventListener('click', () => closeModal('topoModalOverlay'));
    overlay.addEventListener('click', e => { if (e.target === overlay) closeModal('topoModalOverlay'); });
}
