"""Exports (CSV, PDF), sauvegarde et restauration de la base.

Routes de téléchargement de fichiers (le contenu est fabriqué par services/export_csv.py, export_pdf.py
et backup.py). Les exports ne contiennent que les données de l'utilisateur connecté ; la sauvegarde
brute, elle, contient toute la base.
"""
from datetime import date, datetime

from flask import Blueprint, current_app, jsonify, request, send_file, session

from ..auth import current_user_id, login_required
from ..db import close_db, get_db
from ..services import backup as backup_service
from ..services import export_csv, export_pdf
from ..security import require_admin

bp = Blueprint('exports', __name__)


@bp.route('/export/csv')
@login_required
def export_csv_zip():
    """ZIP de 4 CSV liés par ascension_id : ascensions, longueurs, répétitions, séances."""
    buf = export_csv.build_export_zip(get_db(), current_user_id())
    filename = f"carnet_de_croix_export_{date.today().isoformat()}.zip"
    return send_file(buf, mimetype='application/zip', as_attachment=True, download_name=filename)


@bp.route('/export/pdf')
@login_required
def export_pdf_file():
    """PDF unique : résumé statistique + liste complète des ascensions loguées."""
    buf = export_pdf.build_pdf(get_db(), current_user_id(), session.get('user_name', ''))
    filename = f"carnet_de_croix_{datetime.now().strftime('%Y%m%d')}.pdf"
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=filename)


@bp.route('/backup')
@login_required
def backup_db():
    """Télécharge une copie brute du fichier carnet.db (tous les comptes inclus). Réservé à l'administrateur (403)."""
    require_admin()
    filename = f"carnet_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db"
    return send_file(current_app.config['DATABASE'], as_attachment=True, download_name=filename,
                     mimetype='application/octet-stream')


@bp.route('/restore', methods=['POST'])
@login_required
def restore_db():
    """Remplace la base par la sauvegarde envoyée (après vérification).

    Envoi en multipart/form-data, fichier dans le champ `dbfile`. Réponses : 200 {success} ;
    erreur 400 (JSON) si le fichier est absent ou n'est pas une base valide (contrôle dans le service).
    Attention : remplace les données de TOUS les comptes, donc réservé à l'administrateur (403 sinon).
    """
    require_admin()
    # Les contrôles de sécurité ont ouvert la connexion de cette requête : on la ferme AVANT de remplacer le
    # fichier, car Windows refuse de remplacer une base encore ouverte (PermissionError).
    close_db()
    backup_service.restore_database(request.files.get('dbfile'), current_app.config['DATABASE'])
    return jsonify({'success': True})
