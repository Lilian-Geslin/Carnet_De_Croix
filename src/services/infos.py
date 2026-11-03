"""Fenêtre « Plus d'informations » : topo, ouverture, rééquipements, choix (roche, fixations…).

Les informations facultatives d'une ascension : le topo (papier ou PDF), l'année d'ouverture et
l'ouvreur, la liste des rééquipements, les choix cochés (tags) et les séances de projet. Les
fonctions `_clean_*` suivent la convention (valeur, erreur) : l'erreur est un message à afficher
ou None.
"""
import re
from datetime import date

from ..constants import MAX_REEQUIPEMENTS, TAG_CATS, TOPO_FIELDS, TOPO_TYPES
from ..errors import NotFoundError, ValidationError
from . import seances as seances_service
from . import tags as tags_service
from . import topo_pdf as topo_pdf_service


# ─── Nettoyage des saisies ───────────────────────────────────────────────────

def _clean_text(v, maxlen):
    """Texte nettoyé (espaces de bord retirés) ou None s'il est vide / absent. Retourne (valeur, erreur)."""
    if v is None:
        return None, None
    if not isinstance(v, str):
        return None, 'Texte invalide.'
    v = v.strip()
    if len(v) > maxlen:
        return None, f'Texte trop long ({maxlen} caractères maximum).'
    return (v or None), None


def _clean_year(v, label):
    """Année entre 1800 et l'an prochain, ou None. Retourne (valeur, erreur)."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None, None
    try:
        y = int(v)
    except (TypeError, ValueError):
        return None, f'{label} : année invalide.'
    if y < 1800 or y > date.today().year + 1:
        return None, f'{label} : année invalide (entre 1800 et {date.today().year + 1}).'
    return y, None


def _clean_link(v):
    """Lien vers un topo PDF : uniquement http(s). Sans schéma (« exemple.fr/topo.pdf »), on ajoute https://."""
    v, err = _clean_text(v, 500)
    if err or not v:
        return v, err
    # Un lien avec espace est presque sûrement une faute de frappe : on refuse
    if ' ' in v:
        return None, 'Le lien ne doit pas contenir d\'espace.'
    if v.lower().startswith(('http://', 'https://')):
        return v, None
    # javascript:, data:, file:, mailto: … refusés (« site.fr:8080 » reste accepté)
    if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:(?!\d)', v):
        return None, 'Le lien doit commencer par http:// ou https://.'
    return 'https://' + v, None


def _clean_topo_id(v):
    """Identifiant du topo PDF choisi dans la bibliothèque : entier positif ou None (aucun). Retourne (valeur, erreur).
    Le fait que ce topo existe et soit bien à l'utilisateur est vérifié plus tard, par update_infos."""
    if v is None or v == '':
        return None, None
    if isinstance(v, bool) or not isinstance(v, int) or v < 1:
        return None, 'Topo invalide.'
    return v, None


def clean_reequipements(raw):
    """Valide la liste « rééquipé par … (année) ». Une ligne vide est ignorée ; il faut un nom ou une année.

    Retourne (liste de (nom, année), erreur). Liste None : champ absent, rien à modifier
    (différent d'une liste vide, qui efface les rééquipements). En cas d'erreur la liste vaut False.
    """
    if raw is None:
        return None, None
    if not isinstance(raw, list) or len(raw) > MAX_REEQUIPEMENTS:
        return False, f'Rééquipements : liste invalide ({MAX_REEQUIPEMENTS} maximum).'
    out = []
    for item in raw:
        if not isinstance(item, dict):
            return False, 'Rééquipements : format invalide.'
        nom, e = _clean_text(item.get('nom'), 100)
        if e:
            return False, 'Rééquipé par : ' + e
        annee, e = _clean_year(item.get('annee'), 'Année de rééquipement')
        if e:
            return False, e
        if nom or annee:
            out.append((nom, annee))
    return out, None


def parse_infos_payload(data):
    """Valide topo, ouverture et rééquipements. Retourne (champs_topo, rééquipements).

    Lève ValidationError au premier problème rencontré. Selon le type de topo, seuls les champs qui le
    concernent sont lus : « papier » (nom, édition, année, page) ou « pdf » (nom, lien, topo choisi dans la bibliothèque) ; les autres
    restent à None pour effacer d'anciennes valeurs.
    """
    topo_type = data.get('topo_type') or None
    if topo_type not in (None,) + TOPO_TYPES:
        raise ValidationError('Type de topo invalide.')
    # Tous les champs de topo partent à None : changer de type de topo efface les champs devenus inutiles
    f = {k: None for k in TOPO_FIELDS}
    f['topo_type'] = topo_type
    errs = []
    if topo_type:
        f['topo_nom'], e = _clean_text(data.get('topo_nom'), 150); errs.append(e)
    if topo_type == 'papier':
        f['topo_edition'], e = _clean_text(data.get('topo_edition'), 100); errs.append(e)
        f['topo_annee'], e = _clean_year(data.get('topo_annee'), 'Année de publication'); errs.append(e)
        f['topo_page'], e = _clean_text(data.get('topo_page'), 30); errs.append(e)
    elif topo_type == 'pdf':
        f['topo_lien'], e = _clean_link(data.get('topo_lien')); errs.append(e)
        f['topo_id'], e = _clean_topo_id(data.get('topo_id')); errs.append(e)
    f['annee_ouverture'], e = _clean_year(data.get('annee_ouverture'), "Année d'ouverture"); errs.append(e)
    f['ouvreur'], e = _clean_text(data.get('ouvreur'), 100); errs.append(e)
    # Les erreurs sont collectées pendant la lecture ; on ne remonte que la première
    errs = [x for x in errs if x]
    if errs:
        raise ValidationError(errs[0])
    reeq, e = clean_reequipements(data.get('reequipements'))
    if e:
        raise ValidationError(e)
    return f, reeq


# ─── Lecture / écriture ──────────────────────────────────────────────────────

def get_reequipements(conn, asc_id):
    """Rééquipements d'une ascension dans l'ordre saisi, sous la forme [{'nom', 'annee'}]."""
    rows = conn.execute("SELECT nom, annee FROM reequipement WHERE ascension_id=? ORDER BY ordre, id", (asc_id,)).fetchall()
    return [{'nom': r['nom'] or '', 'annee': r['annee']} for r in rows]


def get_infos(conn, uid, asc_id):
    """Tout ce qu'affiche la fenêtre « Plus d'informations » : séances, topo, ouverture, choix retenus
    et propositions disponibles.

    Les catégories de choix proposées dépendent du type d'ascension (cats_for_type). Lève NotFoundError
    si l'ascension n'existe pas ou n'appartient pas à l'utilisateur.
    """
    a = conn.execute("SELECT * FROM ascension WHERE id=? AND user_id=?", (asc_id, uid)).fetchone()
    if not a:
        raise NotFoundError()
    cats = tags_service.cats_for_type(a['type'])
    tags = tags_service.get_ascension_tags(conn, asc_id, cats)
    options = {c: tags_service.get_options(conn, uid, c) for c in cats}
    seances = seances_service.list_seances(conn, asc_id)
    return {
        'nom': a['nom'], 'type': a['type'], 'statut': a['statut'],
        'seances': seances, 'nb_seances': len(seances),
        'total_essais': seances_service.total_essais(seances),
        'topo': {k: a[k] for k in ('topo_type', 'topo_nom', 'topo_edition', 'topo_annee', 'topo_page', 'topo_lien')},
        'ouverture': {'annee': a['annee_ouverture'], 'ouvreur': a['ouvreur']},
        'reequipements': get_reequipements(conn, asc_id),
        # Topo PDF choisi dans la bibliothèque (ou None) et toute la bibliothèque, ceux du site de l'ascension en premier
        'topo_pdf': topo_pdf_service.get_meta(conn, uid, a['topo_id']) if a['topo_id'] else None,
        'topos': _topos_proposes(conn, uid, asc_id),
        'cats': [{'key': c, 'label': TAG_CATS[c]['label']} for c in cats],
        'tags': tags, 'options': options,
    }


def _topos_proposes(conn, uid, asc_id):
    """Bibliothèque de topos PDF, avec `local` = True pour ceux déjà utilisés ou rattachés au site de l'ascension
    (la fiche les propose d'abord)."""
    locaux = topo_pdf_service.site_topo_ids(conn, uid, asc_id)
    return [dict(t, local=t['id'] in locaux) for t in topo_pdf_service.list_topos(conn, uid)]


def update_infos(conn, uid, asc_id, data):
    """Enregistre topo, ouverture, rééquipements et choix d'une ascension.

    Tout est validé avant la moindre écriture. Si `reequipements` est absent de `data`, la liste
    existante n'est pas touchée ; sinon elle est remplacée (et l'ordre saisi est conservé).
    """
    topo_fields, reeq = parse_infos_payload(data)
    a = conn.execute("SELECT type FROM ascension WHERE id=? AND user_id=?", (asc_id, uid)).fetchone()
    if not a:
        raise NotFoundError()
    selection = tags_service.clean_tag_selection(data.get('tags'), tags_service.cats_for_type(a['type']))
    # Le topo choisi doit exister dans la bibliothèque de l'utilisateur (un id étranger est refusé comme un id inconnu)
    if topo_fields['topo_id'] is not None and not topo_pdf_service.get_meta(conn, uid, topo_fields['topo_id']):
        raise ValidationError('Topo inconnu.')

    # Les champs de topo / ouverture sont tous réécrits d'un coup (les noms de colonnes viennent de TOPO_FIELDS)
    sets = ', '.join(f"{k}=?" for k in TOPO_FIELDS)
    conn.execute(f"UPDATE ascension SET {sets} WHERE id=? AND user_id=?",
                 [topo_fields[k] for k in TOPO_FIELDS] + [asc_id, uid])
    tags_service.replace_ascension_tags(conn, asc_id, selection)
    if reeq is not None:
        conn.execute("DELETE FROM reequipement WHERE ascension_id=?", (asc_id,))
        for i, (nom, annee) in enumerate(reeq):
            conn.execute("INSERT INTO reequipement(ascension_id, nom, annee, ordre) VALUES(?,?,?,?)",
                         (asc_id, nom, annee, i))
    conn.commit()


def known_names(conn, uid):
    """Noms déjà saisis, pour les suggestions déroulantes : ascensions, lieux, ouvreurs (rééquipeurs inclus), topos."""
    ascs = [r[0] for r in conn.execute(
        "SELECT DISTINCT nom FROM ascension WHERE user_id=? AND nom<>'' ORDER BY nom COLLATE NOCASE", (uid,))]
    # Un nom de lieu peut exister à plusieurs niveaux : l'ensemble supprime les doublons.
    # Chaque requête liste les noms d'un niveau de la hiérarchie, limités aux lieux de l'utilisateur.
    lieux = set()
    for sql in (
        "SELECT name FROM pays WHERE user_id=?",
        "SELECT d.name FROM departement d JOIN pays p ON d.pays_id=p.id WHERE p.user_id=?",
        "SELECT l.name FROM localisation l JOIN departement d ON l.departement_id=d.id JOIN pays p ON d.pays_id=p.id WHERE p.user_id=?",
        "SELECT si.name FROM site si JOIN localisation l ON si.localisation_id=l.id JOIN departement d ON l.departement_id=d.id JOIN pays p ON d.pays_id=p.id WHERE p.user_id=?",
        "SELECT sec.name FROM secteur sec JOIN site si ON sec.site_id=si.id JOIN localisation l ON si.localisation_id=l.id JOIN departement d ON l.departement_id=d.id JOIN pays p ON d.pays_id=p.id WHERE p.user_id=?",
        "SELECT ss.name FROM sous_secteur ss JOIN secteur sec ON ss.secteur_id=sec.id JOIN site si ON sec.site_id=si.id JOIN localisation l ON si.localisation_id=l.id JOIN departement d ON l.departement_id=d.id JOIN pays p ON d.pays_id=p.id WHERE p.user_id=?",
    ):
        lieux.update(r[0] for r in conn.execute(sql, (uid,)) if r[0])
    # Ouvreurs et personnes ayant rééquipé sont fusionnés en une seule liste de noms (UNION supprime les doublons exacts)
    ouvreurs = [r[0] for r in conn.execute("""
        SELECT ouvreur FROM ascension WHERE user_id=? AND ouvreur<>''
        UNION
        SELECT r.nom FROM reequipement r JOIN ascension a ON a.id=r.ascension_id WHERE a.user_id=? AND r.nom<>''
        ORDER BY 1 COLLATE NOCASE""", (uid, uid))]
    topos = [r[0] for r in conn.execute(
        "SELECT DISTINCT topo_nom FROM ascension WHERE user_id=? AND topo_nom<>'' ORDER BY topo_nom COLLATE NOCASE", (uid,))]
    return {'ascensions': ascs, 'lieux': sorted(lieux, key=lambda x: x.lower()), 'ouvreurs': ouvreurs, 'topos': topos}
