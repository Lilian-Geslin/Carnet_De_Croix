"""API des topos PDF (bibliothèque) et du bouton « Topo » des lieux."""
import io

import pytest

from src.constants import TOPO_PDF_MAX_BYTES
from tests.helpers import asc_payload

PDF = b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n'
PDF2 = PDF + b'% edition 2\n'


def make(client, **over):
    return client.post('/api/ascension', json=asc_payload(**over)).get_json()['id']


def upload(client, data=PDF, name='topo.pdf', field='fichier', **form):
    payload = {field: (io.BytesIO(data), name), **{k: str(v) for k, v in form.items()}}
    return client.post('/api/topos', data=payload, content_type='multipart/form-data')


def choose(client, asc_id, topo_id, **extra):
    return client.put(f'/api/ascension/{asc_id}/infos', json={'topo_type': 'pdf', 'topo_id': topo_id, **extra})


# ─── Bibliothèque ────────────────────────────────────────────────────────────

def test_upload_view_rename_delete_roundtrip(client):
    r = upload(client, name='Verdon.pdf')
    assert r.status_code == 200
    body = r.get_json()
    assert body['success'] is True and body['existait'] is False
    topo = body['topo']
    assert topo == {'id': topo['id'], 'nom': 'Verdon', 'fichier': 'Verdon.pdf', 'taille': len(PDF), 'nb': 0}

    got = client.get(f"/api/topos/{topo['id']}/pdf")
    assert got.status_code == 200 and got.data == PDF and got.mimetype == 'application/pdf'
    assert got.headers['X-Content-Type-Options'] == 'nosniff'
    assert got.headers['Content-Disposition'].startswith('inline') and 'Verdon.pdf' in got.headers['Content-Disposition']

    assert client.put(f"/api/topos/{topo['id']}", json={'nom': 'Verdon 2023'}).get_json() == {'success': True, 'nom': 'Verdon 2023'}
    assert client.get('/api/topos').get_json()[0]['nom'] == 'Verdon 2023'

    assert client.delete(f"/api/topos/{topo['id']}").get_json() == {'success': True, 'ascensions': 0}
    assert client.get(f"/api/topos/{topo['id']}/pdf").status_code == 404
    assert client.get('/api/topos').get_json() == []


def test_same_file_twice_is_stored_once(client, dbq):
    first = upload(client, name='a.pdf').get_json()
    again = upload(client, name='b.pdf', titre='Autre').get_json()
    assert again['existait'] is True and again['topo']['id'] == first['topo']['id']
    assert dbq('SELECT COUNT(*) AS n FROM topo')[0]['n'] == 1


def test_title_field(client):
    assert upload(client, titre='Topo Calanques 2023').get_json()['topo']['nom'] == 'Topo Calanques 2023'
    assert upload(client, data=PDF2, titre='x' * 200).status_code == 400


@pytest.mark.parametrize('data, name, message', [
    (b'GIF89a pas un pdf', 'topo.pdf', "Ce fichier n'est pas un PDF."),
    (b'', 'vide.pdf', 'Aucun fichier reçu.'),
])
def test_upload_validation(client, data, name, message):
    r = upload(client, data=data, name=name)
    assert r.status_code == 400 and r.get_json()['error'] == message
    assert client.get('/api/topos').get_json() == []


def test_upload_without_file_field(client):
    r = upload(client, field='autre')
    assert r.status_code == 400 and r.get_json()['error'] == 'Aucun fichier reçu.'


def test_upload_too_big_is_refused(client):
    r = upload(client, data=b'%PDF-' + b'0' * TOPO_PDF_MAX_BYTES, name='gros.pdf')
    assert r.status_code == 400 and 'dépasse 20 Mo' in r.get_json()['error']


def test_request_larger_than_the_server_limit_gets_a_json_413(app, client):
    app.config['MAX_CONTENT_LENGTH'] = 1024
    r = upload(client, data=b'%PDF-' + b'0' * 5000)
    assert r.status_code == 413 and r.get_json() == {'error': 'Fichier trop volumineux.'}


def test_rename_validation(client):
    t = upload(client).get_json()['topo']['id']
    assert client.put(f'/api/topos/{t}', json={'nom': '  '}).status_code == 400
    assert client.put(f'/api/topos/{t}', json={}).status_code == 400
    assert client.put('/api/topos/999', json={'nom': 'x'}).status_code == 404


def test_unknown_topo_is_404(client):
    assert client.get('/api/topos/999/pdf').status_code == 404
    assert client.delete('/api/topos/999').status_code == 404


# ─── Choix dans la fiche d'une ascension ─────────────────────────────────────

def test_one_topo_for_many_ascensions_and_detach_on_delete(client, dbq):
    topo = upload(client).get_json()['topo']['id']
    ids = [make(client, nom=f'Bloc {i}') for i in range(3)]
    for a in ids:
        assert choose(client, a, topo).status_code == 200
    assert dbq('SELECT COUNT(*) AS n FROM topo')[0]['n'] == 1
    assert client.get('/api/topos').get_json()[0]['nb'] == 3
    infos = client.get(f'/api/ascension/{ids[0]}/infos').get_json()
    assert infos['topo_pdf']['id'] == topo and infos['topos'][0]['id'] == topo

    assert client.delete(f'/api/topos/{topo}').get_json() == {'success': True, 'ascensions': 3}
    assert client.get(f'/api/ascension/{ids[0]}/infos').get_json()['topo_pdf'] is None


def test_choose_requires_a_topo_of_the_account(client, client2):
    foreign = upload(client2).get_json()['topo']['id']
    a = make(client)
    r = choose(client, a, foreign)
    assert r.status_code == 400 and r.get_json()['error'] == 'Topo inconnu.'
    assert choose(client, a, 999).status_code == 400
    assert choose(client, a, 'abc').status_code == 400
    assert choose(client, a, True).status_code == 400
    assert client.get(f'/api/ascension/{a}/infos').get_json()['topo_pdf'] is None


def test_choice_is_cleared_when_the_topo_type_changes(client):
    topo = upload(client).get_json()['topo']['id']
    a = make(client)
    choose(client, a, topo)
    client.put(f'/api/ascension/{a}/infos', json={'topo_type': 'papier', 'topo_nom': 'Guide', 'topo_id': topo})
    assert client.get(f'/api/ascension/{a}/infos').get_json()['topo_pdf'] is None
    assert client.get('/api/topos').get_json()[0]['nb'] == 0            # le topo reste dans la bibliothèque


def test_no_topo_id_means_no_pdf(client):
    topo = upload(client).get_json()['topo']['id']
    a = make(client)
    choose(client, a, topo)
    choose(client, a, None)
    assert client.get(f'/api/ascension/{a}/infos').get_json()['topo_pdf'] is None


def test_upload_for_an_ascension_attaches_to_its_place(client):
    a = make(client, site='Site 1', secteur='S1')
    b = make(client, site='Site 2', secteur='S2')
    topo = upload(client, ascension_id=a).get_json()['topo']['id']
    infos_a = client.get(f'/api/ascension/{a}/infos').get_json()
    infos_b = client.get(f'/api/ascension/{b}/infos').get_json()
    assert [t['local'] for t in infos_a['topos']] == [True]
    assert [t['local'] for t in infos_b['topos']] == [False]
    assert infos_a['topo_pdf'] is None                                    # pas encore choisi : il faut enregistrer la fiche
    assert topo


def test_upload_for_foreign_ascension_is_404(client, client2):
    a = make(client)
    assert upload(client2, ascension_id=a).status_code == 404
    assert client2.get('/api/topos').get_json() == []


# ─── Bouton « Topo » d'un lieu ───────────────────────────────────────────────

def lieu_ids(dbq, site_name):
    site = dbq('SELECT id, localisation_id FROM site WHERE name=?', site_name)[0]
    return site['id'], site['localisation_id']


def test_place_button_content_per_level(client, dbq):
    a1 = make(client, site='Site 1', secteur='S1')
    a2 = make(client, site='Site 2', secteur='S2')
    t1 = upload(client, name='un.pdf', ascension_id=a1).get_json()['topo']['id']
    t2 = upload(client, data=PDF2, name='deux.pdf', ascension_id=a2).get_json()['topo']['id']
    choose(client, a1, t1); choose(client, a2, t2)
    client.put(f'/api/ascension/{make(client, site="Site 1", secteur="S1", nom="P")}/infos',
               json={'topo_type': 'papier', 'topo_nom': 'Guide papier', 'topo_edition': '2e éd.'})
    site1, loc = lieu_ids(dbq, 'Site 1')
    site2, _ = lieu_ids(dbq, 'Site 2')

    r1 = client.get(f'/api/topos/lieu/site/{site1}').get_json()
    assert [t['nom'] for t in r1['pdf']] == ['un'] and r1['pdf'][0]['nb'] == 1
    assert r1['papier'] == [{'nom': 'Guide papier', 'edition': '2e éd.', 'annee': None, 'nb': 1}]
    assert [t['nom'] for t in client.get(f'/api/topos/lieu/site/{site2}').get_json()['pdf']] == ['deux']
    assert [t['nom'] for t in client.get(f'/api/topos/lieu/localisation/{loc}').get_json()['pdf']] == ['deux', 'un']


def test_upload_attached_to_a_place(client, dbq):
    make(client)
    site, loc = lieu_ids(dbq, 'Calanques')
    r = upload(client, niveau='site', lieu_id=site)
    assert r.status_code == 200
    assert [t['nom'] for t in client.get(f'/api/topos/lieu/site/{site}').get_json()['pdf']] == ['topo']
    assert [t['nom'] for t in client.get(f'/api/topos/lieu/localisation/{loc}').get_json()['pdf']] == ['topo']


@pytest.mark.parametrize('niveau', ['pays', 'departement', 'nimporte'])
def test_levels_without_topo_button(client, dbq, niveau):
    make(client)
    pid = dbq('SELECT id FROM pays')[0]['id']
    assert client.get(f'/api/topos/lieu/{niveau}/{pid}').status_code == 400
    assert upload(client, niveau=niveau, lieu_id=pid).status_code == 400


def test_place_errors(client, dbq):
    make(client)
    assert client.get('/api/topos/lieu/site/9999').status_code == 404
    assert upload(client, niveau='site', lieu_id=9999).status_code == 404
    assert upload(client, niveau='site', lieu_id='abc').status_code == 400


def test_other_account_gets_404_everywhere(client, client2, dbq):
    make(client)
    site, _ = lieu_ids(dbq, 'Calanques')
    topo = upload(client, niveau='site', lieu_id=site).get_json()['topo']['id']
    assert client2.get(f'/api/topos/lieu/site/{site}').status_code == 404
    assert upload(client2, data=PDF2, niveau='site', lieu_id=site).status_code == 404
    assert client2.get(f'/api/topos/{topo}/pdf').status_code == 404
    assert client2.put(f'/api/topos/{topo}', json={'nom': 'x'}).status_code == 404
    assert client2.delete(f'/api/topos/{topo}').status_code == 404
    assert client2.get('/api/topos').get_json() == []
    assert client.get(f'/api/topos/{topo}/pdf').data == PDF


def test_anonymous_is_redirected_to_login(anon):
    calls = (lambda: anon.get('/api/topos'), lambda: anon.get('/api/topos/1/pdf'), lambda: anon.put('/api/topos/1', json={}),
             lambda: anon.delete('/api/topos/1'), lambda: anon.get('/api/topos/lieu/site/1'), lambda: upload(anon))
    for call in calls:
        r = call()
        assert r.status_code == 302 and r.headers['Location'].endswith('/login')


def test_deleting_the_ascension_keeps_the_shared_topo(client, dbq):
    topo = upload(client).get_json()['topo']['id']
    a, b = make(client, nom='A'), make(client, nom='B')
    choose(client, a, topo); choose(client, b, topo)
    client.delete(f'/api/ascension/{a}')
    assert dbq('SELECT COUNT(*) AS n FROM topo')[0]['n'] == 1
    assert client.get(f'/api/ascension/{b}/infos').get_json()['topo_pdf']['id'] == topo


def test_the_library_survives_backup_and_restore(client):
    a = make(client)
    topo = upload(client, name='sauvegarde.pdf').get_json()['topo']['id']
    choose(client, a, topo)
    backup = client.get('/backup').data
    client.delete(f'/api/topos/{topo}')
    assert client.get(f'/api/topos/{topo}/pdf').status_code == 404
    r = client.post('/restore', data={'dbfile': (io.BytesIO(backup), 'carnet.db')}, content_type='multipart/form-data')
    assert r.status_code == 200
    assert client.get(f'/api/topos/{topo}/pdf').data == PDF
    assert client.get(f'/api/ascension/{a}/infos').get_json()['topo_pdf']['id'] == topo


def test_carnet_page_has_the_topo_buttons_but_not_for_pays_and_departement(client):
    make(client)
    html = client.get('/carnet').get_data(as_text=True)
    for niveau in ('localisation', 'site', 'secteur'):
        assert f'data-niveau="{niveau}"' in html
    assert 'data-niveau="pays"' not in html and 'data-niveau="departement"' not in html
    assert 'id="topoModalOverlay"' in html and 'id="infoTopoId"' in html
