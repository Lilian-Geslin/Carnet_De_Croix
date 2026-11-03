"""Routes de l'application, regroupées par thème dans des blueprints.

Un blueprint = un groupe de routes Flask défini dans son propre fichier (variable `bp`).
Les routes ne font que lire la requête, vérifier les entrées et appeler les services (src/services) ;
les erreurs sont levées sous forme d'exceptions (src/errors.py) et transformées en JSON.
"""
from . import api_ascensions, api_geo, api_infos, api_seances, api_topos, auth, exports, pages


def register_blueprints(app):
    """Branche tous les blueprints sur l'application (appelé par `create_app`)."""
    for module in (auth, pages, api_geo, api_ascensions, api_seances, api_infos, api_topos, exports):
        app.register_blueprint(module.bp)
