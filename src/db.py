"""Accès à la base SQLite : une connexion par requête, fermée automatiquement à la fin.

Les routes et services appellent `get_db()` pour obtenir la connexion de la requête en cours.
Elle est stockée dans `g` (objet Flask propre à chaque requête) et fermée par `close_db`.
Le COMMIT n'est pas automatique : chaque route qui écrit doit appeler `conn.commit()`.
"""
import sqlite3

from flask import current_app, g


def connect(path):
    """Ouvre une connexion SQLite dont les lignes s'utilisent comme des dictionnaires."""
    # row_factory = Row : on lit les colonnes par leur nom (row['nom']) et dict(row) fonctionne.
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def get_db():
    """Connexion de la requête en cours (créée à la première demande)."""
    # `g` est vidé à la fin de chaque requête : une seule connexion par requête, même si on appelle get_db() plusieurs fois.
    if 'db' not in g:
        g.db = connect(current_app.config['DATABASE'])
    return g.db


def close_db(_exc=None):
    """Ferme la connexion de la requête ; une transaction non validée est annulée."""
    conn = g.pop('db', None)
    if conn is not None:
        conn.close()


def init_app(app):
    """Demande à Flask d'appeler `close_db` à la fin de chaque requête (même en cas d'erreur)."""
    app.teardown_appcontext(close_db)
