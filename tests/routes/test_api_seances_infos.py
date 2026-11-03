"""API des séances, de la fiche d'informations, des listes de choix et des suggestions de noms."""
import pytest

from tests.helpers import asc_payload


def project(client, **over):
    return client.post('/api/ascension', json=asc_payload(statut='projet', **over)).get_json()['id']


def add(client, a, **body):
    return client.post(f'/api/ascension/{a}/seances', json={'date': '2026-02-01', 'nb_essais': 3, **body})


# ─── Séances ─────────────────────────────────────────────────────────────────

def test_list_seances_empty(client):
    a = project(client)
    d = client.get(f'/api/ascension/{a}/seances').get_json()
    assert (d['nom'], d['type'], d['statut'], d['seances'], d['nb_seances'], d['total_essais']) == ('Bloc A', 'bloc', 'projet', [], 0, 0)
    assert d['lieu'] == 'Calanques › En-Vau'


def test_list_seances_lieu_with_sous_secteur(client):
    a = project(client, sous_secteur='Nord')
    assert client.get(f'/api/ascension/{a}/seances').get_json()['lieu'] == 'Calanques › En-Vau › Nord'


def test_add_seances_are_numbered_and_summed(client, dbq):
    a = project(client)
    r1, r2 = add(client, a).get_json(), add(client, a, nb_essais=4, commentaire='mieux').get_json()
    assert (r1['numero'], r2['numero']) == (1, 2) and r1['success']
    assert dbq('SELECT nb_essais_projet FROM ascension')[0]['nb_essais_projet'] == 7
    d = client.get(f'/api/ascension/{a}/seances').get_json()
    assert d['nb_seances'] == 2 and d['total_essais'] == 7 and d['seances'][1]['commentaire'] == 'mieux'


@pytest.mark.parametrize('body', [{'date': ''}, {'date': '31/12/2026'}, {'nb_essais': 0}, {'nb_essais': 1000},
                                  {'nb_essais': 'x'}, {'commentaire': 'x' * 5001}])
def test_add_seance_validation(client, body):
    a = project(client)
    assert add(client, a, **body).status_code == 400


def test_add_seance_to_foreign_ascension(client, client2):
    a = project(client)
    assert add(client2, a).status_code == 404


def test_seance_on_a_log_is_allowed(client):
    a = client.post('/api/ascension', json=asc_payload()).get_json()['id']
    assert add(client, a).status_code == 200


def test_update_seance(client, dbq):
    a = project(client)
    sid = add(client, a).get_json()['id']
    assert client.put(f'/api/seance/{sid}', json={'nb_essais': 9}).status_code == 200
    row = dbq('SELECT * FROM seance WHERE id=?', sid)[0]
    assert (row['nb_essais'], row['date']) == (9, '2026-02-01')        # champs non fournis inchangés
    assert dbq('SELECT nb_essais_projet FROM ascension')[0]['nb_essais_projet'] == 9
    client.put(f'/api/seance/{sid}', json={'date': '', 'commentaire': 'ok'})
    row = dbq('SELECT * FROM seance WHERE id=?', sid)[0]
    assert row['date'] is None and row['commentaire'] == 'ok'


def test_update_seance_errors(client, client2):
    a = project(client)
    sid = add(client, a).get_json()['id']
    assert client.put(f'/api/seance/{sid}', json={'nb_essais': 0}).status_code == 400
    assert client.put(f'/api/seance/{sid}', json={'date': 'zzz'}).status_code == 400
    assert client2.put(f'/api/seance/{sid}', json={'nb_essais': 2}).status_code == 404
    assert client.put('/api/seance/9999', json={'nb_essais': 2}).status_code == 404


def test_delete_seance_renumbers(client, dbq):
    a = project(client)
    ids = [add(client, a, nb_essais=n).get_json()['id'] for n in (1, 2, 4)]
    assert client.delete(f'/api/seance/{ids[0]}').get_json() == {'success': True}
    assert [(r['numero'], r['nb_essais']) for r in dbq('SELECT numero, nb_essais FROM seance ORDER BY numero')] == [(1, 2), (2, 4)]
    assert dbq('SELECT nb_essais_projet FROM ascension')[0]['nb_essais_projet'] == 6


def test_delete_seance_not_owned(client, client2):
    a = project(client)
    sid = add(client, a).get_json()['id']
    assert client2.delete(f'/api/seance/{sid}').status_code == 404
    assert client2.get(f'/api/ascension/{a}/seances').status_code == 404


# ─── Fiche d'informations ────────────────────────────────────────────────────

def test_infos_roundtrip(client):
    a = client.post('/api/ascension', json=asc_payload(type='voie', grimpe='tete')).get_json()['id']
    body = {'topo_type': 'pdf', 'topo_nom': 'Topo', 'topo_lien': 'exemple.fr/t.pdf', 'annee_ouverture': 1999, 'ouvreur': 'Bob',
            'reequipements': [{'nom': 'Club', 'annee': 2015}], 'tags': {'roche': ['Calcaire'], 'fixation': ['Spits']}}
    assert client.put(f'/api/ascension/{a}/infos', json=body).get_json() == {'success': True}
    d = client.get(f'/api/ascension/{a}/infos').get_json()
    assert d['topo']['topo_lien'] == 'https://exemple.fr/t.pdf' and d['ouverture'] == {'annee': 1999, 'ouvreur': 'Bob'}
    assert d['reequipements'] == [{'nom': 'Club', 'annee': 2015}]
    assert d['tags']['roche'] == ['Calcaire'] and d['tags']['fixation'] == ['Spits']


@pytest.mark.parametrize('body', [
    {'topo_type': 'inconnu'}, {'topo_type': 'pdf', 'topo_lien': 'javascript:alert(1)'}, {'topo_type': 'pdf', 'topo_lien': 'a b'},
    {'annee_ouverture': 1700}, {'annee_ouverture': 'abc'}, {'topo_type': 'papier', 'topo_annee': 3000},
    {'reequipements': 'x'}, {'reequipements': [{'nom': 'a', 'annee': 1000}]}, {'reequipements': [{'nom': 'x'}] * 21},
    {'ouvreur': 'x' * 101}, {'tags': {'roche': 'Grès'}},
])
def test_infos_validation(client, body):
    a = client.post('/api/ascension', json=asc_payload()).get_json()['id']
    r = client.put(f'/api/ascension/{a}/infos', json=body)
    assert r.status_code == 400 and r.get_json()['error']


def test_infos_not_owned(client, client2):
    a = client.post('/api/ascension', json=asc_payload()).get_json()['id']
    assert client2.get(f'/api/ascension/{a}/infos').status_code == 404
    assert client2.put(f'/api/ascension/{a}/infos', json={}).status_code == 404
    assert client.get('/api/ascension/9999/infos').status_code == 404


# ─── Listes de choix ─────────────────────────────────────────────────────────

def test_options_list(client):
    d = client.get('/api/options').get_json()
    assert set(d['options']) == {'grimpe', 'roche', 'fixation', 'coinceur'} == set(d['labels'])
    assert 'Grès' in d['options']['roche'] and d['labels']['roche'] == 'Type de roche'


def test_add_option(client):
    assert client.post('/api/options', json={'categorie': 'coinceur', 'nom': ' Tricams '}).get_json() == {
        'success': True, 'nom': 'Tricams', 'existait': False}
    assert client.post('/api/options', json={'categorie': 'coinceur', 'nom': 'tricams'}).get_json()['existait'] is True
    assert 'Tricams' in client.get('/api/options').get_json()['options']['coinceur']


@pytest.mark.parametrize('body', [{}, {'categorie': 'bidon', 'nom': 'x'}, {'categorie': 'roche'}, {'categorie': 'roche', 'nom': ''},
                                  {'categorie': 'roche', 'nom': 'x' * 41}])
def test_add_option_validation(client, body):
    assert client.post('/api/options', json=body).status_code in (400, 500) and \
        client.post('/api/options', json=body).status_code == 400


def test_delete_option(client):
    assert client.delete('/api/options', json={'categorie': 'roche', 'nom': 'Grès'}).get_json() == {'success': True}
    assert 'Grès' not in client.get('/api/options').get_json()['options']['roche']
    assert client.delete('/api/options', json={'categorie': 'bidon', 'nom': 'x'}).status_code == 400
    assert client.delete('/api/options', json={'categorie': 'roche'}).status_code == 400


def test_options_are_per_user(client, client2):
    client.post('/api/options', json={'categorie': 'roche', 'nom': 'Silex'})
    assert 'Silex' not in client2.get('/api/options').get_json()['options']['roche']


# ─── Suggestions de noms ─────────────────────────────────────────────────────

def test_noms(client, client2):
    client.post('/api/ascension', json=asc_payload(nom='Zèbre'))
    client2.post('/api/ascension', json=asc_payload(nom='Intrus', pays='Italie'))
    d = client.get('/api/noms').get_json()
    assert set(d) == {'ascensions', 'lieux', 'ouvreurs', 'topos'}
    assert d['ascensions'] == ['Zèbre'] and 'France' in d['lieux'] and 'Italie' not in d['lieux']
