"""API des ascensions, répétitions et passages de statut."""
import pytest

from tests.helpers import asc_payload


def create(client, **over):
    r = client.post('/api/ascension', json=asc_payload(**over))
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()['id']


# ─── Création ────────────────────────────────────────────────────────────────

def test_create_log(client, dbq):
    r = client.post('/api/ascension', json=asc_payload())
    body = r.get_json()
    assert body['success'] and body['id'] and body['secteur_id']
    row = dbq('SELECT * FROM ascension WHERE id=?', body['id'])[0]
    assert (row['nom'], row['statut'], row['cotation'], row['date']) == ('Bloc A', 'log', '6a', '2026-01-10')


@pytest.mark.parametrize('missing, msg', [('pays', 'Pays'), ('departement', 'Département'), ('site', 'Site')])
def test_create_requires_geo(client, missing, msg):
    r = client.post('/api/ascension', json=asc_payload(**{missing: ''}))
    assert r.status_code == 400 and msg in r.get_json()['error']


@pytest.mark.parametrize('over', [{'type': 'nimporte'}, {'type': None}, {'statut': 'bidon'}])
def test_create_rejects_bad_type_or_statut(client, over):
    assert client.post('/api/ascension', json=asc_payload(**over)).status_code == 400


@pytest.mark.parametrize('typ', ['voie', 'grande_voie', 'trad_voie', 'trad_gv'])
def test_rope_log_requires_grimpe(client, typ):
    r = client.post('/api/ascension', json=asc_payload(type=typ))
    assert r.status_code == 400 and 'tête' in r.get_json()['error']
    assert client.post('/api/ascension', json=asc_payload(type=typ, grimpe='tete')).status_code == 200


def test_rope_project_and_ticklist_do_not_require_grimpe(client):
    assert client.post('/api/ascension', json=asc_payload(type='voie', statut='projet')).status_code == 200
    assert client.post('/api/ascension', json=asc_payload(type='voie', nom='V2', statut='ticklist')).status_code == 200


@pytest.mark.parametrize('typ', ['bloc', 'psychobloc'])
def test_boulder_needs_no_grimpe(client, typ):
    assert client.post('/api/ascension', json=asc_payload(type=typ)).status_code == 200


def test_create_without_json_body_is_400(client):
    assert client.post('/api/ascension', json={}).status_code == 400


def test_duplicate_is_reported_and_nothing_is_written(client, dbq):
    first = create(client)
    r = client.post('/api/ascension', json=asc_payload(date='2026-05-05', style='flash'))
    body = r.get_json()
    assert body['success'] is False and body['duplicate'] is True
    assert body['existing']['id'] == first and body['existing']['statut'] == 'log'
    assert dbq('SELECT COUNT(*) AS n FROM ascension')[0]['n'] == 1


def test_duplicate_of_a_project_reports_attempts(client):
    create(client, statut='projet', nb_essais_projet=6)
    body = client.post('/api/ascension', json=asc_payload()).get_json()
    assert body['duplicate'] and body['existing']['statut'] == 'projet' and body['existing']['nb_essais_projet'] == 6


def test_same_name_in_other_sector_is_not_duplicate(client):
    create(client)
    assert client.post('/api/ascension', json=asc_payload(secteur='Ailleurs')).get_json()['success'] is True


def test_other_user_with_same_data_is_not_duplicate(client, client2):
    create(client)
    assert client2.post('/api/ascension', json=asc_payload()).get_json()['success'] is True


def test_create_project_with_attempts_makes_seance(client, dbq):
    a = create(client, statut='projet', nb_essais_projet=4, date_seance='2026-02-02')
    assert [tuple(r) for r in dbq('SELECT numero, date, nb_essais FROM seance WHERE ascension_id=?', a)] == [(1, '2026-02-02', 4)]


def test_create_applies_ressenti(client, dbq):
    create(client, ressenti='dur')
    assert dbq('SELECT ressenti FROM secteur')[0]['ressenti'] == 'dur'


def test_create_grande_voie_with_longueurs(client, dbq):
    a = create(client, type='grande_voie', cotation='5a', cotation_haute='6a', grimpe='tete',
               longueurs=[{'cotation': '5a'}, {'cotation': '6a'}])
    assert dbq('SELECT COUNT(*) AS n FROM longueur WHERE ascension_id=?', a)[0]['n'] == 2


# ─── Lecture ─────────────────────────────────────────────────────────────────

def test_get_ascension(client):
    a = create(client, sous_secteur='Nord')
    d = client.get(f'/api/ascension/{a}').get_json()
    assert d['ascension']['nom'] == 'Bloc A' and d['ascension']['sous_secteur_name'] == 'Nord' and d['longueurs'] == []


def test_get_other_users_ascension_is_404(client, client2):
    a = create(client)
    assert client2.get(f'/api/ascension/{a}').status_code == 404
    assert client.get('/api/ascension/9999').get_json() == {'error': 'Non trouvé'}


# ─── Modification ────────────────────────────────────────────────────────────

def test_update(client, dbq):
    a = create(client)
    r = client.put(f'/api/ascension/{a}', json=asc_payload(nom='Renommé', cotation='7a', secteur='Nouveau'))
    assert r.get_json() == {'success': True}
    row = dbq('SELECT * FROM ascension WHERE id=?', a)[0]
    assert (row['nom'], row['cotation']) == ('Renommé', '7a')
    assert dbq('SELECT name FROM secteur WHERE id=?', row['secteur_id'])[0]['name'] == 'Nouveau'


def test_update_validation_and_ownership(client, client2):
    a = create(client)
    assert client.put(f'/api/ascension/{a}', json=asc_payload(pays='')).status_code == 400
    assert client2.put(f'/api/ascension/{a}', json=asc_payload(nom='Piraté')).status_code == 404
    assert client.get(f'/api/ascension/{a}').get_json()['ascension']['nom'] == 'Bloc A'


def test_update_rope_log_requires_grimpe_but_project_does_not(client):
    log = create(client, type='voie', grimpe='tete')
    assert client.put(f'/api/ascension/{log}', json=asc_payload(type='voie', grimpe=None)).status_code == 400
    proj = create(client, nom='P', type='voie', statut='projet')
    assert client.put(f'/api/ascension/{proj}', json=asc_payload(nom='P', type='voie')).status_code == 200


# ─── Suppression ─────────────────────────────────────────────────────────────

def test_delete(client, client2, dbq):
    a = create(client)
    assert client2.delete(f'/api/ascension/{a}').status_code == 404
    assert client.delete(f'/api/ascension/{a}').get_json() == {'success': True}
    assert dbq('SELECT COUNT(*) AS n FROM ascension')[0]['n'] == 0
    assert client.delete(f'/api/ascension/{a}').status_code == 404


# ─── Projet / tick list → log ────────────────────────────────────────────────

def test_log_from_projet(client, dbq):
    a = create(client, statut='projet')
    r = client.post(f'/api/ascension/{a}/log', json={'date': '2026-03-03', 'style': 'essais_2', 'note_beaute': 3,
                                                      'cotation_perso': '6b', 'pieds_nus': True})
    assert r.get_json() == {'success': True}
    row = dbq('SELECT * FROM ascension WHERE id=?', a)[0]
    assert (row['statut'], row['date'], row['style'], row['note_beaute'], row['cotation_perso'], row['pieds_nus']) == (
        'log', '2026-03-03', 'essais_2', 3, '6b', 1)


def test_log_from_ticklist(client, dbq):
    a = create(client, statut='ticklist')
    client.post(f'/api/ascension/{a}/log', json={'date': '2026-03-03'})
    assert dbq('SELECT statut FROM ascension WHERE id=?', a)[0]['statut'] == 'log'


def test_log_rope_requires_grimpe(client, dbq):
    a = create(client, type='voie', statut='projet')
    assert client.post(f'/api/ascension/{a}/log', json={'date': '2026-03-03'}).status_code == 400
    assert dbq('SELECT statut FROM ascension WHERE id=?', a)[0]['statut'] == 'projet'
    assert client.post(f'/api/ascension/{a}/log', json={'date': '2026-03-03', 'grimpe': 'moulinette'}).status_code == 200


def test_log_other_users_ascension_is_404(client, client2):
    a = create(client, statut='projet')
    assert client2.post(f'/api/ascension/{a}/log', json={}).status_code == 404


# ─── Tick list → projet ──────────────────────────────────────────────────────

def test_ticklist_to_projet_with_attempts(client, dbq):
    a = create(client, statut='ticklist')
    r = client.post(f'/api/ascension/{a}/projet', json={'nb_essais_projet': 5, 'date_seance': '2026-04-04'})
    assert r.get_json() == {'success': True}
    assert dbq('SELECT statut, nb_essais_projet FROM ascension WHERE id=?', a)[0]['statut'] == 'projet'
    assert dbq('SELECT nb_essais_projet FROM ascension WHERE id=?', a)[0]['nb_essais_projet'] == 5
    assert [tuple(s) for s in dbq('SELECT numero, date, nb_essais FROM seance')] == [(1, '2026-04-04', 5)]


def test_ticklist_to_projet_without_attempts_makes_no_seance(client, dbq):
    a = create(client, statut='ticklist')
    client.post(f'/api/ascension/{a}/projet', json={})
    assert dbq('SELECT COUNT(*) AS n FROM seance')[0]['n'] == 0


def test_ticklist_to_projet_clamps_attempts(client, dbq):
    a = create(client, statut='ticklist')
    client.post(f'/api/ascension/{a}/projet', json={'nb_essais_projet': 5000})
    assert dbq('SELECT nb_essais FROM seance')[0]['nb_essais'] == 999


def test_ticklist_to_projet_errors(client, client2):
    a = create(client, statut='ticklist')
    assert client.post(f'/api/ascension/{a}/projet', json={'nb_essais_projet': 'abc'}).status_code == 400
    assert client2.post(f'/api/ascension/{a}/projet', json={}).status_code == 404
    log = create(client, nom='Log')
    assert client.post(f'/api/ascension/{log}/projet', json={}).status_code == 404     # seulement depuis la tick list
    assert client.post(f'/api/ascension/{a}/projet', json={}).status_code == 200
    assert client.post(f'/api/ascension/{a}/projet', json={}).status_code == 404       # plus dans la tick list


# ─── Catégorie d'envie ───────────────────────────────────────────────────────

def test_set_categorie(client, dbq):
    a = create(client, statut='ticklist')
    assert client.post(f'/api/ascension/{a}/categorie', json={'categorie': 'beaute'}).status_code == 200
    assert dbq('SELECT envie_categorie FROM ascension WHERE id=?', a)[0]['envie_categorie'] == 'beaute'
    client.post(f'/api/ascension/{a}/categorie', json={'categorie': ''})
    assert dbq('SELECT envie_categorie FROM ascension WHERE id=?', a)[0]['envie_categorie'] is None


def test_set_categorie_errors(client, client2):
    a = create(client, statut='ticklist')
    assert client.post(f'/api/ascension/{a}/categorie', json={'categorie': 'bidon'}).status_code == 400
    assert client2.post(f'/api/ascension/{a}/categorie', json={'categorie': 'beaute'}).status_code == 404
    log = create(client, nom='Log')
    assert client.post(f'/api/ascension/{log}/categorie', json={'categorie': 'beaute'}).status_code == 404


# ─── Répétitions ─────────────────────────────────────────────────────────────

def test_add_and_delete_repetition(client, dbq):
    a = create(client)
    r = client.post('/api/repetition', json={'ascension_id': a, 'date': '2026-05-05', 'nb_essais': '2',
                                              'cotation_perso': '6b', 'pieds_nus': True, 'note_beaute': 2, 'commentaire': 'bien'})
    assert r.get_json() == {'success': True}
    rep = dbq('SELECT * FROM repetition')[0]
    assert (rep['date'], rep['nb_essais'], rep['pieds_nus'], rep['commentaire']) == ('2026-05-05', '2', 1, 'bien')
    assert client.delete(f"/api/repetition/{rep['id']}").get_json() == {'success': True}
    assert dbq('SELECT COUNT(*) AS n FROM repetition')[0]['n'] == 0


@pytest.mark.parametrize('body', [{}, {'date': '2026-05-05'}, {'ascension_id': 1}, {'ascension_id': 999, 'date': '2026-05-05'}])
def test_repetition_needs_owned_ascension_and_date(client, body):
    create(client)
    assert client.post('/api/repetition', json=body).status_code == 400


def test_repetition_on_foreign_ascension(client, client2):
    a = create(client)
    assert client2.post('/api/repetition', json={'ascension_id': a, 'date': '2026-05-05'}).status_code == 400


def test_repetition_rope_requires_grimpe_and_keeps_valid_mode(client, dbq):
    a = create(client, type='voie', grimpe='tete')
    assert client.post('/api/repetition', json={'ascension_id': a, 'date': '2026-05-05'}).status_code == 400
    client.post('/api/repetition', json={'ascension_id': a, 'date': '2026-05-05', 'grimpe': 'moulinette'})
    assert dbq('SELECT grimpe FROM repetition')[0]['grimpe'] == 'moulinette'


def test_repetition_boulder_discards_grimpe(client, dbq):
    a = create(client)
    client.post('/api/repetition', json={'ascension_id': a, 'date': '2026-05-05', 'grimpe': 'bidon'})
    assert dbq('SELECT grimpe FROM repetition')[0]['grimpe'] is None


def test_delete_repetition_of_other_user_does_nothing(client, client2, dbq):
    a = create(client)
    client.post('/api/repetition', json={'ascension_id': a, 'date': '2026-05-05'})
    rid = dbq('SELECT id FROM repetition')[0]['id']
    client2.delete(f'/api/repetition/{rid}')
    assert dbq('SELECT COUNT(*) AS n FROM repetition')[0]['n'] == 1
