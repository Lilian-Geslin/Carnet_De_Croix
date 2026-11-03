"""Sécurité : CSRF, CSP à nonce, en-têtes, HTTPS, connexion, inscription, comptes supprimés, droits d'admin."""
import io
import re

import pytest

from src import create_app
from src.security import RedactSecretsFilter, check_password_policy, is_admin
from tests.conftest import AutoCsrfClient, PASSWORD, TEST_CSRF, register


def token_of(client, path='/login'):
    """Jeton CSRF réel de la session, lu dans la page comme le ferait un navigateur."""
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf-token" content="([^"]+)"', html or '') and re.search(
        r'name="csrf-token" content="([^"]+)"', html).group(1) or re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


# ─── CSRF ───
def test_post_without_token_is_refused(client, plain_client):
    # (plain_client n'est pas connecté : la protection joue avant même la vérification de connexion)
    r = plain_client.post('/api/ascension', json={})
    assert r.status_code == 400 and 'expirée' in r.get_json()['error']


def test_form_post_without_token_shows_expired_page(plain_client):
    r = plain_client.post('/login', data={'email': 'a@x.fr', 'password': 'x'})
    assert r.status_code == 400 and 'Session expirée' in r.get_data(as_text=True)


def test_wrong_token_is_refused(plain_client):
    token_of(plain_client)
    r = plain_client.post('/login', data={'email': 'a@x.fr', 'password': 'x', 'csrf_token': 'faux'})
    assert r.status_code == 400


def test_real_token_in_form_and_header_is_accepted(plain_client):
    token = token_of(plain_client)
    assert plain_client.post('/login', data={'email': 'a@x.fr', 'password': 'x', 'csrf_token': token}).status_code == 200
    assert plain_client.post('/api/ascension', json={}, headers={'X-CSRF-Token': token}).status_code == 302   # pas connecté : /login


def test_restore_without_token_is_json_400(plain_client):
    r = plain_client.post('/restore', data={'dbfile': (io.BytesIO(b'x'), 'x.db')}, content_type='multipart/form-data')
    assert r.status_code == 400 and r.is_json


@pytest.mark.parametrize('method', ['put', 'delete'])
def test_put_and_delete_need_token_too(plain_client, method):
    assert getattr(plain_client, method)('/api/ascension/1').status_code == 400


def test_get_never_needs_token(plain_client):
    assert plain_client.get('/login').status_code == 200


def test_pages_carry_meta_token_and_logout_form(client):
    html = client.get('/carnet').get_data(as_text=True)
    assert 'name="csrf-token"' in html and 'action="/logout"' in html


def test_logout_by_get_is_not_allowed(client):
    assert client.get('/logout').status_code == 405
    assert client.get('/carnet').status_code == 200


# ─── En-têtes et CSP ───
def test_security_headers_and_nonce_csp(client):
    r = client.get('/stats')
    h = r.headers
    nonce = re.search(r"'nonce-([^']+)'", h['Content-Security-Policy']).group(1)
    assert f'nonce="{nonce}"' in r.get_data(as_text=True)                       # le nonce du en-tête est celui des scripts
    csp = h['Content-Security-Policy']
    assert "script-src 'self' 'nonce-" in csp and "'unsafe-inline'" not in csp.split('style-src')[0]
    assert "frame-ancestors 'none'" in csp and "object-src 'none'" in csp and "font-src 'self'" in csp
    assert h['X-Content-Type-Options'] == 'nosniff' and h['X-Frame-Options'] == 'DENY' and h['Cache-Control'] == 'no-store'
    assert h['Referrer-Policy'] == 'strict-origin-when-cross-origin'


def test_nonce_changes_each_request(client):
    a = client.get('/carnet').headers['Content-Security-Policy']
    b = client.get('/carnet').headers['Content-Security-Policy']
    assert a != b


@pytest.mark.parametrize('url', ['/carnet', '/projets', '/ticklist', '/recherche', '/stats'])
def test_every_inline_script_has_the_nonce(client, url):
    html = client.get(url).get_data(as_text=True)
    for tag in re.findall(r'<script(?![^>]*\ssrc=)[^>]*>', html):
        assert 'nonce="' in tag


@pytest.mark.parametrize('url', ['/carnet', '/stats', '/login', '/register'])
def test_no_external_resource(client, anon, url):
    html = (anon if url in ('/login', '/register') else client).get(url).get_data(as_text=True)
    assert not re.search(r'(src|href)="https?://', html.replace('href="https://…"', ''))


def test_static_files_are_cacheable_and_have_no_csp(client):
    r = client.get('/static/js/core/csrf.js')
    assert r.status_code == 200 and r.headers.get('Cache-Control') != 'no-store'
    assert client.get('/static/fonts/bebas-neue-latin-400-normal.woff2').status_code == 200
    assert client.get('/static/js/vendor/chart.umd.js').status_code == 200


def test_json_responses_have_no_csp(client):
    assert 'Content-Security-Policy' not in client.get('/api/options').headers


def test_production_adds_hsts_and_redirects_http(db_path):
    prod = create_app({'DATABASE': db_path, 'TESTING': True, 'IS_DEV': False, 'FORCE_HTTPS': True})
    c = prod.test_client()
    assert 'Strict-Transport-Security' in c.get('/login', headers={'X-Forwarded-Proto': 'https'}).headers
    r = c.get('/login?x=1', headers={'X-Forwarded-Proto': 'http'})
    assert r.status_code == 301 and r.headers['Location'] == 'https://localhost/login?x=1'
    assert c.get('/login').status_code == 200                        # sans en-tête : aucune redirection (pas de boucle)


def test_development_has_no_hsts(anon):
    assert 'Strict-Transport-Security' not in anon.get('/login').headers


def test_session_cookie_flags(anon):
    cookie = register(anon, 'N', 'n@x.fr', 'motdepasse1').headers['Set-Cookie']
    assert 'HttpOnly' in cookie and 'SameSite=Lax' in cookie


def test_production_cookie_is_secure(db_path):
    prod = create_app({'DATABASE': db_path, 'TESTING': True, 'IS_DEV': False, 'FORCE_HTTPS': False,
                       'SESSION_COOKIE_SECURE': True})
    prod.test_client_class = AutoCsrfClient
    c = prod.test_client()
    assert 'Secure' in register(c, 'N', 'n@x.fr', 'motdepasse1').headers['Set-Cookie']


# ─── Connexion ───
def test_login_errors_are_identical_for_unknown_and_wrong_password(client, app):
    a = app.test_client().post('/login', data={'email': 'inconnu@x.fr', 'password': 'x'}).get_data(as_text=True)
    b = app.test_client().post('/login', data={'email': 'lilian@example.fr', 'password': 'faux'}).get_data(as_text=True)
    assert 'Email ou mot de passe incorrect' in a and 'Email ou mot de passe incorrect' in b


def test_login_blocked_after_too_many_failures(client, app):
    other = app.test_client()
    for _ in range(5):
        assert other.post('/login', data={'email': 'lilian@example.fr', 'password': 'faux'}).status_code == 200
    r = other.post('/login', data={'email': 'lilian@example.fr', 'password': PASSWORD})   # même le bon mot de passe est refusé
    assert r.status_code == 429 and 'Trop de tentatives' in r.get_data(as_text=True)
    assert other.get('/carnet').status_code == 302


def test_login_success_resets_pair_counter(client, app, dbq):
    other = app.test_client()
    for _ in range(3):
        other.post('/login', data={'email': 'lilian@example.fr', 'password': 'faux'})
    assert other.post('/login', data={'email': 'lilian@example.fr', 'password': PASSWORD}).status_code == 302
    assert not [r for r in dbq("SELECT bucket FROM auth_attempt") if r['bucket'].startswith('login:pair')]


def test_one_ip_cannot_try_too_many_emails(anon, monkeypatch):
    monkeypatch.setattr('src.routes.auth.LOGIN_IP_MAX', 3)
    for i in range(3):
        anon.post('/login', data={'email': f'u{i}@x.fr', 'password': 'x'})
    assert anon.post('/login', data={'email': 'nouveau@x.fr', 'password': 'x'}).status_code == 429


def test_login_email_is_case_insensitive(client, app):
    assert app.test_client().post('/login', data={'email': 'LILIAN@Example.fr', 'password': PASSWORD}).status_code == 302


def test_login_missing_fields_and_huge_password_do_not_crash(anon):
    assert anon.post('/login', data={}).status_code == 200
    assert anon.post('/login', data={'email': 'a@x.fr', 'password': 'x' * 100000}).status_code == 200


def test_login_starts_a_clean_session(client, app):
    other = app.test_client()
    with other.session_transaction() as s:
        s['donnee_avant_connexion'] = 1
    other.post('/login', data={'email': 'lilian@example.fr', 'password': PASSWORD})
    with other.session_transaction() as s:
        assert 'donnee_avant_connexion' not in s and s['user_id']


def test_proxy_ip_is_read_only_when_trusted(anon, monkeypatch, dbq):
    anon.post('/login', data={'email': 'a@x.fr', 'password': 'x'}, headers={'X-Real-IP': '9.9.9.9'})
    assert not [r for r in dbq("SELECT bucket FROM auth_attempt") if '9.9.9.9' in r['bucket']]
    monkeypatch.setenv('TRUST_PROXY', '1')
    anon.post('/login', data={'email': 'a@x.fr', 'password': 'x'}, headers={'X-Real-IP': '9.9.9.9'})
    anon.post('/login', data={'email': 'a@x.fr', 'password': 'x'}, headers={'X-Forwarded-For': '1.1.1.1, 8.8.8.8'})
    buckets = [r['bucket'] for r in dbq("SELECT bucket FROM auth_attempt")]
    assert any('9.9.9.9' in b for b in buckets) and any('8.8.8.8' in b for b in buckets)


# ─── Mots de passe et inscriptions ───
@pytest.mark.parametrize('pw, ok', [('court', False), ('1234567', False), ('12345678', True), ('x' * 128, True), ('x' * 129, False)])
def test_password_policy(pw, ok):
    assert (check_password_policy(pw) is None) is ok


def test_register_rejects_short_password(anon):
    r = register(anon, 'N', 'n@x.fr', 'court')
    assert r.status_code == 400 and '8 et 128' in r.get_data(as_text=True)
    assert anon.get('/carnet').status_code == 302


def test_register_validation_messages(client, anon):
    assert register(anon, ' ', 'n@x.fr').status_code == 400
    assert 'invalide' in register(anon, 'N', 'pas-un-email').get_data(as_text=True)
    assert 'existe déjà' in register(anon, 'X', 'LILIAN@example.fr').get_data(as_text=True)


def test_register_form_keeps_typed_values(anon):
    html = register(anon, 'Jean', 'pas-un-email').get_data(as_text=True)
    assert 'value="Jean"' in html and 'value="pas-un-email"' in html


def test_register_honeypot_and_missing_form_token(anon):
    assert 'expiré' in register(anon, 'Robot', 'r@x.fr', company_url='http://spam').get_data(as_text=True)
    assert 'expiré' in anon.post('/register', data={'name': 'N', 'email': 'n@x.fr', 'password': PASSWORD}).get_data(as_text=True)
    assert 'expiré' in register(anon, 'N', 'n@x.fr', form_ts='falsifie').get_data(as_text=True)
    assert anon.get('/carnet').status_code == 302


def test_register_form_too_fast_is_refused(anon, monkeypatch):
    monkeypatch.setattr('src.services.antibot.REGISTER_MIN_SECONDS', 3600)
    assert 'expiré' in register(anon, 'N', 'n@x.fr').get_data(as_text=True)


def test_register_rate_limit_per_ip(anon, monkeypatch):
    monkeypatch.setattr('src.routes.auth.REGISTER_IP_MAX', 2)
    for i in range(2):
        assert register(app_client(anon), f'N{i}', f'n{i}@x.fr').status_code == 302
    assert register(app_client(anon), 'N9', 'n9@x.fr').status_code == 429


def app_client(anon):
    """Nouveau client sur la même application (une inscription connecte le client précédent)."""
    return anon.application.test_client()


def test_registration_can_be_closed(db_path):
    closed = create_app({'DATABASE': db_path, 'TESTING': True, 'ALLOW_REGISTRATION': False})
    c = closed.test_client()
    assert c.get('/register').status_code == 403 and 'fermées' in c.get('/register').get_data(as_text=True)


# ─── Compte supprimé : déconnexion immédiate ───
def test_deleted_account_is_logged_out(client, dbq, db_path):
    from src.db import connect
    c = connect(db_path); c.execute("DELETE FROM user"); c.commit(); c.close()
    assert client.get('/carnet').status_code == 302


def test_renamed_account_name_is_refreshed(client, db_path):
    from src.db import connect
    c = connect(db_path); c.execute("UPDATE user SET name='Nouveau Nom'"); c.commit(); c.close()
    assert 'Nouveau Nom' in client.get('/carnet').get_data(as_text=True)


# ─── Journaux ───
def test_log_filter_redacts_secrets():
    import logging
    rec = logging.LogRecord('x', logging.INFO, '', 0, 'GET /x?token=abc123&a=1 password=hunter2', None, None)
    RedactSecretsFilter().filter(rec)
    assert 'abc123' not in rec.getMessage() and 'hunter2' not in rec.getMessage() and 'token=***' in rec.getMessage()


# ─── Sauvegarde / restauration réservées à l'administrateur ───
def test_backup_and_restore_forbidden_for_non_admin(client, client2):
    assert client2.get('/backup').status_code == 403
    r = client2.post('/restore', data={'dbfile': (io.BytesIO(b'x'), 'x.db')}, content_type='multipart/form-data')
    assert r.status_code == 403 and 'administrateur' in r.get_json()['error']


def test_backup_allowed_for_first_account(client):
    assert client.get('/backup').status_code == 200


def test_backup_buttons_hidden_for_non_admin(client, client2):
    assert 'btnRestoreDb' in client.get('/stats').get_data(as_text=True)
    assert 'btnRestoreDb' not in client2.get('/stats').get_data(as_text=True)


def test_admin_email_setting(db_path):
    app = create_app({'DATABASE': db_path, 'TESTING': True, 'ADMIN_EMAIL': 'second@x.fr'})
    app.test_client_class = AutoCsrfClient
    first, second = app.test_client(), app.test_client()
    register(first, 'A', 'a@x.fr', 'motdepasse1'); register(second, 'B', 'SECOND@x.fr', 'motdepasse1')
    assert first.get('/backup').status_code == 403 and second.get('/backup').status_code == 200


def test_is_admin_edge_cases(conn, uid, uid2):
    assert is_admin(conn, None) is False and is_admin(conn, uid) is True and is_admin(conn, uid2) is False
    assert is_admin(conn, uid2, 'autre@example.fr') is True and is_admin(conn, uid, 'autre@example.fr') is False


def test_xss_in_place_name_is_escaped_in_pages(client):
    from tests.helpers import asc_payload
    client.post('/api/ascension', json=asc_payload(nom='<script>alert(1)</script>'))
    html = client.get('/carnet').get_data(as_text=True)
    assert '<script>alert(1)</script>' not in html
