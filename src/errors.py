"""Erreurs métier : les services les lèvent, l'application les transforme en réponse JSON.

Principe : plutôt que de renvoyer des tuples (réponse, code) partout, le code fait
`raise ValidationError("message")` ; le gestionnaire enregistré en bas du fichier attrape
l'exception et fabrique la réponse `{"error": "message"}` avec le bon code HTTP.
"""
from flask import jsonify


class ApiError(Exception):
    """Erreur renvoyée au navigateur sous la forme {"error": message} avec un code HTTP."""
    status = 400   # code HTTP par défaut, redéfini dans les sous-classes

    def __init__(self, message=None, status=None):
        super().__init__(message)
        # `message` est ce que le navigateur affichera à l'utilisateur
        self.message = message or 'Requête invalide.'
        if status is not None:
            self.status = status


class ValidationError(ApiError):
    """Donnée saisie invalide (400)."""


class NotFoundError(ApiError):
    """Élément inexistant, ou qui n'appartient pas à l'utilisateur (404)."""
    status = 404

    def __init__(self, message='Non trouvé'):
        super().__init__(message)


class ForbiddenError(ApiError):
    """Action interdite à cet utilisateur (403)."""
    status = 403

    def __init__(self, message='Action interdite.'):
        super().__init__(message)


class ConflictError(ApiError):
    """L'élément existe déjà (409)."""
    status = 409


def register_error_handlers(app):
    """Branche le traitement des ApiError (et de toutes ses sous-classes) sur l'application."""
    @app.errorhandler(ApiError)
    def handle_api_error(err):
        """Transforme l'exception en JSON {"error": message} avec le code HTTP de l'erreur."""
        return jsonify({'error': err.message}), err.status

    @app.errorhandler(413)
    def handle_too_large(_err):
        """Requête plus grosse que MAX_CONTENT_LENGTH (config.py) : message JSON plutôt que la page d'erreur HTML de Flask."""
        return jsonify({'error': 'Fichier trop volumineux.'}), 413
