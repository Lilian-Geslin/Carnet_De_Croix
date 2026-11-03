"""Routes : connexion, inscription, déconnexion, pages HTML et protection par login."""
import pytest

from tests.conftest import register

PAGES = ['/carnet', '/projets', '/ticklist', '/recherche', '/stats']
PROTECTED = PAGES + ['/', '/export/csv', '/export/pdf', '/backup', '/api/options', '/api/noms', '/api/geo/pays']


@pytest.mark.parametrize('url', PROTECTED)
def test_anonymous_is_redirected_to_login(anon, url):
    r = anon.get(url)
    assert r.status_code == 302 and r.headers['Location'].endswith('/login')


@pytest.mark.parametrize('method, url', [('post', '/api/ascension'), ('put', '/api/ascension/1'), ('delete', '/api/ascension/1'),
                                          ('post', '/api/repetition'), ('delete', '/api/seance/1'), ('post', '/restore')])
def test_anonymous_cannot_write(anon, method, url):
    r = getattr(anon, method)(url, json={})
    assert r.status_code == 302


def test_login_and_register_pages_render(anon):
    assert anon.get('/login').status_code == 200 and anon.get('/register').status_code == 200


def test_register_creates_account_and_logs_in(anon, dbq):
    r = register(anon, 'Nouveau', 'n@x.fr', 'motdepasse1')
    assert r.status_code == 302
    assert anon.get('/carnet').status_code == 200
    rows = dbq('SELECT name, password FROM user WHERE email=?', 'n@x.fr')
    assert rows[0]['name'] == 'Nouveau' and rows[0]['password'] != 'motdepasse1'     # mot de passe haché


def test_register_duplicate_email(client, anon):
    r = register(anon, 'X', 'lilian@example.fr', 'motdepasse1')
    assert r.status_code == 400 and 'existe déjà' in r.get_data(as_text=True)
    assert anon.get('/carnet').status_code == 302


def test_login_success(client, app):
    other = app.test_client()
    r = other.post('/login', data={'email': 'lilian@example.fr', 'password': 'secret-pass'})
    assert r.status_code == 302 and other.get('/carnet').status_code == 200


def test_login_wrong_password(client, app):
    other = app.test_client()
    r = other.post('/login', data={'email': 'lilian@example.fr', 'password': 'faux'})
    assert 'Email ou mot de passe incorrect' in r.get_data(as_text=True) and other.get('/carnet').status_code == 302


def test_login_unknown_email(anon):
    r = anon.post('/login', data={'email': 'inconnu@x.fr', 'password': 'x'})
    assert 'Email ou mot de passe incorrect' in r.get_data(as_text=True)    # même message que pour un mauvais mot de passe


def test_logout(client):
    assert client.post('/logout').status_code == 302
    assert client.get('/carnet').status_code == 302


def test_home_redirects_to_carnet(client):
    r = client.get('/')
    assert r.status_code == 302 and r.headers['Location'].endswith('/carnet')


@pytest.mark.parametrize('url', PAGES)
def test_pages_render_when_empty(client, url):
    assert client.get(url).status_code == 200


def test_pages_render_with_data(client):
    from tests.helpers import asc_payload
    client.post('/api/ascension', json=asc_payload(nom='Bloc visible', sous_secteur='Nord'))
    client.post('/api/ascension', json=asc_payload(nom='Mon projet', statut='projet', nb_essais_projet=3))
    client.post('/api/ascension', json=asc_payload(nom='Mon envie', statut='ticklist'))
    assert 'Bloc visible' in client.get('/carnet').get_data(as_text=True)
    assert 'Mon projet' in client.get('/projets').get_data(as_text=True)
    assert 'Mon envie' in client.get('/ticklist').get_data(as_text=True)
    assert 'Bloc visible' in client.get('/recherche').get_data(as_text=True)
    assert client.get('/stats').status_code == 200


def test_carnet_hides_projects(client):
    from tests.helpers import asc_payload
    client.post('/api/ascension', json=asc_payload(nom='Mon projet', statut='projet'))
    assert 'Mon projet' not in client.get('/carnet').get_data(as_text=True)


@pytest.mark.parametrize('qs', ['?open_secteur=1', '?open_secteur=999', '?open_secteur=abc'])
def test_carnet_open_secteur_never_crashes(client, qs):
    from tests.helpers import asc_payload
    client.post('/api/ascension', json=asc_payload())
    assert client.get('/carnet' + qs).status_code == 200


@pytest.mark.parametrize('qs', [
    '?q=bloc', '?statut=tout', '?statut=projet', '?type=bloc&type=voie', '?style=flash&beaute=2', '?cot_min=6a&cot_max=7a',
    '?cot_min=7a&cot_max=6a', '?groupe=plat', '?tri=nom', '?tri=bidon', '?mois=2026-02', '?mois=zzz', '?date=2026-01-10',
    '?pieds_nus=1', '?hauteur_min=2&hauteur_max=10', '?ouvreur=x&topo=y&annee_min=1990&annee_max=2020', '?roche=Grès&tgrimpe=Dalle',
    '?mode=tete',
])
def test_recherche_query_strings(client, qs):
    from tests.helpers import asc_payload
    client.post('/api/ascension', json=asc_payload())
    assert client.get('/recherche' + qs).status_code == 200


def test_recherche_filters_results(client):
    from tests.helpers import asc_payload
    client.post('/api/ascension', json=asc_payload(nom='Trouvable'))
    client.post('/api/ascension', json=asc_payload(nom='Autre chose', cotation='7a'))
    html = client.get('/recherche?q=trouv').get_data(as_text=True)
    assert 'Trouvable' in html and 'Autre chose' not in html


def test_unknown_url_is_404(client):
    assert client.get('/nimporte').status_code == 404


def test_stats_page_shows_lead_only_sentence_without_mode_buttons(client):
    from tests.helpers import asc_payload
    client.post('/api/ascension', json=asc_payload(nom='Voie', type='voie', grimpe='tete'))
    client.post('/api/ascension', json=asc_payload(nom='GV', type='grande_voie', cotation='5a', cotation_haute='6a',
                                                   grimpe='moulinette'))
    html = client.get('/stats').get_data(as_text=True)
    assert html.count('Seules les ascensions grimpées en tête sont comptabilisées') == 1     # voie seulement
    assert 'Moulinette</button>' not in html and 'Les deux' not in html
