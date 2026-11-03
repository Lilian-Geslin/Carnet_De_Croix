"""API des séances d'un projet (mini-journal).

Une séance = un jour d'essais sur un projet : numéro (1, 2, 3…), date, nombre d'essais, commentaire.
Après chaque changement, le total d'essais de l'ascension est recalculé (`sync_essais_projet`).
"""
from flask import Blueprint, jsonify, request

from ..auth import current_user_id, login_required
from ..db import get_db
from ..errors import NotFoundError, ValidationError
from ..services import ascensions as asc_service
from ..services import seances as seances_service

bp = Blueprint('api_seances', __name__)


def _payload_fields(partial=False):
    """Lit et valide le JSON de la requête ; renvoie les champs à enregistrer ou lève ValidationError (400).
    `partial=True` (modification) : seuls les champs envoyés sont renvoyés."""
    fields, err = seances_service.parse_seance_payload(request.get_json(silent=True) or {}, partial=partial)
    if err:
        raise ValidationError(err)
    return fields


@bp.route('/api/ascension/<int:asc_id>/seances', methods=['GET'])
@login_required
def list_seances(asc_id):
    """Séances d'une ascension (projet ou ascension déjà ajoutée au carnet), de la première à la dernière.
    Renvoie aussi nom, type, statut, lieu (« site › secteur › sous-secteur »), nombre de séances et total d'essais. 404 si inconnue."""
    conn = get_db()
    a = conn.execute("""
        SELECT a.nom, a.type, a.statut, s.name AS secteur, si.name AS site, ss.name AS sous_secteur
        FROM ascension a
        LEFT JOIN secteur s ON a.secteur_id = s.id
        LEFT JOIN site si ON s.site_id = si.id
        LEFT JOIN sous_secteur ss ON a.sous_secteur_id = ss.id
        WHERE a.id=? AND a.user_id=?""", (asc_id, current_user_id())).fetchone()
    if not a:
        raise NotFoundError()
    seances = seances_service.list_seances(conn, asc_id)
    return jsonify({
        'nom': a['nom'], 'type': a['type'], 'statut': a['statut'],
        'lieu': ' › '.join(x for x in (a['site'], a['secteur'], a['sous_secteur']) if x),
        'seances': seances,
        'nb_seances': len(seances),
        'total_essais': seances_service.total_essais(seances),
    })


@bp.route('/api/ascension/<int:asc_id>/seances', methods=['POST'])
@login_required
def add_seance(asc_id):
    """Ajoute une séance (numéro = séance précédente + 1) : date, nombre d'essais, mini-journal.
    Réponses : 200 {success, id, numero} ; 400 si données invalides ; 404 si l'ascension n'est pas à l'utilisateur."""
    fields = _payload_fields()
    conn = get_db()
    if not asc_service.ascension_owned(conn, asc_id, current_user_id()):
        raise NotFoundError()
    numero = seances_service.next_seance_numero(conn, asc_id)
    cur = conn.execute("INSERT INTO seance(ascension_id, numero, date, nb_essais, commentaire) VALUES(?,?,?,?,?)",
                       (asc_id, numero, fields['date'], fields['nb_essais'], fields['commentaire']))
    seances_service.sync_essais_projet(conn, asc_id)
    conn.commit()
    return jsonify({'success': True, 'id': cur.lastrowid, 'numero': numero})


@bp.route('/api/seance/<int:seance_id>', methods=['PUT'])
@login_required
def update_seance(seance_id):
    """Modifie la date, le nombre d'essais et/ou le commentaire d'une séance (seuls les champs envoyés changent).
    Réponses : 200 {success} ; 400 si données invalides ; 404 si la séance n'est pas à l'utilisateur."""
    fields = _payload_fields(partial=True)
    conn = get_db()
    seance = seances_service.get_seance_owned(conn, seance_id, current_user_id())
    if not seance:
        raise NotFoundError()
    # Requête construite à partir des seuls champs validés (noms de colonnes sûrs, valeurs passées en paramètres)
    if fields:
        sets = ', '.join(f"{k}=?" for k in fields)
        conn.execute(f"UPDATE seance SET {sets} WHERE id=?", list(fields.values()) + [seance_id])
        seances_service.sync_essais_projet(conn, seance['ascension_id'])
    conn.commit()
    return jsonify({'success': True})


@bp.route('/api/seance/<int:seance_id>', methods=['DELETE'])
@login_required
def delete_seance(seance_id):
    """Supprime une séance et renumérote les suivantes (1, 2, 3…). 404 si elle n'est pas à l'utilisateur."""
    conn = get_db()
    seance = seances_service.get_seance_owned(conn, seance_id, current_user_id())
    if not seance:
        raise NotFoundError()
    seances_service.delete_seance(conn, seance)
    conn.commit()
    return jsonify({'success': True})
