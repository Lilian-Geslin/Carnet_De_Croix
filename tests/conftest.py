"""Fixtures communes : application sur base temporaire, clients connectés, connexion directe."""
import os
import re
import tempfile

# Les tests ne touchent jamais à la vraie base `carnet.db` ni au fichier `.secret_key` : même la valeur par
# défaut de la configuration est redirigée vers un dossier temporaire (avant l'import de l'application).
os.environ['CARNET_SECRET_KEY'] = 'cle-de-test-' + 'x' * 30
os.environ['CARNET_ENV'] = 'development'        # pas de HTTPS forcé ni de cookie « secure » pendant les tests
os.environ.pop('TRUST_PROXY', None)
os.environ['CARNET_DATABASE'] = os.path.join(tempfile.mkdtemp(prefix='carnet-tests-'), 'jamais-utilisee.db')

import pytest
from flask.testing import FlaskClient

from src import create_app
from src.db import connect
from src.schema import init_db
from tests.helpers import create_user

PASSWORD = 'secret-pass'
TEST_CSRF = 'jeton-csrf-de-test'


@pytest.fixture(autouse=True)
def fast_password_hash(monkeypatch):
    """Hachage de mot de passe très peu coûteux pendant les tests (la vérification reste celle de Werkzeug)."""
    from werkzeug.security import generate_password_hash as real
    fast = lambda password, *a, **k: real(password, method='pbkdf2:sha256:1')
    monkeypatch.setattr('src.routes.auth.generate_password_hash', fast)
    monkeypatch.setattr('tests.helpers.generate_password_hash', fast)


@pytest.fixture(autouse=True)
def no_signup_delay(monkeypatch):
    """Formulaire d'inscription sans délai minimal (un test ne met pas 2 secondes à remplir un formulaire)."""
    monkeypatch.setattr('src.services.antibot.REGISTER_MIN_SECONDS', 0)


class AutoCsrfClient(FlaskClient):
    """Client de test qui joint tout seul le jeton CSRF aux requêtes qui modifient des données.

    Un vrai navigateur le fait via la balise <meta> et csrf.js ; ici on pose un jeton connu dans la session
    et on l'envoie en en-tête. Les tests de la protection elle-même utilisent `plain_client` (sans cette aide).
    """
    def open(self, *args, **kwargs):
        method = (kwargs.get('method') or 'GET').upper()
        if method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            with self.session_transaction() as sess:
                sess.setdefault('csrf_token', TEST_CSRF)
                token = sess['csrf_token']
            kwargs.setdefault('headers', {})
            if not isinstance(kwargs['headers'], dict):
                kwargs['headers'] = dict(kwargs['headers'])
            kwargs['headers'].setdefault('X-CSRF-Token', token)
        return super().open(*args, **kwargs)


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / 'test.db')


@pytest.fixture
def app(db_path):
    application = create_app({'DATABASE': db_path, 'TESTING': True})
    application.test_client_class = AutoCsrfClient
    return application


@pytest.fixture
def plain_client(app):
    """Client SANS l'aide CSRF : pour vérifier que le serveur refuse bien une requête sans jeton."""
    return FlaskClient(app, app.response_class, use_cookies=True)


@pytest.fixture
def conn(db_path):
    """Connexion directe à une base neuve (schéma créé) pour tester les services sans HTTP."""
    init_db(db_path)
    connection = connect(db_path)
    yield connection
    connection.close()


@pytest.fixture
def uid(conn):
    """Premier utilisateur (service)."""
    return create_user(conn, 'Lilian', 'lilian@example.fr')


@pytest.fixture
def uid2(conn):
    """Second utilisateur (service), pour vérifier l'isolation des données."""
    return create_user(conn, 'Autre', 'autre@example.fr')


def _logged_client(app, name, email):
    client = app.test_client()
    register(client, name, email)
    return client


def register(client, name, email, password=None, **extra):
    """Inscription par le vrai formulaire (jeton daté et champ piège compris) ; renvoie la réponse."""
    html = client.get('/register').get_data(as_text=True)
    form_ts = re.search(r'name="form_ts" value="([^"]+)"', html).group(1)
    data = {'name': name, 'email': email, 'password': password or PASSWORD, 'form_ts': form_ts}
    data.update(extra)
    return client.post('/register', data=data)


@pytest.fixture
def client(app):
    """Client HTTP connecté en tant que Lilian (compte créé par /register)."""
    return _logged_client(app, 'Lilian', 'lilian@example.fr')


@pytest.fixture
def client2(app, client):
    """Second client HTTP, connecté avec un autre compte (même application, même base)."""
    return _logged_client(app, 'Autre', 'autre@example.fr')


@pytest.fixture
def anon(app):
    """Client HTTP non connecté."""
    return app.test_client()


@pytest.fixture
def dbq(db_path):
    """Lecture directe de la base pendant un test HTTP : dbq('SELECT ...', params) -> liste de lignes."""
    def query(sql, *params):
        c = connect(db_path)
        try:
            return c.execute(sql, params).fetchall()
        finally:
            c.close()
    return query
