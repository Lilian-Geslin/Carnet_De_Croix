"""Bibliothèque de topos PDF enregistrés dans le site, et contenu du bouton « Topo » d'un lieu.

Chaque PDF n'est enregistré qu'UNE fois (table `topo`, contenu en BLOB dans `carnet.db`, donc emporté par la
sauvegarde) : plusieurs ascensions peuvent le choisir (`ascension.topo_id`). Un même fichier envoyé deux fois
(même empreinte SHA-256) n'est pas dupliqué. Un nouveau fichier — par exemple une nouvelle édition du topo — est un
nouveau topo : les ascensions déjà saisies gardent l'ancien.

Un topo peut aussi être rattaché à un lieu (table `topo_lieu`, niveaux localisation / site / secteur / sous-secteur) ;
le bouton « Topo » d'un lieu liste les topos qui lui sont rattachés ou qui sont utilisés par une ascension en dessous
de lui, plus les topos papier et les liens en ligne qui y sont renseignés (`topos_du_lieu`).

Les routes (routes/api_topos.py) ne font que passer le fichier reçu.
"""
import hashlib
import os
import re
from datetime import date

from ..constants import TOPO_NIVEAUX, TOPO_PDF_MAX_BYTES, TOPO_TITRE_MAX
from ..errors import NotFoundError, ValidationError
from .ascensions import ascension_owned
from .geo import geo_owned

# Longueur maximale conservée pour le nom d'origine d'un fichier.
_NOM_MAX = 150


# ─── Vérification du fichier ─────────────────────────────────────────────────

def clean_filename(name):
    """Nom de fichier propre à afficher : sans chemin, sans caractères de contrôle, 150 caractères maximum,
    avec l'extension « .pdf » (ajoutée si elle manque). Un nom vide devient « topo.pdf »."""
    # Certains navigateurs envoient un chemin complet (C:\\dossier\\topo.pdf) : on ne garde que le dernier morceau.
    name = os.path.basename((name or '').replace('\\', '/'))
    name = re.sub(r'[\x00-\x1f\x7f]', '', name).strip()
    if not name:
        name = 'topo.pdf'
    if not name.lower().endswith('.pdf'):
        name += '.pdf'
    if len(name) > _NOM_MAX:
        name = name[:_NOM_MAX - 4] + '.pdf'
    return name


def validate_pdf(data):
    """Lève ValidationError si le contenu n'est pas un PDF acceptable : non vide, au plus TOPO_PDF_MAX_BYTES,
    et commençant par la signature « %PDF- » (on ne se fie pas à l'extension, qu'on peut falsifier)."""
    if not data:
        raise ValidationError('Aucun fichier reçu.')
    if len(data) > TOPO_PDF_MAX_BYTES:
        raise ValidationError(f'Le PDF dépasse {TOPO_PDF_MAX_BYTES // (1024 * 1024)} Mo.')
    # Certains PDF commencent par quelques octets parasites : la norme tolère la signature dans les 1024 premiers octets.
    if b'%PDF-' not in data[:1024]:
        raise ValidationError("Ce fichier n'est pas un PDF.")


def clean_titre(titre, fichier_nom):
    """Titre d'un topo : le titre saisi (espaces de bord retirés, 150 caractères maximum), sinon le nom du fichier
    sans « .pdf ». Lève ValidationError si le titre n'est pas du texte ou est trop long."""
    if titre is not None and not isinstance(titre, str):
        raise ValidationError('Titre invalide.')
    titre = (titre or '').strip()
    if len(titre) > TOPO_TITRE_MAX:
        raise ValidationError(f'Titre trop long ({TOPO_TITRE_MAX} caractères maximum).')
    if titre:
        return titre
    return fichier_nom[:-4] if fichier_nom.lower().endswith('.pdf') else fichier_nom


# ─── Bibliothèque ────────────────────────────────────────────────────────────

def _meta(row, nb=0):
    """Description d'un topo sans son contenu : id, titre, nom du fichier, taille (octets) et nombre d'ascensions."""
    return {'id': row['id'], 'nom': row['nom'], 'fichier': row['fichier_nom'], 'taille': row['taille'], 'nb': nb}


def get_meta(conn, uid, topo_id):
    """Description du topo (sans son contenu), ou None s'il n'existe pas ou n'est pas à l'utilisateur."""
    row = conn.execute("SELECT id, nom, fichier_nom, taille FROM topo WHERE id=? AND user_id=?", (topo_id, uid)).fetchone()
    return _meta(row, _count_ascensions(conn, uid, topo_id)) if row else None


def _count_ascensions(conn, uid, topo_id):
    """Nombre d'ascensions de l'utilisateur qui utilisent ce topo."""
    return conn.execute("SELECT COUNT(*) FROM ascension WHERE topo_id=? AND user_id=?", (topo_id, uid)).fetchone()[0]


def list_topos(conn, uid):
    """Tous les topos PDF de l'utilisateur, par titre, avec le nombre d'ascensions qui les utilisent."""
    rows = conn.execute("""
        SELECT t.id, t.nom, t.fichier_nom, t.taille,
               (SELECT COUNT(*) FROM ascension a WHERE a.topo_id=t.id AND a.user_id=t.user_id) AS nb
        FROM topo t WHERE t.user_id=? ORDER BY t.nom COLLATE NOCASE, t.id""", (uid,)).fetchall()
    return [_meta(r, r['nb']) for r in rows]


def lieu_of_ascension(conn, uid, asc_id):
    """Lieu le plus précis d'une ascension : ('sous_secteur', id) s'il y en a un, sinon ('secteur', id).
    Lève NotFoundError si l'ascension n'est pas à l'utilisateur."""
    a = conn.execute("SELECT secteur_id, sous_secteur_id FROM ascension WHERE id=? AND user_id=?", (asc_id, uid)).fetchone()
    if not a:
        raise NotFoundError()
    if a['sous_secteur_id']:
        return 'sous_secteur', a['sous_secteur_id']
    return ('secteur', a['secteur_id']) if a['secteur_id'] else None


def _check_lieu(conn, uid, niveau, lieu_id):
    """Vérifie que (niveau, id) est un lieu de l'utilisateur qui peut avoir un topo (pas le pays ni le département)."""
    if niveau not in TOPO_NIVEAUX:
        raise ValidationError('Les topos se rattachent à une localisation, un site, un secteur ou un sous-secteur.')
    if not isinstance(lieu_id, int) or isinstance(lieu_id, bool) or not geo_owned(conn, niveau, lieu_id, uid):
        raise NotFoundError()


def add_topo(conn, uid, filename, data, titre=None, lieu=None):
    """Enregistre un PDF dans la bibliothèque ; renvoie (topo, existait).

    Si le même fichier (même contenu) est déjà enregistré pour ce compte, il n'est pas dupliqué : on renvoie le
    topo existant (`existait` vaut True, son titre est conservé). `lieu` = (niveau, id) rattache le topo à ce lieu.
    Lève ValidationError si le fichier ou le titre est refusé, NotFoundError si le lieu n'est pas à l'utilisateur.
    Tout est vérifié avant la moindre écriture."""
    validate_pdf(data)
    fichier_nom = clean_filename(filename)
    titre = clean_titre(titre, fichier_nom)
    if lieu:
        _check_lieu(conn, uid, *lieu)
    sha = hashlib.sha256(data).hexdigest()
    row = conn.execute("SELECT id FROM topo WHERE user_id=? AND sha256=?", (uid, sha)).fetchone()
    existait = bool(row)
    if row:
        topo_id = row['id']
    else:
        topo_id = conn.execute(
            "INSERT INTO topo(user_id, nom, fichier_nom, taille, sha256, contenu, date_ajout) VALUES(?,?,?,?,?,?,?)",
            (uid, titre, fichier_nom, len(data), sha, data, date.today().isoformat())).lastrowid
    if lieu:
        # OR IGNORE : le rattachement existe peut-être déjà
        conn.execute("INSERT OR IGNORE INTO topo_lieu(topo_id, niveau, lieu_id) VALUES(?,?,?)", (topo_id, *lieu))
    conn.commit()
    return get_meta(conn, uid, topo_id), existait


def read_pdf(conn, uid, topo_id):
    """(nom du fichier, contenu) d'un topo. Lève NotFoundError s'il n'existe pas ou n'est pas à l'utilisateur."""
    row = conn.execute("SELECT fichier_nom, contenu FROM topo WHERE id=? AND user_id=?", (topo_id, uid)).fetchone()
    if not row:
        raise NotFoundError('Topo introuvable.')
    return row['fichier_nom'], bytes(row['contenu'])


def rename_topo(conn, uid, topo_id, titre):
    """Change le titre d'un topo (le titre ne peut pas être vide). Lève NotFoundError / ValidationError."""
    row = conn.execute("SELECT fichier_nom FROM topo WHERE id=? AND user_id=?", (topo_id, uid)).fetchone()
    if not row:
        raise NotFoundError('Topo introuvable.')
    if not isinstance(titre, str) or not titre.strip():
        raise ValidationError('Le titre ne peut pas être vide.')
    titre = clean_titre(titre, row['fichier_nom'])
    conn.execute("UPDATE topo SET nom=? WHERE id=?", (titre, topo_id))
    conn.commit()
    return titre


def delete_topo(conn, uid, topo_id):
    """Supprime un topo de la bibliothèque. Les ascensions qui le choisissaient n'ont plus de topo PDF (le reste de
    leur fiche est intact) ; renvoie leur nombre. Lève NotFoundError si le topo n'est pas à l'utilisateur."""
    if not conn.execute("SELECT 1 FROM topo WHERE id=? AND user_id=?", (topo_id, uid)).fetchone():
        raise NotFoundError('Topo introuvable.')
    nb = conn.execute("UPDATE ascension SET topo_id=NULL WHERE topo_id=? AND user_id=?", (topo_id, uid)).rowcount
    conn.execute("DELETE FROM topo_lieu WHERE topo_id=?", (topo_id,))
    conn.execute("DELETE FROM topo WHERE id=?", (topo_id,))
    conn.commit()
    return nb


# ─── Bouton « Topo » d'un lieu ───────────────────────────────────────────────

def _subtree(conn, niveau, lieu_id):
    """Identifiants du lieu et de tous ses descendants, par niveau : {'site': [...], 'secteur': [...], …}.
    Sert à retrouver les ascensions et les topos rattachés « en dessous » d'un lieu."""
    ids = {n: [] for n in TOPO_NIVEAUX}
    ids[niveau] = [lieu_id]
    if niveau == 'localisation':
        ids['site'] = [r[0] for r in conn.execute("SELECT id FROM site WHERE localisation_id=?", (lieu_id,))]
    if niveau in ('localisation', 'site') and ids['site']:
        marks = ','.join('?' for _ in ids['site'])
        ids['secteur'] = [r[0] for r in conn.execute(f"SELECT id FROM secteur WHERE site_id IN ({marks})", ids['site'])]
    if niveau in ('localisation', 'site', 'secteur') and ids['secteur']:
        marks = ','.join('?' for _ in ids['secteur'])
        ids['sous_secteur'] = [r[0] for r in conn.execute(
            f"SELECT id FROM sous_secteur WHERE secteur_id IN ({marks})", ids['secteur'])]
    return ids


def _ascension_filter(ids):
    """Condition SQL (et ses paramètres) qui retient les ascensions situées dans ce sous-arbre.
    Un sous-secteur se reconnaît à `sous_secteur_id` ; au-dessus, `secteur_id` (toujours renseigné) suffit."""
    if ids['secteur']:
        return f"a.secteur_id IN ({','.join('?' for _ in ids['secteur'])})", list(ids['secteur'])
    if ids['sous_secteur']:
        return f"a.sous_secteur_id IN ({','.join('?' for _ in ids['sous_secteur'])})", list(ids['sous_secteur'])
    return '0', []


def topos_du_lieu(conn, uid, niveau, lieu_id):
    """Contenu du bouton « Topo » d'un lieu : {'pdf': [...], 'papier': [...], 'en_ligne': [...]}.

    - `pdf` : topos de la bibliothèque rattachés à ce lieu ou à un lieu en dessous, ou utilisés par une ascension en dessous
      (chacun avec son nombre d'ascensions dans ce lieu) ;
    - `papier` : topos papier renseignés sur les ascensions du lieu (titre, édition, année), regroupés ;
    - `en_ligne` : liens renseignés sans fichier enregistré, regroupés.
    Un site n'affiche que ses propres topos ; une localisation, ceux de tous ses sites. Lève NotFoundError si le lieu
    n'est pas à l'utilisateur, ValidationError si le niveau n'a pas de topo (pays, département)."""
    _check_lieu(conn, uid, niveau, lieu_id)
    ids = _subtree(conn, niveau, lieu_id)
    cond, params = _ascension_filter(ids)

    # PDF utilisés par des ascensions du lieu (avec leur nombre) …
    nb = {r[0]: r[1] for r in conn.execute(
        f"SELECT a.topo_id, COUNT(*) FROM ascension a WHERE a.user_id=? AND a.topo_id IS NOT NULL AND {cond} GROUP BY a.topo_id",
        [uid] + params)}
    # … et PDF rattachés au lieu ou à un lieu en dessous
    ors, tparams = [], []
    for n in TOPO_NIVEAUX:
        if ids[n]:
            ors.append(f"(tl.niveau=? AND tl.lieu_id IN ({','.join('?' for _ in ids[n])}))")
            tparams += [n] + ids[n]
    rattaches = set()
    if ors:
        rattaches = {r[0] for r in conn.execute(
            f"SELECT DISTINCT tl.topo_id FROM topo_lieu tl JOIN topo t ON t.id=tl.topo_id "
            f"WHERE t.user_id=? AND ({' OR '.join(ors)})", [uid] + tparams)}
    tous = sorted(set(nb) | rattaches)
    pdf = []
    if tous:
        rows = conn.execute(
            f"SELECT id, nom, fichier_nom, taille FROM topo WHERE user_id=? AND id IN ({','.join('?' for _ in tous)})",
            [uid] + tous).fetchall()
        pdf = sorted((_meta(r, nb.get(r['id'], 0)) for r in rows), key=lambda t: (t['nom'].lower(), t['id']))

    # Regroupement fait en Python : le LOWER de SQLite ignore les majuscules accentuées (« É »), pas casefold().
    papier, groupes = [], {}
    for r in conn.execute(
            f"""SELECT a.topo_nom, a.topo_edition, a.topo_annee FROM ascension a
                WHERE a.user_id=? AND a.topo_type='papier' AND {cond} ORDER BY a.id""", [uid] + params):
        cle = ((r['topo_nom'] or '').casefold(), (r['topo_edition'] or '').casefold(), r['topo_annee'])
        if cle in groupes:
            groupes[cle]['nb'] += 1
        else:
            groupes[cle] = {'nom': r['topo_nom'], 'edition': r['topo_edition'], 'annee': r['topo_annee'], 'nb': 1}
            papier.append(groupes[cle])
    papier.sort(key=lambda p: (p['nom'] or '').casefold())

    en_ligne, groupes = [], {}
    for r in conn.execute(
            f"""SELECT a.topo_nom, a.topo_lien FROM ascension a
                WHERE a.user_id=? AND a.topo_type='pdf' AND a.topo_id IS NULL
                  AND (a.topo_lien IS NOT NULL OR a.topo_nom IS NOT NULL) AND {cond} ORDER BY a.id""", [uid] + params):
        cle = ((r['topo_nom'] or '').casefold(), r['topo_lien'] or '')
        if cle in groupes:
            groupes[cle]['nb'] += 1
        else:
            groupes[cle] = {'nom': r['topo_nom'], 'lien': r['topo_lien'], 'nb': 1}
            en_ligne.append(groupes[cle])
    en_ligne.sort(key=lambda o: (o['nom'] or '').casefold())
    return {'pdf': pdf, 'papier': papier, 'en_ligne': en_ligne}


def site_topo_ids(conn, uid, asc_id):
    """Identifiants des topos « du lieu » d'une ascension (ceux de son site), pour les proposer en premier dans sa fiche."""
    lieu = lieu_of_ascension(conn, uid, asc_id)
    if not lieu:
        return set()
    niveau, lieu_id = lieu
    if niveau == 'sous_secteur':
        lieu_id = conn.execute("SELECT secteur_id FROM sous_secteur WHERE id=?", (lieu_id,)).fetchone()[0]
    site_id = conn.execute("SELECT site_id FROM secteur WHERE id=?", (lieu_id,)).fetchone()[0]
    return {t['id'] for t in topos_du_lieu(conn, uid, 'site', site_id)['pdf']}
