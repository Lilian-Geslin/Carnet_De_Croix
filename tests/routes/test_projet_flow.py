"""Passage en projet : « ⚡ Projet » de la Tick List ouvre le formulaire de séance, et l'ajout d'un projet propose de détailler la séance.

Le JavaScript n'est pas exécuté ici : on vérifie les pages (la bonne fenêtre est présente) et l'enchaînement d'appels d'API
que le navigateur fait (passage en projet, puis séance n°1)."""
from tests.helpers import asc_payload


def make(client, **over):
    return client.post('/api/ascension', json=asc_payload(**over)).get_json()['id']


def test_ticklist_page_uses_the_full_seance_form(client):
    make(client, statut='ticklist', nom='Envie')
    html = client.get('/ticklist').get_data(as_text=True)
    assert 'id="seanceModalOverlay"' in html and 'id="seanceComment"' in html and 'id="btnSeanceSkip"' in html
    assert 'projetModalOverlay' not in html and 'btnSubmitProjet' not in html      # l'ancien petit formulaire a disparu


def test_projets_page_still_has_the_seance_form(client):
    make(client, statut='projet', nom='Projet')
    html = client.get('/projets').get_data(as_text=True)
    assert 'id="seanceModalOverlay"' in html and 'id="seanceModalTitle"' in html


def test_ticklist_wish_becomes_a_project_with_its_first_detailed_session(client):
    """Ce que fait « ⚡ Projet » : passage en projet (sans essais), puis enregistrement de la séance n°1 avec son commentaire."""
    a = make(client, statut='ticklist', nom='Envie')
    assert client.post(f'/api/ascension/{a}/projet', json={'nb_essais_projet': 0}).get_json() == {'success': True}
    r = client.post(f'/api/ascension/{a}/seances', json={'date': '2026-10-20', 'nb_essais': 3, 'commentaire': 'Crux au 3e mouvement'})
    assert r.status_code == 200 and r.get_json()['numero'] == 1
    d = client.get(f'/api/ascension/{a}/seances').get_json()
    assert d['statut'] == 'projet' and d['nb_seances'] == 1 and d['total_essais'] == 3
    assert d['seances'][0]['commentaire'] == 'Crux au 3e mouvement' and d['seances'][0]['date'] == '2026-10-20'


def test_wish_can_become_a_project_without_any_session(client):
    a = make(client, statut='ticklist', nom='Envie')
    client.post(f'/api/ascension/{a}/projet', json={'nb_essais_projet': 0})
    d = client.get(f'/api/ascension/{a}/seances').get_json()
    assert d['statut'] == 'projet' and d['nb_seances'] == 0 and d['total_essais'] == 0


def test_cancelling_the_form_leaves_the_wish_untouched(client):
    """Fermer la fenêtre sans enregistrer n'appelle aucune route : l'envie reste dans la tick list."""
    a = make(client, statut='ticklist', nom='Envie')
    assert client.get(f'/api/ascension/{a}/seances').get_json()['statut'] == 'ticklist'


def test_deep_link_data_for_the_session_form(client):
    """/projets?seance=<id> : le JavaScript lit nom, type et séances de ce projet pour ouvrir la séance n°1 en modification."""
    a = make(client, statut='projet', nom='Mon projet', nb_essais_projet=3)
    d = client.get(f'/api/ascension/{a}/seances').get_json()
    assert (d['nom'], d['type'], d['nb_seances']) == ('Mon projet', 'bloc', 1)
    assert d['seances'][0]['nb_essais'] == 3 and d['seances'][0]['id']


def test_deep_link_of_an_unknown_or_foreign_project_is_404(client, client2):
    a = make(client, statut='projet', nom='Projet')
    assert client2.get(f'/api/ascension/{a}/seances').status_code == 404
    assert client.get('/api/ascension/9999/seances').status_code == 404


def test_new_project_page_loads_with_the_deep_link_parameter(client):
    a = make(client, statut='projet', nom='Projet')
    assert client.get(f'/projets?seance={a}').status_code == 200
