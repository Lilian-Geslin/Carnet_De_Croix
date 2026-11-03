"""src/config.py : clé de session obligatoire, mode production par défaut, chemin de base."""
import os

import pytest

from src import config


def test_secret_key_comes_from_environment(monkeypatch):
    monkeypatch.setenv('CARNET_SECRET_KEY', 'x' * 20)
    assert config.load_secret_key() == 'x' * 20


@pytest.mark.parametrize('value', [None, '', 'trop-court'])
def test_missing_or_short_secret_key_refuses_to_start(monkeypatch, value):
    if value is None:
        monkeypatch.delenv('CARNET_SECRET_KEY', raising=False)
    else:
        monkeypatch.setenv('CARNET_SECRET_KEY', value)
    with pytest.raises(RuntimeError, match='CARNET_SECRET_KEY'):
        config.load_secret_key()


def test_no_secret_key_file_is_ever_created(monkeypatch, tmp_path):
    monkeypatch.setenv('CARNET_SECRET_KEY', 'x' * 20)
    monkeypatch.setattr(config, 'BASE_DIR', str(tmp_path))
    config.load_secret_key()
    assert not (tmp_path / '.secret_key').exists()


def test_production_is_the_default_mode(monkeypatch):
    """Sans CARNET_ENV=development : cookie sécurisé et HTTPS forcé (les tests tournent en « development »)."""
    import importlib

    import dotenv
    # Un vrai fichier .env local (avec CARNET_ENV=development) ne doit pas fausser le test : on neutralise sa lecture
    monkeypatch.setattr(dotenv, 'load_dotenv', lambda *a, **k: False)
    saved = os.environ.pop('CARNET_ENV')
    try:
        fresh = importlib.reload(config)
        assert fresh.IS_DEV is False and fresh.FORCE_HTTPS is True and fresh.Config.SESSION_COOKIE_SECURE is True
    finally:
        os.environ['CARNET_ENV'] = saved
        importlib.reload(config)


def test_development_mode_relaxes_https():
    assert config.IS_DEV is True and config.FORCE_HTTPS is False and config.Config.SESSION_COOKIE_SECURE is False


def test_session_cookie_settings():
    assert config.Config.SESSION_COOKIE_HTTPONLY is True and config.Config.SESSION_COOKIE_SAMESITE == 'Lax'


def test_database_path_comes_from_environment():
    assert config.Config.DATABASE == os.environ['CARNET_DATABASE']


def test_tests_never_target_the_real_database():
    """Garde-fou : la base par défaut pendant les tests n'est pas `carnet.db` à la racine du projet."""
    assert os.path.abspath(config.Config.DATABASE) != os.path.join(config.BASE_DIR, 'carnet.db')


def test_request_limit_leaves_room_for_a_pdf_and_a_backup():
    from src.constants import TOPO_PDF_MAX_BYTES
    assert config.Config.MAX_CONTENT_LENGTH > TOPO_PDF_MAX_BYTES
