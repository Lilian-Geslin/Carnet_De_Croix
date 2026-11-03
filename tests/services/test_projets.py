"""src/services/projets.py."""
from src.services import projets
from tests.helpers import add_ascension


def add_seance(conn, asc, numero, nb, date):
    conn.execute('INSERT INTO seance(ascension_id, numero, date, nb_essais) VALUES(?,?,?,?)', (asc, numero, date, nb))


def test_only_projects_of_the_user(conn, uid, uid2):
    add_ascension(conn, uid, 'P', statut='projet')
    add_ascension(conn, uid, 'L')
    add_ascension(conn, uid, 'T', statut='ticklist')
    add_ascension(conn, uid2, 'Autre', statut='projet')
    assert [p['nom'] for p in projets.list_projets(conn, uid)] == ['P']


def test_empty(conn, uid):
    assert projets.list_projets(conn, uid) == []


def test_sorted_by_name(conn, uid):
    for n in ('Zéta', 'Alpha', 'Milieu'):
        add_ascension(conn, uid, n, statut='projet')
    assert [p['nom'] for p in projets.list_projets(conn, uid)] == ['Alpha', 'Milieu', 'Zéta']


def test_project_without_seance(conn, uid):
    add_ascension(conn, uid, 'P', statut='projet', cotation='7a')
    p = projets.list_projets(conn, uid)[0]
    assert (p['seances'], p['nb_seances'], p['total_essais'], p['next_numero'], p['last_seance'],
            p['last_date'], p['max_essais']) == ([], 0, 0, 1, None, '', 0)
    assert p['cot_idx'] >= 0


def test_project_totals_with_seances(conn, uid):
    a = add_ascension(conn, uid, 'P', statut='projet')
    add_seance(conn, a, 1, 3, '2026-02-01')
    add_seance(conn, a, 2, 8, '2026-03-05')
    add_seance(conn, a, 3, 1, None)
    p = projets.list_projets(conn, uid)[0]
    assert (p['nb_seances'], p['total_essais'], p['next_numero'], p['max_essais']) == (3, 12, 4, 8)
    assert p['last_date'] == '2026-03-05' and p['last_seance']['numero'] == 3
    assert p['seances'][0]['date_fmt'] == '01/02/2026'


def test_project_carries_location_names(conn, uid):
    add_ascension(conn, uid, 'P', statut='projet', place={'sous_secteur': 'Nord'})
    p = projets.list_projets(conn, uid)[0]
    assert (p['site_name'], p['secteur_name'], p['sous_secteur_name'], p['pays_name']) == ('Calanques', 'En-Vau', 'Nord', 'France')
    assert p['site_id'] and p['secteur_id_geo']


def test_grande_voie_project_uses_high_grade_for_index(conn, uid):
    add_ascension(conn, uid, 'Facile', statut='projet', cotation='6a')
    add_ascension(conn, uid, 'GV', statut='projet', type='grande_voie', cotation='5a', cotation_haute='7a')
    by = {p['nom']: p for p in projets.list_projets(conn, uid)}
    assert by['GV']['cot_idx'] > by['Facile']['cot_idx']


def test_unknown_grade_gives_negative_index(conn, uid):
    add_ascension(conn, uid, 'P', statut='projet', cotation=None)
    assert projets.list_projets(conn, uid)[0]['cot_idx'] < 0
