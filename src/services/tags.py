"""Listes de choix personnalisables : fixations, coinceurs, type de roche, type de grimpe.

Deux notions à ne pas confondre : les « propositions » (table `tag_option`) sont la liste de choix
propre à chaque utilisateur et à chaque catégorie ; les « choix » d'une ascension (table
`ascension_tag`) sont ceux qu'il a cochés parmi elles. Supprimer une proposition ne touche pas aux
ascensions qui l'avaient déjà cochée.
"""
from ..constants import MAX_TAGS_PER_LIST, TAG_CATS, TAG_MAX_LEN, TAG_ORDER
from ..errors import ValidationError


def cats_for_type(asc_type):
    """Catégories de choix proposées pour ce type d'ascension (fixations : voie / grande voie ;
    coinceurs : trad ; roche et type de grimpe : tous)."""
    return [c for c in TAG_ORDER if TAG_CATS[c]['types'] is None or asc_type in TAG_CATS[c]['types']]


def clean_tag_name(v):
    """Nom de choix nettoyé (espaces multiples → un seul), ou None s'il est vide / trop long."""
    if not isinstance(v, str):
        return None
    v = ' '.join(v.split())
    if not v or len(v) > TAG_MAX_LEN:
        return None
    return v


def get_options(conn, uid, cat):
    """Propositions de l'utilisateur pour une catégorie.

    Au premier accès, la liste est remplie avec les propositions de départ ; ensuite
    l'utilisateur la fait évoluer (ajouts, suppressions).
    """
    # `tag_seed` retient que la liste de départ a déjà été créée : sans elle, une proposition de
    # départ supprimée par l'utilisateur reviendrait à chaque affichage
    seeded = conn.execute("SELECT 1 FROM tag_seed WHERE user_id=? AND categorie=?", (uid, cat)).fetchone()
    if not seeded:
        for nom in TAG_CATS[cat]['defaults']:
            conn.execute("INSERT OR IGNORE INTO tag_option(user_id, categorie, nom) VALUES(?,?,?)", (uid, cat, nom))
        conn.execute("INSERT OR IGNORE INTO tag_seed(user_id, categorie) VALUES(?,?)", (uid, cat))
        conn.commit()
    return [r[0] for r in conn.execute(
        "SELECT nom FROM tag_option WHERE user_id=? AND categorie=? ORDER BY id", (uid, cat))]


def all_options(conn, uid):
    """Toutes les listes de propositions de l'utilisateur, par catégorie."""
    return {c: get_options(conn, uid, c) for c in TAG_ORDER}


def add_option(conn, uid, cat, raw_name):
    """Ajoute une proposition. Si elle existe déjà (casse ignorée), renvoie la version existante.

    Retourne (nom, existait_deja).
    """
    if cat not in TAG_CATS:
        raise ValidationError('Catégorie inconnue.')
    nom = clean_tag_name(raw_name)
    if not nom:
        raise ValidationError(f"Le nom doit faire entre 1 et {TAG_MAX_LEN} caractères.")
    # casefold : comparaison insensible à la casse (« calcaire » = « Calcaire »)
    existing = get_options(conn, uid, cat)
    for e in existing:
        if e.casefold() == nom.casefold():
            return e, True
    if len(existing) >= MAX_TAGS_PER_LIST:
        raise ValidationError(f'Trop de propositions dans cette liste ({MAX_TAGS_PER_LIST} maximum).')
    conn.execute("INSERT INTO tag_option(user_id, categorie, nom) VALUES(?,?,?)", (uid, cat, nom))
    conn.commit()
    return nom, False


def delete_option(conn, uid, cat, raw_name):
    """Retire une proposition de la liste (les ascensions qui l'avaient choisie la gardent)."""
    if cat not in TAG_CATS:
        raise ValidationError('Catégorie inconnue.')
    nom = clean_tag_name(raw_name)
    if not nom:
        raise ValidationError('Nom invalide.')
    get_options(conn, uid, cat)    # s'assure que la liste de départ existe (évite qu'elle revienne ensuite)
    conn.execute("DELETE FROM tag_option WHERE user_id=? AND categorie=? AND nom=? COLLATE NOCASE", (uid, cat, nom))
    conn.commit()


def clean_tag_selection(raw_tags, allowed_cats):
    """Choix retenus pour une ascension : {catégorie: [noms]} limité aux catégories autorisées,
    sans doublon (casse ignorée).

    Les noms invalides sont ignorés en silence ; une liste qui n'est pas une liste, ou trop longue,
    lève ValidationError.
    """
    raw_tags = raw_tags if isinstance(raw_tags, dict) else {}
    result = {}
    for c in allowed_cats:
        seen, names = set(), []
        vals = raw_tags.get(c) or []
        if not isinstance(vals, list) or len(vals) > MAX_TAGS_PER_LIST:
            raise ValidationError('Liste de choix invalide.')
        for v in vals:
            nom = clean_tag_name(v)
            if nom and nom.casefold() not in seen:
                seen.add(nom.casefold())
                names.append(nom)
        result[c] = names
    return result


def replace_ascension_tags(conn, asc_id, selection):
    """Remplace les choix d'une ascension (toutes catégories confondues) par `selection`."""
    # On efface d'abord tous les choix existants puis on réinsère : plus simple que de comparer
    marks = ','.join('?' for _ in TAG_CATS)
    conn.execute(f"DELETE FROM ascension_tag WHERE ascension_id=? AND categorie IN ({marks})", [asc_id] + list(TAG_CATS))
    for cat, names in selection.items():
        for nom in names:
            conn.execute("INSERT OR IGNORE INTO ascension_tag(ascension_id, categorie, nom) VALUES(?,?,?)",
                         (asc_id, cat, nom))


def get_ascension_tags(conn, asc_id, cats):
    """Choix retenus d'une ascension pour les catégories données : {catégorie: [noms]} (liste vide si aucun)."""
    tags = {c: [] for c in cats}
    for t in conn.execute("SELECT categorie, nom FROM ascension_tag WHERE ascension_id=? ORDER BY id", (asc_id,)):
        if t['categorie'] in tags:
            tags[t['categorie']].append(t['nom'])
    return tags
