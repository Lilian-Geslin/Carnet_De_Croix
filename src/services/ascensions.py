"""Ascensions (logs, projets, envies de tick list) : doublons, création, mise à jour, suppression.

Une ascension est la ligne centrale de l'application. Son `statut` dit à quelle page elle appartient :
« log » (Carnet), « projet » (Projets) ou « ticklist » (Tick List). Ce module contient aussi les
fragments SQL (GEO_JOINS / GEO_COLUMNS) que les autres services réutilisent pour récupérer d'un coup
tous les noms de lieux d'une ascension.
"""
from ..constants import ENVIE_CATS, GV_TYPES
from .formatting import compare_key, to_int_or_none
from .seances import clean_iso_date, sync_essais_projet

# Jointures vers toute la hiérarchie des lieux (alias : sec, si, loc, d, p, ss), à insérer après
# `FROM ascension a`.
GEO_JOINS = """
        LEFT JOIN secteur sec ON a.secteur_id = sec.id
        LEFT JOIN site si     ON sec.site_id   = si.id
        LEFT JOIN localisation loc ON si.localisation_id = loc.id
        LEFT JOIN departement d ON loc.departement_id = d.id
        LEFT JOIN pays p      ON d.pays_id      = p.id
        LEFT JOIN sous_secteur ss ON a.sous_secteur_id = ss.id"""

# Colonnes de lieux correspondantes, à ajouter après `SELECT a.*`.
GEO_COLUMNS = """sec.name as secteur_name, si.name as site_name,
               loc.name as localisation_name, d.name as departement_name, p.name as pays_name,
               ss.name as sous_secteur_name"""


def ascension_owned(conn, asc_id, uid):
    """True si l'ascension `asc_id` existe et appartient à l'utilisateur `uid` (contrôle d'accès des routes)."""
    return conn.execute("SELECT 1 FROM ascension WHERE id=? AND user_id=?", (asc_id, uid)).fetchone() is not None


# ─── Doublons ────────────────────────────────────────────────────────────────

def _identity_key(nom, cotation, cotation_haute, nb_longueurs, type_depart, type_arrivee):
    """Empreinte d'une ascension pour détecter les doublons.

    Les textes sont normalisés (casse, accents et espaces ignorés), et un départ / une arrivée vide
    équivaut à « normal », pour que « Voie  Éole » et « voie eole » soient jugées identiques.
    """
    return (
        compare_key(nom),
        compare_key(cotation),
        compare_key(cotation_haute),
        to_int_or_none(nb_longueurs),
        compare_key(type_depart or 'normal'),
        compare_key(type_arrivee or 'normal'),
    )


def find_duplicate(conn, uid, secteur_id, sous_secteur_id, data):
    """Cherche, dans le même secteur / sous-secteur, une ascension identique (tous statuts confondus).

    Critères comparés : type, nom, cotation (basse), cotation haute, nombre de longueurs, type de
    départ, type d'arrivée. Ignorés : cotation perso, essais, date, pieds nus, note, hauteur,
    commentaire, en tête / moulinette. En cas de plusieurs correspondances, on privilégie
    le log, puis le projet, puis la tick list.
    """
    # Candidates : même utilisateur, même secteur, même discipline et même sous-secteur
    # (« IS » et non « = » pour que NULL corresponde à NULL : voie sans sous-secteur).
    rows = conn.execute(
        "SELECT * FROM ascension WHERE user_id=? AND secteur_id=? AND type=? AND sous_secteur_id IS ?",
        (uid, secteur_id, data['type'], sous_secteur_id)).fetchall()
    wanted = _identity_key(data.get('nom'), data.get('cotation'), data.get('cotation_haute'),
                           data.get('nb_longueurs'), data.get('type_depart'), data.get('type_arrivee'))
    matches = [r for r in rows
               if _identity_key(r['nom'], r['cotation'], r['cotation_haute'], r['nb_longueurs'],
                                r['type_depart'], r['type_arrivee']) == wanted]
    if not matches:
        return None
    # Priorité si plusieurs doublons : un log « gagne » sur un projet, qui gagne sur une envie
    order = {'log': 0, 'projet': 1, 'ticklist': 2}
    matches.sort(key=lambda r: order.get(r['statut'], 9))
    return matches[0]


# ─── Création / mise à jour ──────────────────────────────────────────────────

def _save_longueurs(conn, asc_id, longueurs):
    """Enregistre les longueurs d'une grande voie (numérotées dans l'ordre reçu)."""
    for i, l in enumerate(longueurs):
        conn.execute("""
            INSERT INTO longueur(ascension_id, numero, cotation, cotation_perso, style,
                pieds_nus, hauteur, note_beaute, grimpe)
            VALUES(?,?,?,?,?,?,?,?,?)
        """, (asc_id, i + 1, l.get('cotation'), l.get('cotation_perso'), l.get('style'),
              1 if l.get('pieds_nus') else 0, l.get('hauteur'), l.get('note_beaute'),
              l.get('grimpe')))


def insert_ascension(conn, uid, secteur_id, sous_secteur_id, data):
    """Crée une ascension (et ses longueurs / sa séance n°1 de projet) ; renvoie son identifiant.

    `data` est le dictionnaire déjà validé par la route. `statut` vaut « log » par défaut.
    La catégorie d'envie (performance / beauté / majeure) n'a de sens que pour la tick list.
    Pour une grande voie, `data['longueurs']` donne le détail longueur par longueur.
    """
    asc_type = data['type']
    statut = data.get('statut', 'log')
    cur = conn.execute("""
        INSERT INTO ascension(user_id, secteur_id, sous_secteur_id, type, statut, nom, cotation, cotation_haute,
            cotation_perso, style, nb_essais_projet, pieds_nus, hauteur, note_beaute, date, commentaire,
            type_depart, type_arrivee, nb_longueurs, grimpe, envie_categorie)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        uid, secteur_id, sous_secteur_id, asc_type, statut,
        data.get('nom', ''),
        data.get('cotation'),
        data.get('cotation_haute'),
        data.get('cotation_perso'),
        data.get('style'),
        0,   # recalculé à partir des séances (sync_essais_projet)
        1 if data.get('pieds_nus') else 0,
        data.get('hauteur'),
        data.get('note_beaute'),
        data.get('date'),
        data.get('commentaire'),
        data.get('type_depart'),
        data.get('type_arrivee'),
        data.get('nb_longueurs'),
        data.get('grimpe'),
        data.get('envie_categorie') if statut == 'ticklist' and data.get('envie_categorie') in ENVIE_CATS else None,
    ))
    asc_id = cur.lastrowid

    # Nouveau projet avec des essais déjà faits : ils forment la séance n°1
    # (le total d'essais du projet est toujours recalculé depuis les séances, jamais saisi à la main)
    if statut == 'projet':
        try:
            nb0 = max(0, min(999, int(data.get('nb_essais_projet') or 0)))
        except (TypeError, ValueError):
            nb0 = 0
        if nb0 > 0:
            conn.execute("INSERT INTO seance(ascension_id, numero, date, nb_essais, commentaire) VALUES(?,?,?,?,?)",
                         (asc_id, 1, clean_iso_date(data.get('date_seance')), nb0, None))
            sync_essais_projet(conn, asc_id)

    if asc_type in GV_TYPES and 'longueurs' in data:
        _save_longueurs(conn, asc_id, data['longueurs'])
    return asc_id


def update_ascension(conn, uid, asc_id, secteur_id, sous_secteur_id, data):
    """Met à jour toutes les informations d'une ascension existante (et ses longueurs si grande voie).

    Le statut et la catégorie d'envie ne changent pas ici. Les longueurs sont supprimées puis
    recréées : c'est plus simple que de comparer l'ancienne liste avec la nouvelle.
    """
    conn.execute("""
        UPDATE ascension SET secteur_id=?, sous_secteur_id=?, nom=?, cotation=?, cotation_haute=?, cotation_perso=?,
            style=?, pieds_nus=?, hauteur=?, note_beaute=?, date=?, commentaire=?,
            type_depart=?, type_arrivee=?, nb_longueurs=?, grimpe=?
        WHERE id=? AND user_id=?
    """, (
        secteur_id, sous_secteur_id,
        data.get('nom', ''),
        data.get('cotation'),
        data.get('cotation_haute'),
        data.get('cotation_perso'),
        data.get('style'),
        1 if data.get('pieds_nus') else 0,
        data.get('hauteur'),
        data.get('note_beaute'),
        data.get('date'),
        data.get('commentaire'),
        data.get('type_depart'),
        data.get('type_arrivee'),
        data.get('nb_longueurs'),
        data.get('grimpe'),
        asc_id, uid
    ))
    if data.get('type') in GV_TYPES and 'longueurs' in data:
        conn.execute("DELETE FROM longueur WHERE ascension_id=?", (asc_id,))
        _save_longueurs(conn, asc_id, data['longueurs'])


def delete_ascensions(conn, asc_ids):
    """Supprime des ascensions avec tout ce qui en dépend (répétitions, longueurs, séances, choix, rééquipements). Un topo PDF de la bibliothèque n'est jamais supprimé avec elle : d'autres ascensions peuvent l'utiliser."""
    if not asc_ids:
        return
    # La base n'a pas de suppression en cascade automatique : on vide d'abord les tables filles
    marks = ','.join('?' for _ in asc_ids)
    for table in ('repetition', 'longueur', 'seance', 'ascension_tag', 'reequipement'):
        conn.execute(f"DELETE FROM {table} WHERE ascension_id IN ({marks})", asc_ids)
    conn.execute(f"DELETE FROM ascension WHERE id IN ({marks})", asc_ids)


# ─── Lecture ─────────────────────────────────────────────────────────────────

def get_ascension_detail(conn, asc_id, uid):
    """Données complètes d'une ascension (avec ses lieux et ses longueurs) pour pré-remplir
    le formulaire de modification. None si elle n'existe pas ou n'appartient pas à `uid`."""
    a = conn.execute("SELECT * FROM ascension WHERE id=? AND user_id=?", (asc_id, uid)).fetchone()
    if not a:
        return None
    detail = dict(a)
    # On remonte la hiérarchie secteur › site › localisation › département › pays pour récupérer les noms
    sec = conn.execute("SELECT * FROM secteur WHERE id=?", (a['secteur_id'],)).fetchone()
    site = conn.execute("SELECT * FROM site WHERE id=?", (sec['site_id'],)).fetchone()
    loc = conn.execute("SELECT * FROM localisation WHERE id=?", (site['localisation_id'],)).fetchone()
    dep = conn.execute("SELECT * FROM departement WHERE id=?", (loc['departement_id'],)).fetchone()
    pays = conn.execute("SELECT * FROM pays WHERE id=?", (dep['pays_id'],)).fetchone()
    detail['secteur_name'] = sec['name']
    detail['site_name'] = site['name']
    detail['localisation_name'] = loc['name']
    detail['departement_name'] = dep['name']
    detail['pays_name'] = pays['name']
    # Le « ressenti » (indicatif) est porté par le sous-secteur s'il y en a un, sinon par le secteur
    if a['sous_secteur_id']:
        ss = conn.execute("SELECT * FROM sous_secteur WHERE id=?", (a['sous_secteur_id'],)).fetchone()
        detail['sous_secteur_name'] = ss['name'] if ss else None
        detail['ressenti'] = ss['ressenti'] if ss else None
    else:
        detail['sous_secteur_name'] = None
        detail['ressenti'] = sec['ressenti']
    longueurs = conn.execute("SELECT * FROM longueur WHERE ascension_id=? ORDER BY numero", (asc_id,)).fetchall()
    return {'ascension': detail, 'longueurs': [dict(l) for l in longueurs]}
