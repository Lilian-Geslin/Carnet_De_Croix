"""API des topos PDF enregistrés dans le site (bibliothèque) et du bouton « Topo » des lieux.

Routes minces : vérifications et accès à la base sont dans services/topo_pdf.py, dont les erreurs (400 / 404) sont
transformées en JSON par src/errors.py. Toutes les routes exigent d'être connecté et ne voient que les topos du compte.
"""
import io

from flask import Blueprint, jsonify, request, send_file

from ..auth import current_user_id, login_required
from ..constants import TOPO_PDF_MAX_BYTES
from ..db import get_db
from ..errors import ValidationError
from ..services import topo_pdf as topo_pdf_service

bp = Blueprint('api_topos', __name__)


def _int_or_none(value):
    """Entier lu dans un champ de formulaire texte, ou None s'il est vide / absent. Lève ValidationError sinon."""
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError('Identifiant invalide.')


@bp.route('/api/topos', methods=['GET'])
@login_required
def list_topos():
    """Bibliothèque de topos PDF du compte : [{id, nom, fichier, taille, nb}] triée par titre (nb = ascensions qui l'utilisent)."""
    return jsonify(topo_pdf_service.list_topos(get_db(), current_user_id()))


@bp.route('/api/topos', methods=['POST'])
@login_required
def add_topo():
    """Enregistre un PDF dans la bibliothèque. Envoi en multipart/form-data : `fichier` (obligatoire), `titre` (facultatif,
    sinon le nom du fichier) et, pour le rattacher à un lieu, soit `ascension_id` (lieu de cette ascension), soit
    `niveau` + `lieu_id` (localisation / site / secteur / sous_secteur).

    Un fichier déjà enregistré n'est pas dupliqué : la réponse renvoie le topo existant avec `existait` = true.
    Réponses : 200 {success, topo: {id, nom, fichier, taille, nb}, existait} ; 400 si le fichier est absent, vide, trop gros
    (20 Mo) ou n'est pas un PDF, ou si le niveau n'a pas de topo ; 404 si l'ascension ou le lieu n'est pas au compte."""
    db, uid = get_db(), current_user_id()
    fichier = request.files.get('fichier')
    if fichier is None:
        raise ValidationError('Aucun fichier reçu.')
    lieu = None
    asc_id = _int_or_none(request.form.get('ascension_id'))
    if asc_id is not None:
        lieu = topo_pdf_service.lieu_of_ascension(db, uid, asc_id)
    elif request.form.get('niveau'):
        lieu_id = _int_or_none(request.form.get('lieu_id'))
        lieu = (request.form['niveau'], lieu_id if lieu_id is not None else 0)
    # On lit un octet de plus que la limite : suffisant pour détecter un fichier trop gros sans tout charger en mémoire.
    data = fichier.stream.read(TOPO_PDF_MAX_BYTES + 1)
    topo, existait = topo_pdf_service.add_topo(db, uid, fichier.filename, data, titre=request.form.get('titre'), lieu=lieu)
    return jsonify({'success': True, 'topo': topo, 'existait': existait})


@bp.route('/api/topos/<int:topo_id>/pdf', methods=['GET'])
@login_required
def view_topo(topo_id):
    """Affiche le PDF dans le navigateur (lecteur PDF intégré). 404 s'il n'existe pas ou n'est pas au compte.
    `nosniff` : le navigateur ne doit pas deviner un autre type de contenu."""
    nom, contenu = topo_pdf_service.read_pdf(get_db(), current_user_id(), topo_id)
    resp = send_file(io.BytesIO(contenu), mimetype='application/pdf', as_attachment=False, download_name=nom)
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    return resp


@bp.route('/api/topos/<int:topo_id>', methods=['PUT'])
@login_required
def rename_topo(topo_id):
    """Change le titre d'un topo. JSON : {"nom": "…"}. Réponses : 200 {success, nom} ; 400 si vide ou trop long ; 404."""
    data = request.get_json(silent=True) or {}
    nom = topo_pdf_service.rename_topo(get_db(), current_user_id(), topo_id, data.get('nom'))
    return jsonify({'success': True, 'nom': nom})


@bp.route('/api/topos/<int:topo_id>', methods=['DELETE'])
@login_required
def delete_topo(topo_id):
    """Supprime un topo de la bibliothèque. Les ascensions qui le choisissaient n'ont plus de topo PDF.
    Réponses : 200 {success, ascensions} (nombre d'ascensions détachées) ; 404 s'il n'est pas au compte."""
    nb = topo_pdf_service.delete_topo(get_db(), current_user_id(), topo_id)
    return jsonify({'success': True, 'ascensions': nb})


@bp.route('/api/topos/lieu/<niveau>/<int:lieu_id>', methods=['GET'])
@login_required
def topos_du_lieu(niveau, lieu_id):
    """Contenu du bouton « Topo » d'un lieu (niveau : localisation, site, secteur ou sous_secteur) :
    {pdf: [{id, nom, fichier, taille, nb}], papier: [{nom, edition, annee, nb}], en_ligne: [{nom, lien, nb}]}.
    400 pour un niveau sans topo (pays, département) ; 404 si le lieu n'est pas au compte."""
    return jsonify(topo_pdf_service.topos_du_lieu(get_db(), current_user_id(), niveau, lieu_id))
