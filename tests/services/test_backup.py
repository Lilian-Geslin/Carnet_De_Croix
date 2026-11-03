"""src/services/backup.py : restauration d'une sauvegarde."""
import io
import os
import sqlite3

import pytest
from werkzeug.datastructures import FileStorage

from src.errors import ValidationError
from src.schema import init_db
from src.services.backup import restore_database
from tests.services.test_schema import make_legacy_db


def upload(path_or_bytes, name='carnet.db'):
    data = path_or_bytes if isinstance(path_or_bytes, bytes) else open(path_or_bytes, 'rb').read()
    return FileStorage(stream=io.BytesIO(data), filename=name)


@pytest.fixture
def target(tmp_path):
    path = str(tmp_path / 'live.db')
    init_db(path)
    c = sqlite3.connect(path)
    c.execute("INSERT INTO user(name,email,password) VALUES('Ancien','ancien@x.fr','x')")
    c.commit()
    c.close()
    return path


@pytest.fixture
def backup(tmp_path):
    path = str(tmp_path / 'backup.db')
    init_db(path)
    c = sqlite3.connect(path)
    c.execute("INSERT INTO user(name,email,password) VALUES('Sauvegardé','sauve@x.fr','x')")
    c.commit()
    c.close()
    return path


def users(path):
    c = sqlite3.connect(path)
    try:
        return [r[0] for r in c.execute('SELECT name FROM user')]
    finally:
        c.close()


def test_no_file(target):
    with pytest.raises(ValidationError):
        restore_database(None, target)
    with pytest.raises(ValidationError):
        restore_database(FileStorage(stream=io.BytesIO(b''), filename=''), target)


def test_wrong_header_is_refused_and_db_untouched(target):
    with pytest.raises(ValidationError, match='SQLite'):
        restore_database(upload(b'ceci n est pas une base de donnees'), target)
    assert users(target) == ['Ancien'] and not os.path.exists(target + '.upload')


def test_valid_header_but_corrupt_content(target):
    with pytest.raises(ValidationError):
        restore_database(upload(b'SQLite format 3\x00' + b'\x07' * 4000), target)
    assert users(target) == ['Ancien'] and not os.path.exists(target + '.upload')


def test_sqlite_without_required_tables(target, tmp_path):
    other = str(tmp_path / 'other.db')
    c = sqlite3.connect(other)
    c.execute('CREATE TABLE autre(x)')
    c.commit()
    c.close()
    with pytest.raises(ValidationError, match='Carnet de Croix'):
        restore_database(upload(other), target)
    assert users(target) == ['Ancien'] and not os.path.exists(target + '.upload')


def test_only_one_required_table_is_not_enough(target, tmp_path):
    other = str(tmp_path / 'other.db')
    c = sqlite3.connect(other)
    c.execute('CREATE TABLE user(id)')
    c.commit()
    c.close()
    with pytest.raises(ValidationError):
        restore_database(upload(other), target)


def test_successful_restore_keeps_a_safety_copy(target, backup):
    restore_database(upload(backup), target)
    assert users(target) == ['Sauvegardé']
    assert users(target + '.before_restore') == ['Ancien']
    assert not os.path.exists(target + '.upload')


def test_restore_when_no_existing_database(tmp_path, backup):
    path = str(tmp_path / 'nouvelle.db')
    restore_database(upload(backup), path)
    assert users(path) == ['Sauvegardé'] and not os.path.exists(path + '.before_restore')


def test_restoring_an_old_backup_migrates_it(target, tmp_path):
    old = str(tmp_path / 'old.db')
    make_legacy_db(old)
    restore_database(upload(old), target)
    c = sqlite3.connect(target)
    names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert 'localisation' in names and 'falaise' not in names
    assert c.execute('SELECT COUNT(*) FROM ascension').fetchone()[0] == 3
    c.close()


def test_temporary_upload_can_be_removed_after_refusal(target):
    """Régression Windows : la connexion de contrôle doit être fermée avant de supprimer le fichier."""
    import gc
    with pytest.raises(ValidationError):
        restore_database(upload(b'SQLite format 3\x00' + b'\x07' * 4000), target)
    gc.collect()
    assert not os.path.exists(target + '.upload')
