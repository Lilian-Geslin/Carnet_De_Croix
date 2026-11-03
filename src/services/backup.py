"""Sauvegarde et restauration du fichier de base SQLite.

Toute la base tient dans un seul fichier : la sauvegarde consiste à télécharger ce fichier, et la
restauration à le remplacer par un fichier envoyé par l'utilisateur (après l'avoir vérifié).
"""
import os
import shutil
import sqlite3

from ..errors import ValidationError
from ..schema import init_db

# Les 16 premiers octets de tout fichier SQLite : permet de reconnaître une base sans l'ouvrir
SQLITE_HEADER = b'SQLite format 3\x00'
# Tables minimales qu'une vraie sauvegarde de Carnet de Croix doit contenir
REQUIRED_TABLES = {'user', 'ascension'}


def restore_database(uploaded_file, database_path):
    """Remplace la base par le fichier envoyé, après vérification que c'est bien une sauvegarde.

    Le fichier doit être une base SQLite contenant au moins les tables « user » et « ascension ».
    Une copie de sécurité de l'ancienne base est conservée (`<base>.before_restore`). Une sauvegarde
    provenant d'une ancienne version est migrée automatiquement (init_db).
    """
    if not uploaded_file or uploaded_file.filename == '':
        raise ValidationError('Aucun fichier fourni.')

    # ─── Contrôle de l'en-tête (rapide, avant d'écrire quoi que ce soit) ───
    header = uploaded_file.read(16)
    uploaded_file.seek(0)
    if header[:16] != SQLITE_HEADER:
        raise ValidationError("Le fichier fourni n'est pas une base SQLite valide.")

    # ─── Contrôle du contenu : on enregistre à côté, on ouvre, on regarde les tables ───
    # (la base en place n'est pas touchée tant que le fichier n'est pas jugé valide)
    tmp_path = database_path + '.upload'
    uploaded_file.save(tmp_path)
    probe = sqlite3.connect(tmp_path)
    try:
        tables = {r[0] for r in probe.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    except sqlite3.Error:
        tables = None
    finally:
        probe.close()    # toujours refermée, sinon Windows refuse de supprimer le fichier ensuite
    if tables is None:
        os.remove(tmp_path)
        raise ValidationError("Le fichier fourni n'est pas une base SQLite valide.")
    if not REQUIRED_TABLES <= tables:
        os.remove(tmp_path)
        raise ValidationError("Ce fichier n'est pas une sauvegarde de Carnet de Croix.")

    # ─── Remplacement : copie de sécurité, puis échange du fichier ───
    if os.path.exists(database_path):
        shutil.copy(database_path, database_path + '.before_restore')
    os.replace(tmp_path, database_path)
    init_db(database_path)   # migre une éventuelle ancienne sauvegarde (falaise → localisation, nouvelles colonnes…)
