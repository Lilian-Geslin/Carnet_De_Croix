"""API des lieux : listes déroulantes, renommage, suppression.

Les lieux forment une hiérarchie pays > département > localisation > site > secteur > sous-secteur
(voir GEO_TABLES et schema.py). Chaque élément est vérifié comme appartenant à l'utilisateur
(via son pays) avant toute lecture ou modification.
"""
import sqlite3

from flask import Blueprint, jsonify, request

from ..auth import current_user_id, login_required
from ..constants import GEO_TABLES
from ..db import get_db
from ..errors import ConflictError, NotFoundError, ValidationError
from ..services import geo as geo_service

bp = Blueprint('api_geo', __name__)

# URL de liste -> (niveau listé, niveau du parent qui doit appartenir à l'utilisateur)
_LISTS = {
    'departements':  ('departement', 'pays'),
    'localisations': ('localisation', 'departement'),
    'sites':         ('site', 'localisation'),
    'secteurs':      ('secteur', 'site'),
    'sous_secteurs': ('sous_secteur', 'secteur'),
}


@bp.route('/api/geo/pays')
@login_required
def api_pays():
    """Liste des pays de l'utilisateur (triés par nom) : premier niveau des listes déroulantes en cascade."""
    rows = get_db().execute("SELECT * FROM pays WHERE user_id=? ORDER BY name", (current_user_id(),)).fetchall()
    return jsonify([dict(r) for r in rows])


def _register_list_route(url_name, child_table, parent_table):
    """Route `/api/geo/<url_name>/<id du parent>` : éléments du niveau `child_table` rattachés au parent."""
    @login_required
    def children(parent_id):
        # Fonction définie ici (et non avec @bp.route) car on en fabrique une par niveau, voir la boucle plus bas.
        conn = get_db()
        if not geo_service.geo_owned(conn, parent_table, parent_id, current_user_id()):
            return jsonify([])   # parent inconnu ou à un autre utilisateur : liste vide
        return jsonify(geo_service.list_children(conn, child_table, parent_id))

    bp.add_url_rule(f'/api/geo/{url_name}/<int:parent_id>', endpoint=f'list_{url_name}', view_func=children)


# Enregistre les 5 routes de liste (départements, localisations, sites, secteurs, sous-secteurs)
for _url_name, (_child, _parent) in _LISTS.items():
    _register_list_route(_url_name, _child, _parent)


def _check_table(table):
    """Refuse (400) tout nom de table absent de GEO_TABLES : il vient de l'URL et finit dans une requête SQL."""
    if table not in GEO_TABLES:
        raise ValidationError('Table non autorisée')


@bp.route('/api/geo/<string:table>/<int:item_id>', methods=['PUT'])
@login_required
def rename_geo(table, item_id):
    """Renomme un élément. Pour secteur / sous-secteur, met aussi à jour le ressenti indicatif de cotation si fourni.

    URL : /api/geo/<table>/<id>. JSON attendu : name (obligatoire), ressenti (facultatif).
    Réponses : 200 {success} ; 400 si table non autorisée ou nom vide ; 404 si l'élément n'est pas à
    l'utilisateur ; 409 si ce nom existe déjà au même endroit.
    """
    _check_table(table)
    data = request.get_json()
    new_name = data.get('name', '').strip()   # .strip() : un nom fait d'espaces compte comme vide
    if not new_name:
        raise ValidationError('Nom vide')
    conn = get_db()
    if not geo_service.geo_owned(conn, table, item_id, current_user_id()):
        raise NotFoundError()
    try:
        geo_service.rename_item(conn, table, item_id, new_name, data.get('ressenti') or None)
    except sqlite3.IntegrityError:
        raise ConflictError(f"« {new_name} » existe déjà à cet endroit.")
    return jsonify({'success': True})


@bp.route('/api/geo/<string:table>/<int:item_id>', methods=['DELETE'])
@login_required
def delete_geo(table, item_id):
    """Supprime un élément, tous ses niveaux enfants et toutes leurs ascensions (suppression en cascade, définitive).

    Réponses : 200 {success} ; 400 si table non autorisée ; 404 si l'élément n'est pas à l'utilisateur.
    """
    _check_table(table)
    conn, uid = get_db(), current_user_id()
    if not geo_service.geo_owned(conn, table, item_id, uid):
        raise NotFoundError()
    geo_service.delete_item(conn, uid, table, item_id)
    return jsonify({'success': True})
