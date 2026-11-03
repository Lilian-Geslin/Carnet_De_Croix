"""Connexion, inscription, déconnexion.

Seules routes publiques de l'application (pas de @login_required). Ce sont des pages HTML classiques
(formulaires), pas du JSON : en cas d'erreur la page est ré-affichée avec un message. Le mot de passe
n'est jamais stocké en clair (hachage werkzeug) ; la connexion est mémorisée dans la session Flask
(cookie signé, voir src/auth.py).
"""
import re

from flask import Blueprint, current_app, redirect, render_template, request
from werkzeug.security import check_password_hash, generate_password_hash

from ..auth import DUMMY_PASSWORD_HASH, start_session
from ..constants import (EMAIL_MAX_LEN, LOGIN_EMAIL_MAX, LOGIN_IP_MAX, LOGIN_PAIR_MAX, LOGIN_WINDOW, NAME_MAX_LEN,
                         PASSWORD_MAX, REGISTER_IP_MAX, REGISTER_WINDOW, TOO_MANY_MSG)
from ..db import get_db
from ..security import check_password_policy
from ..services.antibot import form_token_ok
from ..services.ratelimit import client_ip, rl_count, rl_hit, rl_reset

bp = Blueprint('auth', __name__)

# Forme minimale d'une adresse email (la vraie vérification serait d'envoyer un message)
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """GET : affiche le formulaire. POST (champs email, password) : connecte et redirige vers l'accueil,
    ou ré-affiche le formulaire avec UN SEUL message d'erreur, que le compte existe ou non (sinon on pourrait
    deviner quels emails sont inscrits). Trop d'échecs : 429 (compteurs par email+IP, par IP et par email)."""
    error = None
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()[:EMAIL_MAX_LEN]
        password = request.form.get('password') or ''
        ip = client_ip()
        bucket_pair, bucket_email, bucket_ip = f"login:pair:{email}|{ip}", f"login:email:{email}", f"login:ip:{ip}"

        conn = get_db()
        if (rl_count(conn, bucket_pair, LOGIN_WINDOW) >= LOGIN_PAIR_MAX
                or rl_count(conn, bucket_ip, LOGIN_WINDOW) >= LOGIN_IP_MAX
                or rl_count(conn, bucket_email, LOGIN_WINDOW) >= LOGIN_EMAIL_MAX):
            return render_template('auth/login.html', error=TOO_MANY_MSG), 429

        user = conn.execute("SELECT * FROM user WHERE lower(email)=?", (email,)).fetchone()
        # Toujours un calcul de hash (même sans compte) : la durée de réponse ne révèle rien
        stored_hash = user['password'] if user else DUMMY_PASSWORD_HASH
        password_ok = len(password) <= PASSWORD_MAX and check_password_hash(stored_hash, password)

        if user and password_ok:
            rl_reset(conn, bucket_pair)
            conn.commit()
            start_session(user['id'], user['name'])
            return redirect('/')
        for bucket in (bucket_pair, bucket_email, bucket_ip):
            rl_hit(conn, bucket)
        conn.commit()
        error = "Email ou mot de passe incorrect."
    return render_template('auth/login.html', error=error)


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """GET : affiche le formulaire. POST (champs name, email, password) : crée le compte, connecte directement
    l'utilisateur et redirige vers l'accueil ; sinon ré-affiche le formulaire avec une erreur. Fermée (403) si les
    inscriptions sont désactivées (ALLOW_REGISTRATION). Protégée contre les robots (champ piège + jeton daté)."""
    if not current_app.config.get('ALLOW_REGISTRATION', True):
        return render_template('auth/register.html', error="Les inscriptions sont fermées sur cette instance.",
                               closed=True), 403
    error = None
    name = email = ''
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        bucket_ip = f"register:ip:{client_ip()}"
        conn = get_db()
        if rl_count(conn, bucket_ip, REGISTER_WINDOW) >= REGISTER_IP_MAX:
            return render_template('auth/register.html', error=TOO_MANY_MSG, form_name=name, form_email=email), 429
        if request.form.get('company_url') or not form_token_ok(request.form.get('form_ts', '')):
            # Champ piège rempli (robot), ou formulaire envoyé trop vite / trop vieux / falsifié
            error = "Le formulaire a expiré ou a été envoyé trop vite. Rechargez la page puis réessayez."
        elif not name or len(name) > NAME_MAX_LEN:
            error = f"Le prénom est obligatoire ({NAME_MAX_LEN} caractères maximum)."
        elif len(email) > EMAIL_MAX_LEN or not EMAIL_RE.match(email):
            error = "Adresse email invalide."
        else:
            error = check_password_policy(password)
        if not error and conn.execute("SELECT id FROM user WHERE lower(email)=?", (email,)).fetchone():
            error = "Un compte existe déjà avec cet email."
        if not error:
            cur = conn.execute("INSERT INTO user(name,email,password) VALUES(?,?,?)",
                               (name, email, generate_password_hash(password)))
            rl_hit(conn, bucket_ip)
            conn.commit()
            start_session(cur.lastrowid, name)
            return redirect('/')
    return render_template('auth/register.html', error=error, form_name=name, form_email=email), (400 if error else 200)


@bp.route('/logout', methods=['POST'])
def logout():
    """Oublie la session (déconnexion) et renvoie vers l'accueil, qui redirigera vers /login.
    En POST (avec jeton CSRF) : une page piégée ne peut pas déconnecter l'utilisateur par un simple lien."""
    from flask import session
    session.clear()
    return redirect('/')
