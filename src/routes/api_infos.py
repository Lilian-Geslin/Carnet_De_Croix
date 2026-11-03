"""API de la fenêtre « Plus d'informations », des listes de choix et des suggestions de noms.

Routes minces : la validation et l'accès à la base sont dans services/infos.py et services/tags.py
(les topos PDF enregistrés sont dans routes/api_topos.py), qui lèvent des erreurs (400 / 404) transformées en JSON par src/errors.py.
"""
from flask import Blueprint, jsonify, request

from ..auth import current_user_id, login_required
from ..constants import TAG_CATS, TAG_ORDER
from ..db import get_db
from ..services import infos as infos_service
from ..services import tags as tags_service

bp = Blueprint('api_infos', __name__)


@bp.route('/api/ascension/<int:asc_id>/infos', methods=['GET'])
@login_required
def get_infos(asc_id):
    """Séances, topo, ouverture, choix retenus et propositions disponibles d'une ascension (404 si elle n'est pas à l'utilisateur)."""
    return jsonify(infos_service.get_infos(get_db(), current_user_id(), asc_id))


@bp.route('/api/ascension/<int:asc_id>/infos', methods=['PUT'])
@login_required
def update_infos(asc_id):
    """Enregistre topo, ouverture, rééquipements et choix d'une ascension.

    JSON attendu : champs topo_* , annee_ouverture, ouvreur, rééquipements, choix par catégorie (voir
    services/infos.py). Réponses : 200 {success} ; 400 si une valeur est invalide ; 404 si l'ascension n'est pas à l'utilisateur.
    """
    infos_service.update_infos(get_db(), current_user_id(), asc_id, request.get_json(silent=True) or {})
    return jsonify({'success': True})


@bp.route('/api/options', methods=['GET'])
@login_required
def api_options():
    """Toutes les listes de propositions de l'utilisateur, par catégorie, avec le libellé de chaque catégorie (dans l'ordre TAG_ORDER)."""
    options = tags_service.all_options(get_db(), current_user_id())
    return jsonify({'options': options, 'labels': {c: TAG_CATS[c]['label'] for c in TAG_ORDER}})


@bp.route('/api/options', methods=['POST'])
@login_required
def add_option():
    """Ajoute une proposition (ex. « Tricams » dans les coinceurs) ou renvoie l'existante.

    JSON attendu : categorie, nom. Réponse : 200 {success, nom (nettoyé), existait (True si déjà dans la liste)} ;
    400 si catégorie ou nom invalide, ou liste pleine.
    """
    data = request.get_json(silent=True) or {}
    nom, existait = tags_service.add_option(get_db(), current_user_id(), data.get('categorie'), data.get('nom'))
    return jsonify({'success': True, 'nom': nom, 'existait': existait})


@bp.route('/api/options', methods=['DELETE'])
@login_required
def delete_option():
    """Retire une proposition de la liste. Les ascensions qui l'avaient déjà choisie la gardent.
    JSON attendu : categorie, nom."""
    data = request.get_json(silent=True) or {}
    tags_service.delete_option(get_db(), current_user_id(), data.get('categorie'), data.get('nom'))
    return jsonify({'success': True})


@bp.route('/api/noms')
@login_required
def api_noms():
    """Noms déjà saisis, pour les suggestions déroulantes (datalist)."""
    return jsonify(infos_service.known_names(get_db(), current_user_id()))
