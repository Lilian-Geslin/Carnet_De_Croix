"""src/services/carnet.py : arbre des lieux ne contenant que des logs."""
from src.services.carnet import build_carnet_tree
from tests.helpers import add_ascension


def test_empty_tree(conn, uid):
    assert build_carnet_tree(conn, uid) == []


def test_tree_has_full_hierarchy(conn, uid):
    add_ascension(conn, uid, 'A')
    t = build_carnet_tree(conn, uid)
    assert t[0]['pays']['name'] == 'France'
    dep = t[0]['departements'][0]
    assert dep['departement']['name'] == 'Bouches-du-Rhône'
    site = dep['localisations'][0]['sites'][0]
    sec = site['secteurs'][0]
    assert (site['site']['name'], sec['sec']['name'], sec['total_count']) == ('Calanques', 'En-Vau', 1)
    assert sec['ascensions'][0]['asc']['nom'] == 'A'


def test_projets_and_ticklist_are_hidden(conn, uid):
    add_ascension(conn, uid, 'P', statut='projet')
    add_ascension(conn, uid, 'T', statut='ticklist')
    assert build_carnet_tree(conn, uid) == []


def test_sector_with_only_projects_is_hidden_but_others_stay(conn, uid):
    add_ascension(conn, uid, 'Log', place={'secteur': 'Visible'})
    add_ascension(conn, uid, 'Projet', statut='projet', place={'secteur': 'Caché'})
    secteurs = build_carnet_tree(conn, uid)[0]['departements'][0]['localisations'][0]['sites'][0]['secteurs']
    assert [s['sec']['name'] for s in secteurs] == ['Visible']


def test_empty_geo_nodes_are_hidden(conn, uid):
    add_ascension(conn, uid, 'P', statut='projet', place={'pays': 'Espagne'})
    add_ascension(conn, uid, 'L', place={'pays': 'France'})
    assert [p['pays']['name'] for p in build_carnet_tree(conn, uid)] == ['France']


def test_sous_secteurs_listed_with_their_ascensions(conn, uid):
    add_ascension(conn, uid, 'Directe')
    add_ascension(conn, uid, 'Dans Nord', place={'sous_secteur': 'Nord'})
    add_ascension(conn, uid, 'Dans Sud (projet)', statut='projet', place={'sous_secteur': 'Sud'})
    sec = build_carnet_tree(conn, uid)[0]['departements'][0]['localisations'][0]['sites'][0]['secteurs'][0]
    assert sec['total_count'] == 2
    assert [c['asc']['nom'] for c in sec['ascensions']] == ['Directe']
    assert [s['sous_secteur']['name'] for s in sec['sous_secteurs']] == ['Nord']   # Sud masqué : aucun log


def test_ascensions_sorted_hardest_first(conn, uid):
    add_ascension(conn, uid, 'Facile', cotation='5a')
    add_ascension(conn, uid, 'Dur', cotation='7a')
    add_ascension(conn, uid, 'Moyen', cotation='6b')
    sec = build_carnet_tree(conn, uid)[0]['departements'][0]['localisations'][0]['sites'][0]['secteurs'][0]
    assert [c['asc']['nom'] for c in sec['ascensions']] == ['Dur', 'Moyen', 'Facile']


def test_places_sorted_by_name(conn, uid):
    for pays in ('Suisse', 'Allemagne', 'France'):
        add_ascension(conn, uid, 'X' + pays, place={'pays': pays})
    assert [p['pays']['name'] for p in build_carnet_tree(conn, uid)] == ['Allemagne', 'France', 'Suisse']


def test_cards_carry_repetitions_longueurs_and_formatted_dates(conn, uid):
    a = add_ascension(conn, uid, 'GV', type='grande_voie', cotation='5a', cotation_haute='6a',
                      longueurs=[{'cotation': '5a'}, {'cotation': '6a'}], date='2026-04-09')
    conn.execute("INSERT INTO repetition(ascension_id, date) VALUES(?, '2026-05-01')", (a,))
    conn.execute("INSERT INTO repetition(ascension_id, date) VALUES(?, '2026-06-01')", (a,))
    card = build_carnet_tree(conn, uid)[0]['departements'][0]['localisations'][0]['sites'][0]['secteurs'][0]['ascensions'][0]
    assert card['asc']['date_fmt'] == '09/04/2026'
    assert [r['date'] for r in card['reps']] == ['2026-06-01', '2026-05-01']
    assert card['reps'][0]['date_fmt'] == '01/06/2026'
    assert [l['numero'] for l in card['longueurs']] == [1, 2]


def test_tree_is_per_user(conn, uid, uid2):
    add_ascension(conn, uid2, 'Autre')
    assert build_carnet_tree(conn, uid) == []
