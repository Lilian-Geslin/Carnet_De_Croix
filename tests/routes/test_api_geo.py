"""API des lieux : listes, renommage, suppression."""
import pytest

from tests.helpers import asc_payload


@pytest.fixture
def placed(client):
    client.post('/api/ascension', json=asc_payload(sous_secteur='Nord'))
    return client


def ids(dbq, table):
    return dbq(f'SELECT id FROM {table}')[0]['id']


def test_pays_list(placed):
    assert [p['name'] for p in placed.get('/api/geo/pays').get_json()] == ['France']


def test_pays_list_is_per_user(placed, client2):
    assert client2.get('/api/geo/pays').get_json() == []


@pytest.mark.parametrize('url, parent, expected', [
    ('departements', 'pays', 'Bouches-du-Rhône'), ('localisations', 'departement', 'Marseille'),
    ('sites', 'localisation', 'Calanques'), ('secteurs', 'site', 'En-Vau'), ('sous_secteurs', 'secteur', 'Nord'),
])
def test_children_lists(placed, dbq, url, parent, expected):
    assert [c['name'] for c in placed.get(f'/api/geo/{url}/{ids(dbq, parent)}').get_json()] == [expected]


@pytest.mark.parametrize('url, parent', [('departements', 'pays'), ('localisations', 'departement'), ('sites', 'localisation'),
                                         ('secteurs', 'site'), ('sous_secteurs', 'secteur')])
def test_children_of_foreign_or_unknown_parent_is_empty(placed, client2, dbq, url, parent):
    assert client2.get(f'/api/geo/{url}/{ids(dbq, parent)}').get_json() == []
    assert placed.get(f'/api/geo/{url}/9999').get_json() == []


@pytest.mark.parametrize('url', ['departements', 'localisations', 'sites', 'secteurs', 'sous_secteurs'])
def test_list_routes_refuse_post(placed, url):
    assert placed.post(f'/api/geo/{url}/1').status_code == 405


def test_rename(placed, dbq):
    r = placed.put(f"/api/geo/site/{ids(dbq, 'site')}", json={'name': '  Nouveau  '})
    assert r.get_json() == {'success': True} and dbq('SELECT name FROM site')[0]['name'] == 'Nouveau'


def test_rename_secteur_with_ressenti(placed, dbq):
    placed.put(f"/api/geo/secteur/{ids(dbq, 'secteur')}", json={'name': 'En-Vau', 'ressenti': 'dur'})
    assert dbq('SELECT ressenti FROM secteur')[0]['ressenti'] == 'dur'


@pytest.mark.parametrize('name', ['', '   '])
def test_rename_empty_name(placed, dbq, name):
    r = placed.put(f"/api/geo/site/{ids(dbq, 'site')}", json={'name': name})
    assert r.status_code == 400 and r.get_json()['error'] == 'Nom vide'


def test_rename_table_not_allowed(placed):
    assert placed.put('/api/geo/user/1', json={'name': 'x'}).status_code == 400
    assert placed.delete('/api/geo/ascension/1').status_code == 400


def test_rename_not_owned_or_unknown(placed, client2, dbq):
    assert client2.put(f"/api/geo/site/{ids(dbq, 'site')}", json={'name': 'x'}).status_code == 404
    assert placed.put('/api/geo/site/9999', json={'name': 'x'}).status_code == 404
    assert dbq('SELECT name FROM site')[0]['name'] == 'Calanques'


def test_rename_conflict(placed, dbq):
    placed.post('/api/ascension', json=asc_payload(nom='B', secteur='Autre'))
    sec = dbq("SELECT id FROM secteur WHERE name='Autre'")[0]['id']
    r = placed.put(f'/api/geo/secteur/{sec}', json={'name': 'En-Vau'})
    assert r.status_code == 409 and 'existe déjà' in r.get_json()['error']


def test_delete_cascades(placed, dbq):
    r = placed.delete(f"/api/geo/site/{ids(dbq, 'site')}")
    assert r.get_json() == {'success': True}
    for t in ('site', 'secteur', 'sous_secteur', 'ascension'):
        assert dbq(f'SELECT COUNT(*) AS n FROM {t}')[0]['n'] == 0
    assert dbq('SELECT COUNT(*) AS n FROM pays')[0]['n'] == 1


def test_delete_not_owned(placed, client2, dbq):
    assert client2.delete(f"/api/geo/pays/{ids(dbq, 'pays')}").status_code == 404
    assert dbq('SELECT COUNT(*) AS n FROM ascension')[0]['n'] == 1
