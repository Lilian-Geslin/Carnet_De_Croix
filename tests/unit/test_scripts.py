"""scripts/ : vérification du .env et des mises à jour (sans réseau)."""
import importlib.util
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, 'scripts', f'{name}.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_check_env(tmp_path, content):
    """Lance check_env.py sur un faux projet (le script lit le .env situé à côté de son dossier scripts/)."""
    (tmp_path / 'scripts').mkdir()
    (tmp_path / 'scripts' / 'check_env.py').write_text(open(os.path.join(ROOT, 'scripts', 'check_env.py'), encoding='utf-8').read(), encoding='utf-8')
    (tmp_path / '.env').write_text(content, encoding='utf-8')
    return subprocess.run([sys.executable, str(tmp_path / 'scripts' / 'check_env.py')], capture_output=True, text=True)


def test_check_env_accepts_a_good_file(tmp_path):
    r = run_check_env(tmp_path, 'CARNET_SECRET_KEY=' + 'a1B2' * 12 + '\n')
    assert r.returncode == 0 and '0 erreur' in r.stdout


def test_check_env_rejects_missing_key_and_never_prints_values(tmp_path):
    r = run_check_env(tmp_path, 'CARNET_SECRET_KEY=court\nFAUTE_DE_FRAPPE=1\nsans egal\n')
    assert r.returncode == 1 and 'CARNET_SECRET_KEY absente' in r.stdout
    assert 'FAUTE_DE_FRAPPE' in r.stdout and 'court' not in r.stdout.replace('trop courte', '')


def test_check_env_without_file(tmp_path):
    (tmp_path / 'scripts').mkdir()
    (tmp_path / 'scripts' / 'check_env.py').write_text(open(os.path.join(ROOT, 'scripts', 'check_env.py'), encoding='utf-8').read(), encoding='utf-8')
    r = subprocess.run([sys.executable, str(tmp_path / 'scripts' / 'check_env.py')], capture_output=True, text=True)
    assert r.returncode == 1 and 'aucun fichier .env' in r.stdout


def test_requirements_are_all_pinned():
    pins = load('check_updates').pinned()
    assert {'flask', 'werkzeug', 'python-dotenv', 'reportlab', 'pillow'} <= set(pins)
    for line in open(os.path.join(ROOT, 'requirements.txt'), encoding='utf-8'):
        if line.strip() and not line.startswith('#'):
            assert '==' in line, f"dépendance non épinglée : {line.strip()}"


def test_check_updates_major_version():
    m = load('check_updates')
    assert m.major('13.0.0') == 13 and m.major('abc') == -1
