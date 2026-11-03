"""Sécurité des requêtes : jeton CSRF, redirection HTTPS, relecture du compte, en-têtes HTTP (CSP, HSTS…), journaux.

Tout ce qui protège l'application « autour » des routes est ici, branché une seule fois par `init_app`
(appelée dans `create_app`). Les routes n'ont rien à faire pour en profiter, sauf les formulaires, qui doivent
contenir le champ caché `csrf_token` (voir les gabarits), et le JavaScript, dont `fetch` ajoute l'en-tête tout seul
(static/js/core/csrf.js).
"""
import logging
import re
import secrets

from flask import current_app, g, jsonify, redirect, render_template, request, session

from .constants import PASSWORD_MAX, PASSWORD_MIN
from .errors import ForbiddenError


def check_password_policy(password):
    """Message d'erreur si le mot de passe est refusé (longueur 8 à 128), sinon None."""
    if len(password) < PASSWORD_MIN or len(password) > PASSWORD_MAX:
        return f"Le mot de passe doit contenir entre {PASSWORD_MIN} et {PASSWORD_MAX} caractères."
    return None


# ───────────────────────── Jeton CSRF ─────────────────────────
def get_csrf_token():
    """Jeton CSRF de la session (créé à la première demande). Placé dans les formulaires et dans <meta name="csrf-token">."""
    token = session.get('csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['csrf_token'] = token
    return token


def _csrf_ok():
    """Vrai si la requête porte le jeton de la session (champ `csrf_token` ou en-tête `X-CSRF-Token`)."""
    expected = session.get('csrf_token', '')
    sent = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token') or ''
    if not expected or not sent:
        return False
    return secrets.compare_digest(sent.encode('utf-8'), expected.encode('utf-8'))


# ───────────────────────── Avant chaque requête ─────────────────────────
def security_checks():
    """Contrôles faits avant chaque route : nonce CSP, HTTPS, jeton CSRF, compte toujours valide."""
    # Jeton à usage unique, propre à cette requête : il autorise nos scripts en ligne (voir la CSP plus bas)
    g.csp_nonce = secrets.token_urlsafe(16)

    # Redirection vers HTTPS (derrière l'hébergeur, qui indique le protocole d'origine dans X-Forwarded-Proto).
    # On ne redirige que si l'en-tête dit explicitement « http » : s'il est absent, rien ne se passe (pas de boucle).
    if (current_app.config.get('FORCE_HTTPS')
            and request.headers.get('X-Forwarded-Proto', '').split(',')[0].strip().lower() == 'http'):
        return redirect('https://' + request.host + request.full_path.rstrip('?'), code=301)

    if request.endpoint in (None, 'static'):
        return None

    # 1) Toute requête qui modifie quelque chose doit porter le jeton CSRF
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and not _csrf_ok():
        if request.path.startswith('/api/') or request.path in ('/restore',):
            return jsonify({'error': 'Session expirée : rechargez la page puis réessayez.'}), 400
        return render_template('auth/expired.html'), 400

    # 2) Le compte est relu en base à chaque requête : un compte supprimé est déconnecté tout de suite
    if 'user_id' in session:
        from .db import get_db
        row = get_db().execute("SELECT name FROM user WHERE id=?", (session['user_id'],)).fetchone()
        if not row:
            session.clear()
        elif session.get('user_name') != row['name']:
            session['user_name'] = row['name']
    return None


# ───────────────────────── Après chaque requête ─────────────────────────
def add_security_headers(resp):
    """Ajoute les en-têtes de sécurité à la réponse."""
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')            # le navigateur ne devine pas les types
    resp.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    resp.headers.setdefault('X-Frame-Options', 'DENY')                      # pas d'affichage dans une iframe
    resp.headers.setdefault('Permissions-Policy', 'geolocation=(), microphone=(), camera=(), payment=()')
    if not current_app.config.get('IS_DEV'):
        resp.headers.setdefault('Strict-Transport-Security', 'max-age=15552000')   # HTTPS obligatoire 180 jours
    # Les pages d'un utilisateur ne doivent pas rester dans le cache d'un navigateur partagé
    if request.endpoint != 'static':
        resp.headers.setdefault('Cache-Control', 'no-store')
    nonce = g.get('csp_nonce')
    if nonce and resp.mimetype == 'text/html':
        # Content-Security-Policy : liste blanche de ce que la page a le droit de charger / exécuter. Même si une
        # faille laissait passer du HTML piégé, le navigateur refuserait un script qui n'est pas le nôtre.
        resp.headers['Content-Security-Policy'] = '; '.join([
            "default-src 'self'",
            f"script-src 'self' 'nonce-{nonce}'",
            "style-src 'self' 'unsafe-inline'",
            "font-src 'self'",
            "img-src 'self' data:",
            "connect-src 'self'",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        ])
    return resp


# ───────────────────────── Journaux ─────────────────────────
class RedactSecretsFilter(logging.Filter):
    """Masque clés, jetons et mots de passe qui apparaîtraient dans un message de journal."""
    _pattern = re.compile(r"((?:api_key|apikey|token|secret|password)=)[^&\s\"']+", re.I)

    def filter(self, record):
        try:
            msg = record.getMessage()
        except Exception:
            return True
        redacted = self._pattern.sub(r'\1***', msg)
        if redacted != msg:
            record.msg, record.args = redacted, ()
        return True


# ───────────────────────── Droits d'administration ─────────────────────────
def is_admin(conn, user_id, admin_email=None):
    """Vrai si l'utilisateur peut sauvegarder / restaurer la base (elle contient TOUS les comptes).

    Administrateur = l'email du réglage `ADMIN_EMAIL` (variable CARNET_ADMIN_EMAIL) ; à défaut, le tout premier
    compte créé (celui du propriétaire de l'instance).
    """
    if not user_id:
        return False
    if admin_email:
        return conn.execute("SELECT 1 FROM user WHERE id=? AND lower(email)=lower(?)", (user_id, admin_email)).fetchone() is not None
    first = conn.execute("SELECT MIN(id) AS id FROM user").fetchone()
    return first is not None and first['id'] == user_id


def require_admin():
    """À appeler dans une vue : lève une erreur 403 si l'utilisateur connecté n'est pas administrateur."""
    from .auth import current_user_id
    from .db import get_db
    if not is_admin(get_db(), current_user_id(), current_app.config.get('ADMIN_EMAIL')):
        raise ForbiddenError("Réservé à l'administrateur de l'instance.")


# ───────────────────────── Branchement sur l'application ─────────────────────────
def init_app(app):
    """Branche les protections : contrôles avant requête, en-têtes, variables de gabarit, filtre de journaux."""
    app.before_request(security_checks)
    app.after_request(add_security_headers)

    @app.context_processor
    def inject_security():
        """Disponibles dans tous les gabarits : csrf_token(), csp_nonce, new_form_token(), is_admin."""
        from .db import get_db
        from .services.antibot import make_form_token
        uid = session.get('user_id')
        return {
            'csrf_token': get_csrf_token,
            'csp_nonce': g.get('csp_nonce', ''),
            'new_form_token': make_form_token,
            'is_admin': bool(uid) and is_admin(get_db(), uid, app.config.get('ADMIN_EMAIL')),
        }

    # Les clés, jetons et mots de passe n'apparaissent jamais dans les journaux
    for handler in list(app.logger.handlers) + list(logging.getLogger().handlers):
        handler.addFilter(RedactSecretsFilter())
