"""Configuration de l'application (chemins, mode de fonctionnement, clé de session, cookies, comptes).

Lu une seule fois au démarrage par `create_app` (src/__init__.py). Les variables d'environnement viennent du
fichier `.env` placé à la racine du projet (jamais publié : voir .gitignore et .env.example). Les tests
surchargent ces valeurs en passant leur propre dictionnaire à `create_app`.
"""
import os
from datetime import timedelta

from dotenv import load_dotenv

# Racine du projet (le dossier qui contient run.py et src/) : on remonte de deux niveaux depuis ce fichier.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(BASE_DIR, '.env'))     # charge les variables du fichier .env s'il existe

# Mode de fonctionnement. Par défaut : « production » (le plus sûr : cookie sécurisé, HTTPS forcé, pas de debug).
# Pour travailler sur ton PC en http, mettre CARNET_ENV=development dans ton .env local (jamais sur un serveur).
IS_DEV = os.environ.get('CARNET_ENV', 'production').strip().lower() == 'development'

# Redirection automatique http -> https en production (désactivable avec FORCE_HTTPS=0)
FORCE_HTTPS = (not IS_DEV) and os.environ.get('FORCE_HTTPS', '1') != '0'

SECRET_KEY_MIN_LENGTH = 16


def _env_flag(name, default=False):
    """Variable d'environnement booléenne : « 1 », « true », « yes », « oui », « on » valent vrai."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'oui', 'on')


def load_secret_key():
    """Clé qui signe le cookie de session (variable CARNET_SECRET_KEY du .env).

    Elle est OBLIGATOIRE : sans elle, une clé aléatoire serait générée à chaque démarrage (tout le monde
    déconnecté) et elle pourrait différer d'un processus à l'autre. Mieux vaut refuser de démarrer.
    """
    key = os.environ.get('CARNET_SECRET_KEY', '')
    if len(key) < SECRET_KEY_MIN_LENGTH:
        raise RuntimeError(
            "CARNET_SECRET_KEY absente ou trop courte (16 caractères minimum) : ajoute-la dans le fichier .env "
            "(voir .env.example ; génération : python -c \"import secrets; print(secrets.token_urlsafe(48))\")."
        )
    return key


class Config:
    """Réglages lus au démarrage (chargés par `app.config.from_object(Config)` dans create_app)."""
    # Chemin du fichier SQLite ; CARNET_DATABASE permet de le déplacer (hébergement, tests).
    DATABASE = os.environ.get('CARNET_DATABASE', os.path.join(BASE_DIR, 'carnet.db'))
    # Taille maximale d'une requête (PDF de topo, restauration d'une sauvegarde qui peut contenir des PDF), en Mo
    MAX_CONTENT_LENGTH = int(os.environ.get('CARNET_MAX_UPLOAD_MB', '256')) * 1024 * 1024

    # Mode et HTTPS (recopiés ici pour que les tests puissent les surcharger)
    IS_DEV = IS_DEV
    FORCE_HTTPS = FORCE_HTTPS

    # ─── Cookie de session ───
    SESSION_COOKIE_HTTPONLY = True      # illisible depuis JavaScript
    SESSION_COOKIE_SAMESITE = 'Lax'     # non envoyé lors d'une requête provenant d'un autre site
    SESSION_COOKIE_SECURE = not IS_DEV  # uniquement en HTTPS en production
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)   # durée de la connexion

    # ─── Comptes ───
    # ALLOW_REGISTRATION=0 ferme les inscriptions (instance personnelle : créer son compte d'abord)
    ALLOW_REGISTRATION = _env_flag('ALLOW_REGISTRATION', True)
    # Email de l'administrateur (sauvegarde / restauration) ; à défaut, le premier compte créé
    ADMIN_EMAIL = os.environ.get('CARNET_ADMIN_EMAIL') or None

    @staticmethod
    def secret_key():
        """Clé secrète de session (voir load_secret_key) : lue au moment de créer l'application, pas à l'import."""
        return load_secret_key()
