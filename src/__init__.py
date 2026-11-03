"""Carnet de Croix : carnet d'escalade personnel (Flask + SQLite).

Ce fichier contient la « fabrique d'application » `create_app` : c'est elle qui assemble toutes les
pièces du projet (configuration, base de données, gestion des erreurs, routes, filtres de templates).
Elle est appelée par `run.py` en développement, par un serveur WSGI en production et par les tests
(qui lui passent une configuration à eux, par exemple une base temporaire).
"""
from flask import Flask

from . import db, security
from .config import Config
from .errors import register_error_handlers
from .routes import register_blueprints
from .schema import init_db
from .services.formatting import fmt_date
from .services.grades import alpine_from_classic


def create_app(config=None):
    """Crée et configure l'application (utilisable aussi par un serveur WSGI ou les tests).

    `config` : dictionnaire facultatif qui écrase les réglages par défaut (ex. {'DATABASE': ..., 'TESTING': True}).
    """
    # ─── Configuration ───
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['SECRET_KEY'] = Config.secret_key()
    # Appliqué en dernier pour que les tests puissent tout surcharger (base, clé secrète…).
    if config:
        app.config.update(config)

    # ─── Branchements (base, erreurs, routes) ───
    db.init_app(app)
    register_error_handlers(app)
    security.init_app(app)      # contrôle d'origine, en-têtes de sécurité, droits d'admin
    register_blueprints(app)

    # Filtres utilisables dans les templates : {{ cotation|alpine_grade }} et {{ date|fmt_date }}
    app.jinja_env.filters['alpine_grade'] = alpine_from_classic
    app.jinja_env.filters['fmt_date'] = fmt_date

    # Crée / met à jour les tables au démarrage (voir schema.py : idempotent, donc sans danger à chaque lancement).
    init_db(app.config['DATABASE'])
    return app
