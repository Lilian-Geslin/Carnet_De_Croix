"""API des ascensions : création, lecture, modification, suppression, passage de statut, répétitions.

Toutes les routes exigent d'être connecté et ne touchent que les ascensions de l'utilisateur courant
(une ascension d'un autre compte est traitée comme inexistante : 404). Les corps de requête sont du JSON ;
les erreurs sortent en {"error": message} (voir src/errors.py). Les écritures sont validées par `conn.commit()`.
"""
from flask import Blueprint, jsonify, request

from ..auth import current_user_id, login_required
from ..constants import (ASCENSION_TYPES, GRIMPE_MODES, GRIMPE_REQUIRED_MSG, ROPE_TYPES, STATUTS)
from ..db import get_db
from ..errors import NotFoundError, ValidationError
from ..services import ascensions as asc_service
from ..services import geo as geo_service
from ..services import seances as seances_service
from ..services import ticklist as ticklist_service

bp = Blueprint('api_ascensions', __name__)


def _check_grimpe(asc_type, grimpe):
    """En tête / moulinette est obligatoire pour une ascension (ou répétition) réalisée sur corde."""
    if asc_type in ROPE_TYPES and grimpe not in GRIMPE_MODES:
        raise ValidationError(GRIMPE_REQUIRED_MSG)


def _owned_ascension_type(conn, asc_id, uid):
    """Type de l'ascension `asc_id` si elle appartient à `uid`, sinon lève NotFoundError (404)."""
    row = conn.execute("SELECT type FROM ascension WHERE id=? AND user_id=?", (asc_id, uid)).fetchone()
    if not row:
        raise NotFoundError()
    return row['type']


@bp.route('/api/ascension', methods=['POST'])
@login_required
def add_ascension():
    """Crée une ascension (statut log, projet ou ticklist).

    JSON attendu : type, statut (défaut 'log'), nom, cotation, date, lieu (pays > … > secteur), grimpe, etc.
    Réponses : 200 {success, id, secteur_id} ; 200 {success: False, duplicate: True, existing: {...}} si la
    même voie existe déjà (le navigateur propose alors de la répéter) ; 400 si type, statut, lieu ou mode
    de grimpe est invalide.
    """
    data = request.get_json() or {}
    uid = current_user_id()
    err = geo_service.validate_geo_payload(data)
    if err:
        raise ValidationError(err)
    if data.get('type') not in ASCENSION_TYPES:
        raise ValidationError("Type d'ascension invalide.")
    statut = data.get('statut', 'log')
    if statut not in STATUTS:
        raise ValidationError('Statut invalide.')
    if statut == 'log':
        _check_grimpe(data.get('type'), data.get('grimpe'))
    # Nettoyage des noms de lieux (espaces, casse…) avant de chercher ou créer les niveaux
    data = geo_service.normalize_geo_payload(data)

    conn = get_db()
    # Retrouve ou crée la chaîne pays > … > secteur (> sous-secteur) et renvoie les identifiants utiles
    secteur_id, sous_secteur_id = geo_service.resolve_location(conn, uid, data)

    # Détection de doublon (avant toute écriture définitive : la transaction n'est pas validée)
    dup = asc_service.find_duplicate(conn, uid, secteur_id, sous_secteur_id, data)
    if dup:
        existing = {'id': dup['id'], 'statut': dup['statut'], 'nom': dup['nom'], 'type': dup['type'],
                    'nb_essais_projet': dup['nb_essais_projet'] or 0}
        return jsonify({'success': False, 'duplicate': True, 'existing': existing})

    geo_service.apply_ressenti(conn, data, secteur_id, sous_secteur_id)
    asc_id = asc_service.insert_ascension(conn, uid, secteur_id, sous_secteur_id, data)
    conn.commit()
    return jsonify({'success': True, 'id': asc_id, 'secteur_id': secteur_id})


@bp.route('/api/ascension/<int:asc_id>', methods=['GET'])
@login_required
def get_ascension(asc_id):
    """Données complètes d'une ascension, pour pré-remplir le formulaire de modification."""
    detail = asc_service.get_ascension_detail(get_db(), asc_id, current_user_id())
    if detail is None:
        raise NotFoundError()
    return jsonify(detail)


@bp.route('/api/ascension/<int:asc_id>', methods=['PUT'])
@login_required
def update_ascension(asc_id):
    """Met à jour toutes les infos d'une ascension existante.

    JSON attendu : mêmes champs que la création (le type et le statut ne changent pas ici).
    Réponses : 200 {success} ; 404 si l'ascension n'est pas à l'utilisateur ; 400 si lieu ou mode de grimpe invalide.
    """
    data = request.get_json() or {}
    uid = current_user_id()
    err = geo_service.validate_geo_payload(data)
    if err:
        raise ValidationError(err)
    data = geo_service.normalize_geo_payload(data)

    conn = get_db()
    if not asc_service.ascension_owned(conn, asc_id, uid):
        raise NotFoundError()
    current = conn.execute("SELECT type, statut FROM ascension WHERE id=?", (asc_id,)).fetchone()
    # Le mode de grimpe n'est exigé que pour une ascension loguée (pas pour un projet ou une envie)
    if current['statut'] == 'log':
        _check_grimpe(current['type'], data.get('grimpe'))

    secteur_id, sous_secteur_id = geo_service.resolve_location(conn, uid, data)
    geo_service.apply_ressenti(conn, data, secteur_id, sous_secteur_id)
    asc_service.update_ascension(conn, uid, asc_id, secteur_id, sous_secteur_id, data)
    conn.commit()
    return jsonify({'success': True})


@bp.route('/api/ascension/<int:asc_id>', methods=['DELETE'])
@login_required
def delete_ascension(asc_id):
    """Supprime une ascension et ce qui en dépend (longueurs, répétitions, séances…). 404 si elle n'est pas à l'utilisateur."""
    conn = get_db()
    if not asc_service.ascension_owned(conn, asc_id, current_user_id()):
        raise NotFoundError()
    asc_service.delete_ascensions(conn, [asc_id])
    conn.commit()
    return jsonify({'success': True})


@bp.route('/api/ascension/<int:asc_id>/log', methods=['POST'])
@login_required
def log_from_projet(asc_id):
    """Transforme un projet ou une envie de tick list en ascension loguée.

    JSON attendu : style, date, note_beaute, cotation_perso, pieds_nus, grimpe (obligatoire si voie sur corde).
    Réponses : 200 {success} ; 400 si le mode de grimpe manque ; 404 si l'ascension n'est pas à l'utilisateur.
    """
    data = request.get_json() or {}
    uid = current_user_id()
    conn = get_db()
    _check_grimpe(_owned_ascension_type(conn, asc_id, uid), data.get('grimpe'))
    conn.execute("""
        UPDATE ascension SET statut='log', style=?, date=?, note_beaute=?,
        cotation_perso=?, pieds_nus=?, grimpe=?
        WHERE id=? AND user_id=?
    """, (data.get('style'), data.get('date'), data.get('note_beaute'),
          data.get('cotation_perso'), 1 if data.get('pieds_nus') else 0,
          data.get('grimpe'), asc_id, uid))
    conn.commit()
    return jsonify({'success': True})


@bp.route('/api/ascension/<int:asc_id>/projet', methods=['POST'])
@login_required
def ticklist_to_projet(asc_id):
    """Passe une ascension de la tick list en projet (essayée sans la finir), avec le nombre
    d'essais déjà faits (champ JSON nb_essais_projet, 0 par défaut) qui forme la séance n°1.

    JSON facultatif : nb_essais_projet, date_seance. Réponses : 200 {success} ; 400 si le nombre d'essais
    n'est pas un entier ; 404 si l'ascension n'est pas dans la tick list de l'utilisateur.
    """
    data = request.get_json(silent=True) or {}
    try:
        nb = max(0, int(data.get('nb_essais_projet') or 0))
    except (TypeError, ValueError):
        raise ValidationError("Nombre d'essais invalide.")
    nb = min(nb, 999)   # plafond de sécurité contre une valeur absurde
    conn = get_db()
    cur = conn.execute("UPDATE ascension SET statut='projet' WHERE id=? AND user_id=? AND statut='ticklist'",
                       (asc_id, current_user_id()))
    # Aucune ligne modifiée = pas à l'utilisateur, ou pas (ou plus) en statut ticklist
    if cur.rowcount == 0:
        raise NotFoundError('Ascension introuvable dans la tick list.')
    # Les essais déjà faits deviennent la séance n°1 (le compteur du projet est ensuite recalculé depuis les séances)
    if nb > 0:
        conn.execute("INSERT INTO seance(ascension_id, numero, date, nb_essais, commentaire) VALUES(?,?,?,?,?)",
                     (asc_id, seances_service.next_seance_numero(conn, asc_id),
                      seances_service.clean_iso_date(data.get('date_seance')), nb, None))
    seances_service.sync_essais_projet(conn, asc_id)
    conn.commit()
    return jsonify({'success': True})


@bp.route('/api/ascension/<int:asc_id>/categorie', methods=['POST'])
@login_required
def set_envie_categorie(asc_id):
    """Change la catégorie (Performance / Beauté / Classique, ou aucune) d'une envie de la tick list.

    JSON : {"categorie": "performance" | "beaute" | "majeure" | null}. La validation est faite par le service.
    """
    data = request.get_json(silent=True) or {}
    ticklist_service.set_categorie(get_db(), current_user_id(), asc_id, data.get('categorie') or None)
    return jsonify({'success': True})


@bp.route('/api/repetition', methods=['POST'])
@login_required
def add_repetition():
    """Ajoute une répétition (voie déjà loguée refaite).

    JSON attendu : ascension_id et date (obligatoires), nb_essais, cotation_perso, pieds_nus, note_beaute,
    commentaire, grimpe (obligatoire pour une voie sur corde).
    Réponses : 200 {success} ; 400 si ascension inconnue, date manquante ou mode de grimpe absent.
    """
    data = request.get_json() or {}
    uid = current_user_id()
    conn = get_db()
    if not data.get('ascension_id') or not data.get('date') or not asc_service.ascension_owned(conn, data['ascension_id'], uid):
        raise ValidationError('Ascension introuvable ou date manquante.')
    asc_type = conn.execute("SELECT type FROM ascension WHERE id=?", (data['ascension_id'],)).fetchone()['type']
    _check_grimpe(asc_type, data.get('grimpe'))
    conn.execute("""
        INSERT INTO repetition(ascension_id, date, nb_essais, cotation_perso, pieds_nus, note_beaute, commentaire, grimpe)
        VALUES(?,?,?,?,?,?,?,?)
    """, (
        data['ascension_id'], data['date'], data.get('nb_essais'),
        data.get('cotation_perso'), 1 if data.get('pieds_nus') else 0,
        data.get('note_beaute'), data.get('commentaire'),
        data.get('grimpe') if data.get('grimpe') in GRIMPE_MODES else None   # valeur inconnue -> NULL (cas des blocs)
    ))
    conn.commit()
    return jsonify({'success': True})


@bp.route('/api/repetition/<int:rep_id>', methods=['DELETE'])
@login_required
def delete_repetition(rep_id):
    """Supprime une répétition. La sous-requête garantit qu'elle appartient à une ascension de l'utilisateur
    (sinon rien n'est supprimé, et la réponse reste un succès)."""
    conn = get_db()
    conn.execute("""DELETE FROM repetition WHERE id=? AND ascension_id IN
                    (SELECT id FROM ascension WHERE user_id=?)""", (rep_id, current_user_id()))
    conn.commit()
    return jsonify({'success': True})
