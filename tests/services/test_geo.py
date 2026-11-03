"""src/services/geo.py : lieux (création à la volée, propriété, renommage, suppression, compteurs)."""
import sqlite3

import pytest

from src.services import geo
from tests.helpers import DEFAULT_PLACE, add_ascension, scalar


# ─── Validation et normalisation ─────────────────────────────────────────────

@pytest.mark.parametrize('missing, message', [('pays', 'Pays requis.'), ('departement', 'Département requis.'), ('site', 'Site requis.')])
def test_validate_requires_pays_departement_site(missing, message):
    data = {**DEFAULT_PLACE}
    data[missing] = '   '
    assert geo.validate_geo_payload(data) == message


def test_validate_missing_key_and_ok():
    assert geo.validate_geo_payload({'pays': 'F', 'departement': 'D'}) == 'Site requis.'
    assert geo.validate_geo_payload(DEFAULT_PLACE) is None
    assert geo.validate_geo_payload({'pays': None, 'departement': 'D', 'site': 'S'}) == 'Pays requis.'


def test_normalize_strips_and_defaults():
    data = geo.normalize_geo_payload({'pays': ' France ', 'departement': 'D', 'site': ' S ', 'nom': ' x ', 'localisation': '', 'secteur': None})
    assert data['pays'] == 'France' and data['site'] == 'S' and data['nom'] == 'x'
    assert data['localisation'] == 'Principale' and data['secteur'] == 'Principal'


def test_normalize_keeps_given_values():
    data = geo.normalize_geo_payload({'localisation': ' Loc ', 'secteur': ' Sec ', 'sous_secteur': ' Sous '})
    assert (data['localisation'], data['secteur'], data['sous_secteur']) == ('Loc', 'Sec', 'Sous')


# ─── Résolution d'une chaîne de lieux ────────────────────────────────────────

def test_resolve_creates_whole_chain(conn, uid):
    sec, ss = geo.resolve_location(conn, uid, DEFAULT_PLACE)
    assert ss is None
    for table in ('pays', 'departement', 'localisation', 'site', 'secteur'):
        assert scalar(conn, f'SELECT COUNT(*) FROM {table}') == 1
    assert scalar(conn, 'SELECT COUNT(*) FROM sous_secteur') == 0
    assert scalar(conn, 'SELECT name FROM secteur WHERE id=?', sec) == 'En-Vau'


def test_resolve_is_idempotent(conn, uid):
    first = geo.resolve_location(conn, uid, DEFAULT_PLACE)
    second = geo.resolve_location(conn, uid, DEFAULT_PLACE)
    assert first == second
    assert scalar(conn, 'SELECT COUNT(*) FROM site') == 1


def test_resolve_with_sous_secteur(conn, uid):
    sec, ss = geo.resolve_location(conn, uid, {**DEFAULT_PLACE, 'sous_secteur': 'Face Nord'})
    assert ss is not None and scalar(conn, 'SELECT secteur_id FROM sous_secteur WHERE id=?', ss) == sec
    again = geo.resolve_location(conn, uid, {**DEFAULT_PLACE, 'sous_secteur': 'Face Nord'})
    assert again == (sec, ss)


def test_resolve_shares_parents_between_sectors(conn, uid):
    geo.resolve_location(conn, uid, DEFAULT_PLACE)
    geo.resolve_location(conn, uid, {**DEFAULT_PLACE, 'secteur': 'Autre'})
    assert scalar(conn, 'SELECT COUNT(*) FROM site') == 1 and scalar(conn, 'SELECT COUNT(*) FROM secteur') == 2


def test_resolve_keeps_users_separate(conn, uid, uid2):
    a = geo.resolve_location(conn, uid, DEFAULT_PLACE)
    b = geo.resolve_location(conn, uid2, DEFAULT_PLACE)
    assert a != b and scalar(conn, 'SELECT COUNT(*) FROM pays') == 2


def test_apply_ressenti_on_secteur_then_sous_secteur(conn, uid):
    sec, ss = geo.resolve_location(conn, uid, {**DEFAULT_PLACE, 'sous_secteur': 'Face Nord'})
    geo.apply_ressenti(conn, {'ressenti': 'dur'}, sec, ss)
    assert scalar(conn, 'SELECT ressenti FROM sous_secteur WHERE id=?', ss) == 'dur'
    assert scalar(conn, 'SELECT ressenti FROM secteur WHERE id=?', sec) is None
    geo.apply_ressenti(conn, {'ressenti': 'facile'}, sec, None)
    assert scalar(conn, 'SELECT ressenti FROM secteur WHERE id=?', sec) == 'facile'


def test_apply_ressenti_ignores_unknown_values(conn, uid):
    sec, ss = geo.resolve_location(conn, uid, DEFAULT_PLACE)
    geo.apply_ressenti(conn, {'ressenti': 'nimporte'}, sec, ss)
    geo.apply_ressenti(conn, {}, sec, ss)
    assert scalar(conn, 'SELECT ressenti FROM secteur WHERE id=?', sec) is None


# ─── Propriété et listes ─────────────────────────────────────────────────────

def test_geo_owned_for_every_level(conn, uid, uid2):
    sec, ss = geo.resolve_location(conn, uid, {**DEFAULT_PLACE, 'sous_secteur': 'S'})
    ids = {t: scalar(conn, f'SELECT id FROM {t}') for t in geo.PARENT_COLUMN}
    ids['pays'] = scalar(conn, 'SELECT id FROM pays')
    for table, item_id in ids.items():
        assert geo.geo_owned(conn, table, item_id, uid) is True
        assert geo.geo_owned(conn, table, item_id, uid2) is False
        assert geo.geo_owned(conn, table, 9999, uid) is False


def test_geo_owned_unknown_table(conn, uid):
    assert geo.geo_owned(conn, 'user', 1, uid) is False


def test_list_children_sorted_by_name(conn, uid):
    for s in ('Zèbre', 'Alpha', 'Moyen'):
        geo.resolve_location(conn, uid, {**DEFAULT_PLACE, 'secteur': s})
    site_id = scalar(conn, 'SELECT id FROM site')
    assert [c['name'] for c in geo.list_children(conn, 'secteur', site_id)] == ['Alpha', 'Moyen', 'Zèbre']
    assert geo.list_children(conn, 'secteur', 9999) == []


# ─── Renommage ───────────────────────────────────────────────────────────────

def test_rename_simple_level(conn, uid):
    geo.resolve_location(conn, uid, DEFAULT_PLACE)
    geo.rename_item(conn, 'site', 1, 'Nouveau nom')
    assert scalar(conn, 'SELECT name FROM site WHERE id=1') == 'Nouveau nom'


def test_rename_secteur_updates_ressenti(conn, uid):
    sec, _ = geo.resolve_location(conn, uid, DEFAULT_PLACE)
    geo.rename_item(conn, 'secteur', sec, 'Renommé', 'tres_dur')
    assert scalar(conn, 'SELECT ressenti FROM secteur WHERE id=?', sec) == 'tres_dur'
    geo.rename_item(conn, 'secteur', sec, 'Renommé', 'invalide')
    assert scalar(conn, 'SELECT ressenti FROM secteur WHERE id=?', sec) is None
    geo.rename_item(conn, 'secteur', sec, 'Renommé')
    assert scalar(conn, 'SELECT name FROM secteur WHERE id=?', sec) == 'Renommé'


def test_rename_duplicate_raises_integrity_error(conn, uid):
    geo.resolve_location(conn, uid, DEFAULT_PLACE)
    geo.resolve_location(conn, uid, {**DEFAULT_PLACE, 'secteur': 'Autre'})
    with pytest.raises(sqlite3.IntegrityError):
        geo.rename_item(conn, 'secteur', 2, 'En-Vau')


# ─── Suppression en cascade ──────────────────────────────────────────────────

def build_world(conn, uid):
    """Deux secteurs dans deux sites, dont un avec un sous-secteur, et des ascensions complètes."""
    a1 = add_ascension(conn, uid, 'A1', place={'sous_secteur': 'Face Nord'})
    a2 = add_ascension(conn, uid, 'A2')
    a3 = add_ascension(conn, uid, 'A3', place={'site': 'Autre site', 'secteur': 'Autre secteur'})
    for a in (a1, a2, a3):
        conn.execute("INSERT INTO repetition(ascension_id, date) VALUES(?, '2026-02-01')", (a,))
        conn.execute("INSERT INTO seance(ascension_id, numero, nb_essais) VALUES(?,1,2)", (a,))
        conn.execute("INSERT INTO longueur(ascension_id, numero) VALUES(?,1)", (a,))
        conn.execute("INSERT INTO ascension_tag(ascension_id, categorie, nom) VALUES(?, 'roche', 'Grès')", (a,))
        conn.execute("INSERT INTO reequipement(ascension_id, nom) VALUES(?, 'P')", (a,))
    conn.commit()
    return a1, a2, a3


def counts(conn, *tables):
    return {t: scalar(conn, f'SELECT COUNT(*) FROM {t}') for t in tables}


CHILD_TABLES = ('repetition', 'seance', 'longueur', 'ascension_tag', 'reequipement')


def test_delete_sous_secteur_removes_only_its_ascensions(conn, uid):
    a1, a2, a3 = build_world(conn, uid)
    geo.delete_item(conn, uid, 'sous_secteur', scalar(conn, 'SELECT id FROM sous_secteur'))
    assert scalar(conn, 'SELECT COUNT(*) FROM ascension') == 2
    assert scalar(conn, 'SELECT COUNT(*) FROM ascension WHERE id=?', a1) == 0
    assert scalar(conn, 'SELECT COUNT(*) FROM sous_secteur') == 0
    assert all(v == 2 for v in counts(conn, *CHILD_TABLES).values())


def test_delete_secteur_removes_its_sous_secteurs_and_ascensions(conn, uid):
    a1, a2, a3 = build_world(conn, uid)
    sec = scalar(conn, "SELECT id FROM secteur WHERE name='En-Vau'")
    geo.delete_item(conn, uid, 'secteur', sec)
    assert [r[0] for r in conn.execute('SELECT id FROM ascension')] == [a3]
    assert scalar(conn, 'SELECT COUNT(*) FROM sous_secteur') == 0
    assert scalar(conn, 'SELECT COUNT(*) FROM secteur') == 1
    assert all(v == 1 for v in counts(conn, *CHILD_TABLES).values())


def test_delete_site_cascades(conn, uid):
    build_world(conn, uid)
    geo.delete_item(conn, uid, 'site', scalar(conn, "SELECT id FROM site WHERE name='Calanques'"))
    assert scalar(conn, 'SELECT COUNT(*) FROM ascension') == 1
    assert counts(conn, 'site', 'secteur', 'sous_secteur') == {'site': 1, 'secteur': 1, 'sous_secteur': 0}


@pytest.mark.parametrize('table', ['localisation', 'departement', 'pays'])
def test_delete_higher_levels_remove_everything_below(conn, uid, table):
    build_world(conn, uid)
    geo.delete_item(conn, uid, table, scalar(conn, f'SELECT id FROM {table}'))
    for t in ('ascension', 'secteur', 'site', 'sous_secteur') + CHILD_TABLES:
        assert scalar(conn, f'SELECT COUNT(*) FROM {t}') == 0, t
    assert scalar(conn, f'SELECT COUNT(*) FROM {table}') == 0


def test_delete_does_not_touch_other_users(conn, uid, uid2):
    build_world(conn, uid)
    other = add_ascension(conn, uid2, 'Autre compte')
    geo.delete_item(conn, uid, 'pays', scalar(conn, 'SELECT id FROM pays WHERE user_id=?', uid))
    assert [r[0] for r in conn.execute('SELECT id FROM ascension')] == [other]


def test_delete_empty_secteur(conn, uid):
    sec, _ = geo.resolve_location(conn, uid, DEFAULT_PLACE)
    geo.delete_item(conn, uid, 'secteur', sec)
    assert scalar(conn, 'SELECT COUNT(*) FROM secteur') == 0


# ─── Compteurs d'exploration ─────────────────────────────────────────────────

def test_geo_counts_empty(conn, uid):
    assert geo.get_geo_counts(conn, uid) == {'nb_pays': 0, 'nb_departements': 0, 'nb_localisations': 0,
                                             'nb_sites': 0, 'nb_secteurs': 0, 'nb_sous_secteurs': 0}


def test_geo_counts_only_logged_ascensions(conn, uid):
    add_ascension(conn, uid, 'Log', place={'sous_secteur': 'S1'})
    add_ascension(conn, uid, 'Log 2', place={'secteur': 'Autre'})
    add_ascension(conn, uid, 'Projet', statut='projet', place={'site': 'Projet site'})
    add_ascension(conn, uid, 'Envie', statut='ticklist', place={'pays': 'Espagne'})
    assert geo.get_geo_counts(conn, uid) == {'nb_pays': 1, 'nb_departements': 1, 'nb_localisations': 1,
                                             'nb_sites': 1, 'nb_secteurs': 2, 'nb_sous_secteurs': 1}


def test_geo_counts_ignore_other_users(conn, uid, uid2):
    add_ascension(conn, uid2, 'Autre')
    assert geo.get_geo_counts(conn, uid)['nb_pays'] == 0


def test_geo_counts_distinct_levels(conn, uid):
    for i in range(3):
        add_ascension(conn, uid, f'A{i}')
    add_ascension(conn, uid, 'B', place={'departement': 'Gard', 'site': 'Ailleurs'})
    c = geo.get_geo_counts(conn, uid)
    assert (c['nb_pays'], c['nb_departements'], c['nb_sites']) == (1, 2, 2)


# ─── Chemin d'un secteur ─────────────────────────────────────────────────────

def test_location_path(conn, uid):
    a = add_ascension(conn, uid, 'A')
    sec = scalar(conn, 'SELECT secteur_id FROM ascension WHERE id=?', a)
    assert geo.location_path(conn, sec, uid) == {'secteur_id': sec, 'site_id': 1, 'localisation_id': 1,
                                                 'departement_id': 1, 'pays_id': 1}


def test_location_path_unknown_or_foreign(conn, uid, uid2):
    a = add_ascension(conn, uid, 'A')
    sec = scalar(conn, 'SELECT secteur_id FROM ascension WHERE id=?', a)
    assert geo.location_path(conn, 9999, uid) is None
    assert geo.location_path(conn, sec, uid2) is None
