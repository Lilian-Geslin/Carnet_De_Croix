"""Routes d'export, de sauvegarde et de restauration + gestion d'erreurs de l'application."""
import io
import sqlite3
import zipfile

from tests.conftest import AutoCsrfClient, register
from tests.helpers import asc_payload


def test_csv_export(client):
    client.post('/api/ascension', json=asc_payload(nom='Exporté'))
    r = client.get('/export/csv')
    assert r.status_code == 200 and r.mimetype == 'application/zip'
    assert 'attachment' in r.headers['Content-Disposition'] and '.zip' in r.headers['Content-Disposition']
    z = zipfile.ZipFile(io.BytesIO(r.data))
    assert sorted(z.namelist()) == ['ascensions.csv', 'longueurs.csv', 'repetitions.csv', 'seances.csv']
    assert 'Exporté' in z.read('ascensions.csv').decode()


def test_csv_export_is_per_user(client, client2):
    client.post('/api/ascension', json=asc_payload(nom='Secret'))
    z = zipfile.ZipFile(io.BytesIO(client2.get('/export/csv').data))
    assert 'Secret' not in z.read('ascensions.csv').decode()


def test_pdf_export(client):
    client.post('/api/ascension', json=asc_payload())
    r = client.get('/export/pdf')
    assert r.status_code == 200 and r.mimetype == 'application/pdf' and r.data.startswith(b'%PDF')
    assert '.pdf' in r.headers['Content-Disposition']


def test_pdf_export_when_empty(client):
    assert client.get('/export/pdf').data.startswith(b'%PDF')


def test_backup_download_is_a_sqlite_file(client, tmp_path):
    client.post('/api/ascension', json=asc_payload(nom='Sauvé'))
    r = client.get('/backup')
    assert r.status_code == 200 and r.data.startswith(b'SQLite format 3\x00')
    p = tmp_path / 'copie.db'
    p.write_bytes(r.data)
    c = sqlite3.connect(p)
    assert c.execute('SELECT nom FROM ascension').fetchone()[0] == 'Sauvé'
    c.close()


def test_restore_roundtrip(client, tmp_path):
    client.post('/api/ascension', json=asc_payload(nom='Avant'))
    saved = client.get('/backup').data
    client.post('/api/ascension', json=asc_payload(nom='Après', secteur='Autre'))
    r = client.post('/restore', data={'dbfile': (io.BytesIO(saved), 'carnet.db')}, content_type='multipart/form-data')
    assert r.get_json() == {'success': True}
    html = client.get('/recherche').get_data(as_text=True)
    assert 'Avant' in html and 'Après' not in html


def test_restore_invalid_file(client):
    r = client.post('/restore', data={'dbfile': (io.BytesIO(b'pas une base'), 'x.db')}, content_type='multipart/form-data')
    assert r.status_code == 400 and 'SQLite' in r.get_json()['error']


def test_restore_without_file(client):
    r = client.post('/restore', data={}, content_type='multipart/form-data')
    assert r.status_code == 400 and r.get_json()['error'] == 'Aucun fichier fourni.'


# ─── Application ─────────────────────────────────────────────────────────────

def test_app_factory_uses_given_config(app, db_path):
    assert app.config['DATABASE'] == db_path and app.config['TESTING']


def test_jinja_filters_registered(app):
    assert 'alpine_grade' in app.jinja_env.filters and 'fmt_date' in app.jinja_env.filters


def test_two_apps_are_independent(tmp_path):
    from src import create_app
    a = create_app({'DATABASE': str(tmp_path / 'a.db'), 'TESTING': True})
    b = create_app({'DATABASE': str(tmp_path / 'b.db'), 'TESTING': True})
    a.test_client_class = b.test_client_class = AutoCsrfClient
    ca, cb = a.test_client(), b.test_client()
    register(ca, 'A', 'a@a.fr', 'motdepasse1')
    assert ca.get('/carnet').status_code == 200 and cb.get('/carnet').status_code == 302


def test_api_errors_are_json(client):
    r = client.get('/api/ascension/9999')
    assert r.is_json and r.get_json() == {'error': 'Non trouvé'}


def test_connection_is_closed_after_request(app, client):
    from src import db
    client.get('/carnet')
    with app.app_context():
        assert db.get_db() is not None


def test_secret_key_comes_from_environment(app):
    assert app.config['SECRET_KEY'] == 'cle-de-test-' + 'x' * 30


def test_restore_closes_the_request_connection_first(client, monkeypatch):
    """Windows refuse de remplacer une base encore ouverte : la connexion de la requête doit être fermée avant."""
    from flask import g
    seen = {}
    monkeypatch.setattr('src.routes.exports.backup_service.restore_database',
                        lambda *a, **k: seen.update(open_connection='db' in g))
    assert client.post('/restore', data={}, content_type='multipart/form-data').status_code == 200
    assert seen == {'open_connection': False}
