"""Authentification : décorateur de protection des pages.

L'utilisateur connecté est mémorisé dans la session Flask (cookie signé avec la clé secrète de
config.py) sous la clé `user_id`. La connexion / inscription elles-mêmes sont dans routes/auth.py ;
ici on ne trouve que ce qui sert à protéger les autres routes.
"""
from functools import wraps

from flask import redirect, session
from werkzeug.security import generate_password_hash


# Hash factice : on calcule toujours un hash à la connexion, même quand l'email n'existe pas, pour que le temps
# de réponse ne révèle pas si le compte existe.
DUMMY_PASSWORD_HASH = generate_password_hash('mot-de-passe-factice-carnet')


def start_session(user_id, name):
    """Ouvre une session propre : on vide d'abord l'ancienne (un identifiant posé avant la connexion ne doit
    jamais servir après : fixation de session)."""
    session.clear()
    session.permanent = True
    session['user_id'] = user_id
    session['user_name'] = name


def login_required(view):
    """Redirige vers la page de connexion si personne n'est connecté.

    À placer SOUS @bp.route(...) : `@bp.route(...)` puis `@login_required` puis la fonction.
    Pour une API, l'utilisateur non connecté reçoit donc une redirection (302) vers /login, pas du JSON.
    """
    # wraps conserve le nom de la vue d'origine (Flask en a besoin pour distinguer les routes).
    @wraps(view)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        return view(*args, **kwargs)
    return wrapped


def current_user_id():
    """Identifiant de l'utilisateur connecté (à n'appeler que dans une vue protégée par login_required)."""
    return session['user_id']
