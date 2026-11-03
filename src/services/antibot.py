"""Anti-robots du formulaire d'inscription : jeton daté signé.

Un humain met plus de 2 secondes à remplir le formulaire, et le jeton expire après quelques heures : un robot qui
poste instantanément, ou avec un jeton falsifié / périmé, est refusé.
"""
from datetime import datetime, timezone

from flask import current_app
from itsdangerous import URLSafeTimedSerializer

from ..constants import REGISTER_MAX_SECONDS, REGISTER_MIN_SECONDS


def _signer():
    """Signataire des jetons (créé à la demande : la clé secrète appartient à l'application courante)."""
    return URLSafeTimedSerializer(current_app.secret_key, salt='carnet-register-form')


def make_form_token():
    """Jeton à placer dans le formulaire d'inscription."""
    return _signer().dumps('register')


def form_token_ok(token):
    """Vrai si le jeton est authentique, assez ancien (> REGISTER_MIN_SECONDS) et pas périmé."""
    try:
        value, issued_at = _signer().loads(token, max_age=REGISTER_MAX_SECONDS, return_timestamp=True)
    except Exception:
        return False
    if value != 'register':
        return False
    return (datetime.now(timezone.utc) - issued_at).total_seconds() >= REGISTER_MIN_SECONDS
