"""Lieux : pays › département › localisation › site › secteur › sous-secteur.

Propriété des données, création à la volée (get-or-create), renommage, suppression en cascade,
compteurs d'exploration.

Les lieux sont des tables emboîtées : chaque niveau pointe vers son parent (`pays_id`,
`departement_id`, `localisation_id`, `site_id`, `secteur_id`). Le sous-secteur est facultatif ;
une ascension est toujours rattachée à un secteur, et en plus à un sous-secteur s'il y en a un.
"""
from ..constants import RESSENTI_LABELS
from .ascensions import delete_ascensions

# Seul le pays porte un user_id : on remonte la hiérarchie jusqu'au pays pour savoir à qui
# appartient un élément. Chaque requête, pour un id donné, renvoie le user_id du propriétaire.
_GEO_OWNER_SQL = {
    'pays':         "SELECT p.user_id FROM pays p WHERE p.id=?",
    'departement':  "SELECT p.user_id FROM departement d JOIN pays p ON d.pays_id=p.id WHERE d.id=?",
    'localisation': """SELECT p.user_id FROM localisation l JOIN departement d ON l.departement_id=d.id
                       JOIN pays p ON d.pays_id=p.id WHERE l.id=?""",
    'site':         """SELECT p.user_id FROM site si JOIN localisation l ON si.localisation_id=l.id
                       JOIN departement d ON l.departement_id=d.id JOIN pays p ON d.pays_id=p.id WHERE si.id=?""",
    'secteur':      """SELECT p.user_id FROM secteur sec JOIN site si ON sec.site_id=si.id
                       JOIN localisation l ON si.localisation_id=l.id JOIN departement d ON l.departement_id=d.id
                       JOIN pays p ON d.pays_id=p.id WHERE sec.id=?""",
    'sous_secteur': """SELECT p.user_id FROM sous_secteur ss JOIN secteur sec ON ss.secteur_id=sec.id
                       JOIN site si ON sec.site_id=si.id JOIN localisation l ON si.localisation_id=l.id
                       JOIN departement d ON l.departement_id=d.id JOIN pays p ON d.pays_id=p.id WHERE ss.id=?""",
}

# Colonne qui relie un niveau à son parent (pour lister les enfants d'un élément)
PARENT_COLUMN = {
    'departement': 'pays_id',
    'localisation': 'departement_id',
    'site': 'localisation_id',
    'secteur': 'site_id',
    'sous_secteur': 'secteur_id',
}


def geo_owned(conn, table, item_id, uid):
    """True si l'élément `table`/`item_id` appartient à l'utilisateur `uid`."""
    sql = _GEO_OWNER_SQL.get(table)
    if not sql:
        return False
    row = conn.execute(sql, (item_id,)).fetchone()
    return bool(row) and row[0] == uid


def list_children(conn, child_table, parent_id):
    """Éléments d'un niveau rattachés à leur parent, triés par nom."""
    column = PARENT_COLUMN[child_table]
    rows = conn.execute(f"SELECT * FROM {child_table} WHERE {column}=? ORDER BY name", (parent_id,)).fetchall()
    return [dict(r) for r in rows]


# ─── Saisie d'un lieu ────────────────────────────────────────────────────────

def validate_geo_payload(data):
    """Les niveaux pays / département / site sont obligatoires (pas de lieu sans nom).

    Renvoie un message d'erreur, ou None si tout est correct. Localisation et secteur peuvent
    rester vides : normalize_geo_payload leur donne un nom par défaut.
    """
    for key, label in (('pays', 'Pays'), ('departement', 'Département'), ('site', 'Site')):
        if not str(data.get(key) or '').strip():
            return f"{label} requis."
    return None


def normalize_geo_payload(data):
    """Nettoie les espaces et applique les valeurs par défaut (localisation / secteur).

    Une localisation vide devient « Principale », un secteur vide « Principal » : ainsi toute
    ascension a une chaîne complète de lieux sans obliger l'utilisateur à tout remplir.
    Modifie `data` en place et le renvoie.
    """
    for key in ('pays', 'departement', 'localisation', 'site', 'secteur', 'sous_secteur', 'nom'):
        if isinstance(data.get(key), str):
            data[key] = data[key].strip()
    data['localisation'] = data.get('localisation') or 'Principale'
    data['secteur'] = data.get('secteur') or 'Principal'
    return data


def _get_or_create_pays(conn, uid, name):
    """Identifiant du pays `name` de l'utilisateur (créé s'il n'existe pas encore)."""
    row = conn.execute("SELECT id FROM pays WHERE name=? AND user_id=?", (name, uid)).fetchone()
    if row:
        return row['id']
    return conn.execute("INSERT INTO pays(name,user_id) VALUES(?,?)", (name, uid)).lastrowid


def _get_or_create(conn, table, values):
    """Identifiant de la ligne de `table` correspondant à `values` (colonne → valeur), créée si besoin."""
    # Le nom de la table et des colonnes vient du code (jamais de l'utilisateur) ; les valeurs sont passées en paramètres
    cols = list(values)
    where = ' AND '.join(f"{c}=?" for c in cols)
    row = conn.execute(f"SELECT id FROM {table} WHERE {where}", list(values.values())).fetchone()
    if row:
        return row['id']
    placeholders = ','.join('?' for _ in cols)
    return conn.execute(f"INSERT INTO {table}({','.join(cols)}) VALUES({placeholders})",
                        list(values.values())).lastrowid


def resolve_location(conn, uid, data):
    """Retrouve (ou crée) toute la chaîne de lieux d'une saisie et renvoie (secteur_id, sous_secteur_id).

    Le sous-secteur est facultatif : rien n'est créé s'il est laissé vide.
    """
    pays_id = _get_or_create_pays(conn, uid, data['pays'])
    departement_id = _get_or_create(conn, 'departement', {'name': data['departement'], 'pays_id': pays_id})
    localisation_id = _get_or_create(conn, 'localisation', {'name': data['localisation'], 'departement_id': departement_id})
    site_id = _get_or_create(conn, 'site', {'name': data['site'], 'localisation_id': localisation_id})
    secteur_id = _get_or_create(conn, 'secteur', {'name': data['secteur'], 'site_id': site_id})
    sous_secteur_id = None
    if data.get('sous_secteur'):
        sous_secteur_id = _get_or_create(conn, 'sous_secteur', {'name': data['sous_secteur'], 'secteur_id': secteur_id})
    return secteur_id, sous_secteur_id


def apply_ressenti(conn, data, secteur_id, sous_secteur_id):
    """Ressenti indicatif facultatif : s'applique au sous-secteur s'il y en a un, sinon au secteur.

    Une valeur absente ou inconnue de RESSENTI_LABELS est ignorée (l'ancien ressenti est conservé).
    """
    if data.get('ressenti') in RESSENTI_LABELS:
        table, item_id = ('sous_secteur', sous_secteur_id) if sous_secteur_id else ('secteur', secteur_id)
        conn.execute(f"UPDATE {table} SET ressenti=? WHERE id=?", (data['ressenti'], item_id))


# ─── Renommage et suppression ────────────────────────────────────────────────

def rename_item(conn, table, item_id, name, ressenti=None):
    """Renomme un élément ; pour un secteur / sous-secteur, met aussi à jour le ressenti.

    Lève sqlite3.IntegrityError si le nom existe déjà au même endroit.
    """
    # Seuls secteurs et sous-secteurs portent un ressenti ; un ressenti inconnu est effacé
    if table in ('secteur', 'sous_secteur'):
        if ressenti is not None and ressenti not in RESSENTI_LABELS:
            ressenti = None
        conn.execute(f"UPDATE {table} SET name=?, ressenti=? WHERE id=?", (name, ressenti, item_id))
    else:
        conn.execute(f"UPDATE {table} SET name=? WHERE id=?", (name, item_id))
    conn.commit()


def _ids(conn, sql, params):
    """Première colonne de toutes les lignes renvoyées (liste d'identifiants)."""
    return [r[0] for r in conn.execute(sql, params).fetchall()]


def _marks(values):
    """Les « ?,?,? » à mettre dans un IN (...) pour autant de valeurs."""
    return ','.join('?' for _ in values)


def delete_item(conn, uid, table, item_id):
    """Supprime un élément, tous ses niveaux enfants et toutes leurs ascensions
    (avec répétitions, longueurs, séances…)."""
    # On descend la hiérarchie en collectant les identifiants de chaque niveau concerné
    # (on part de l'élément supprimé : ses descendants seuls sont collectés, les niveaux au-dessus restent vides)
    dep_ids = loc_ids = site_ids = sec_ids = ss_ids = []
    if table == 'pays':
        dep_ids = _ids(conn, "SELECT id FROM departement WHERE pays_id=?", (item_id,))
    elif table == 'departement':
        dep_ids = [item_id]
    if table in ('pays', 'departement') and dep_ids:
        loc_ids = _ids(conn, f"SELECT id FROM localisation WHERE departement_id IN ({_marks(dep_ids)})", dep_ids)
    elif table == 'localisation':
        loc_ids = [item_id]
    if table in ('pays', 'departement', 'localisation') and loc_ids:
        site_ids = _ids(conn, f"SELECT id FROM site WHERE localisation_id IN ({_marks(loc_ids)})", loc_ids)
    elif table == 'site':
        site_ids = [item_id]
    if table in ('pays', 'departement', 'localisation', 'site') and site_ids:
        sec_ids = _ids(conn, f"SELECT id FROM secteur WHERE site_id IN ({_marks(site_ids)})", site_ids)
    elif table == 'secteur':
        sec_ids = [item_id]

    if table == 'sous_secteur':
        ss_ids = [item_id]
        asc_ids = _ids(conn, "SELECT id FROM ascension WHERE sous_secteur_id=? AND user_id=?", (item_id, uid))
    else:
        if sec_ids:
            ss_ids = _ids(conn, f"SELECT id FROM sous_secteur WHERE secteur_id IN ({_marks(sec_ids)})", sec_ids)
        # secteur_id reste renseigné pour les ascensions de sous-secteur : ce filtre les couvre aussi
        asc_ids = _ids(conn, f"SELECT id FROM ascension WHERE secteur_id IN ({_marks(sec_ids)}) AND user_id=?",
                       sec_ids + [uid]) if sec_ids else []

    # D'abord les ascensions (et leurs répétitions, longueurs, séances…), puis les lieux
    delete_ascensions(conn, asc_ids)
    # Du plus bas niveau au plus haut
    for level, ids in (('sous_secteur', ss_ids), ('secteur', sec_ids), ('site', site_ids),
                       ('localisation', loc_ids), ('departement', dep_ids)):
        if ids:
            conn.execute(f"DELETE FROM {level} WHERE id IN ({_marks(ids)})", ids)
            # Les rattachements de topos à ces lieux disparaissent avec eux (les topos, eux, restent dans la bibliothèque)
            conn.execute(f"DELETE FROM topo_lieu WHERE niveau=? AND lieu_id IN ({_marks(ids)})", [level] + list(ids))
    conn.execute("DELETE FROM topo_lieu WHERE niveau=? AND lieu_id=?", (table, item_id))
    conn.execute(f"DELETE FROM {table} WHERE id=?", (item_id,))
    conn.commit()


# ─── Exploration (page Stats, export PDF) ────────────────────────────────────

def get_geo_counts(conn, uid):
    """Nombre de pays / départements / localisations / sites / secteurs / sous-secteurs qui
    contiennent au moins une ascension réellement loguée (statut « log »).

    Un nœud qui ne contient que des projets ou de la tick list n'est pas compté, et l'exclusion
    remonte la hiérarchie. Le sous-secteur étant optionnel, il est rattaché en LEFT JOIN.
    """
    # Une ligne par chemin de lieux distinct qui contient au moins un log ; on compte ensuite les ids uniques par niveau
    geo_rows = conn.execute("""
        SELECT DISTINCT p.id as pays_id, d.id as dep_id, l.id as loc_id,
               si.id as site_id, sec.id as sec_id, ss.id as ss_id
        FROM ascension a
        JOIN secteur sec ON a.secteur_id = sec.id
        JOIN site si ON sec.site_id = si.id
        JOIN localisation l ON si.localisation_id = l.id
        JOIN departement d ON l.departement_id = d.id
        JOIN pays p ON d.pays_id = p.id
        LEFT JOIN sous_secteur ss ON a.sous_secteur_id = ss.id
        WHERE a.user_id=? AND a.statut='log'
    """, (uid,)).fetchall()

    return {
        'nb_pays':          len({r['pays_id'] for r in geo_rows}),
        'nb_departements':  len({r['dep_id'] for r in geo_rows}),
        'nb_localisations': len({r['loc_id'] for r in geo_rows}),
        'nb_sites':         len({r['site_id'] for r in geo_rows}),
        'nb_secteurs':      len({r['sec_id'] for r in geo_rows}),
        'nb_sous_secteurs': len({r['ss_id'] for r in geo_rows if r['ss_id']}),
    }


def location_path(conn, secteur_id, uid):
    """Identifiants de toute la chaîne de lieux d'un secteur de l'utilisateur (None si introuvable).

    Sert à ouvrir automatiquement les bons niveaux du carnet après un ajout.
    """
    sec = conn.execute("SELECT * FROM secteur WHERE id=?", (secteur_id,)).fetchone()
    if not sec or not geo_owned(conn, 'secteur', sec['id'], uid):
        return None
    site = conn.execute("SELECT * FROM site WHERE id=?", (sec['site_id'],)).fetchone()
    loc = conn.execute("SELECT * FROM localisation WHERE id=?", (site['localisation_id'],)).fetchone()
    dep = conn.execute("SELECT * FROM departement WHERE id=?", (loc['departement_id'],)).fetchone()
    pays = conn.execute("SELECT * FROM pays WHERE id=?", (dep['pays_id'],)).fetchone()
    return {
        'secteur_id': sec['id'],
        'site_id': site['id'],
        'localisation_id': loc['id'],
        'departement_id': dep['id'],
        'pays_id': pays['id'],
    }
