"""Export CSV : toutes les données d'un compte, dans un ZIP de 4 fichiers liés par ascension_id.

Les fichiers sont : ascensions.csv (logs, projets et envies, avec lieux, topo, choix…),
longueurs.csv (détail des grandes voies), repetitions.csv et seances.csv (séances de projet).
Les trois derniers renvoient à l'ascension par `ascension_id` (et rappellent son nom pour la lisibilité).
"""
import csv
import io
import zipfile

from .ascensions import GEO_COLUMNS, GEO_JOINS

# Colonnes (et leur ordre) de chaque fichier CSV. Une colonne absente de la requête est écrite vide.
ASCENSION_COLUMNS = [
    'id', 'type', 'statut', 'nom', 'cotation', 'cotation_haute', 'cotation_perso', 'style',
    'nb_essais_projet', 'pieds_nus', 'hauteur', 'note_beaute', 'date',
    'commentaire', 'type_depart', 'type_arrivee', 'nb_longueurs', 'grimpe',
    'pays_name', 'departement_name', 'localisation_name', 'site_name', 'secteur_name', 'sous_secteur_name',
    'topo_type', 'topo_nom', 'topo_edition', 'topo_annee', 'topo_page', 'topo_lien', 'topo_pdf', 'annee_ouverture', 'ouvreur',
    'fixations', 'coinceurs', 'roche', 'type_grimpe', 'reequipements', 'envie_categorie',
]
LONGUEUR_COLUMNS = [
    'id', 'ascension_id', 'ascension_nom', 'numero', 'cotation', 'cotation_perso',
    'style', 'pieds_nus', 'hauteur', 'note_beaute', 'grimpe',
]
REPETITION_COLUMNS = [
    'id', 'ascension_id', 'ascension_nom', 'date', 'nb_essais', 'cotation_perso',
    'pieds_nus', 'note_beaute', 'commentaire', 'grimpe',
]
SEANCE_COLUMNS = ['id', 'ascension_id', 'ascension_nom', 'numero', 'date', 'nb_essais', 'commentaire']


def _tag_list(category):
    """Sous-requête : choix d'une catégorie concaténés (« Calcaire | Grès »).

    `category` vient du code (jamais de l'utilisateur), d'où l'insertion directe dans le SQL.
    """
    return (f"(SELECT group_concat(t.nom, ' | ') FROM ascension_tag t "
            f"WHERE t.ascension_id=a.id AND t.categorie='{category}')")


def _rows_to_csv(rows, columns):
    """Convertit une liste de sqlite3.Row en texte CSV (colonnes dans l'ordre donné)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    for r in rows:
        keys = r.keys()
        writer.writerow([r[c] if c in keys else '' for c in columns])
    return buf.getvalue()


def build_export_zip(conn, uid):
    """ZIP en mémoire (BytesIO) contenant ascensions, longueurs, répétitions et séances du compte."""
    # Toutes les ascensions de l'utilisateur (tous statuts), avec lieux, choix (fixations, roche…)
    # et rééquipements concaténés en une seule cellule « a | b »
    ascensions = conn.execute(f"""
        SELECT a.*, {GEO_COLUMNS},
               {_tag_list('fixation')} AS fixations,
               {_tag_list('coinceur')} AS coinceurs,
               {_tag_list('roche')} AS roche,
               {_tag_list('grimpe')} AS type_grimpe,
               (SELECT t.nom FROM topo t WHERE t.id=a.topo_id) AS topo_pdf,
               (SELECT group_concat(TRIM(COALESCE(r.nom,'') || CASE WHEN r.annee IS NOT NULL THEN ' (' || r.annee || ')' ELSE '' END), ' | ')
                  FROM reequipement r WHERE r.ascension_id=a.id) AS reequipements
        FROM ascension a {GEO_JOINS}
        WHERE a.user_id=?
        ORDER BY a.date
    """, (uid,)).fetchall()

    asc_ids = [a['id'] for a in ascensions]
    longueurs, repetitions, seances = [], [], []
    if asc_ids:
        marks = ','.join('?' for _ in asc_ids)

        def child_rows(table, order_by):
            # Lignes filles (longueurs, répétitions ou séances) de ces ascensions, avec le nom de l'ascension
            return conn.execute(f"""
                SELECT c.*, a.nom as ascension_nom
                FROM {table} c JOIN ascension a ON c.ascension_id = a.id
                WHERE c.ascension_id IN ({marks})
                ORDER BY {order_by}
            """, asc_ids).fetchall()

        longueurs = child_rows('longueur', 'c.ascension_id, c.numero')
        repetitions = child_rows('repetition', 'c.ascension_id, c.date')
        seances = child_rows('seance', 'c.ascension_id, c.numero')

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('ascensions.csv', _rows_to_csv(ascensions, ASCENSION_COLUMNS))
        zf.writestr('longueurs.csv', _rows_to_csv(longueurs, LONGUEUR_COLUMNS))
        zf.writestr('repetitions.csv', _rows_to_csv(repetitions, REPETITION_COLUMNS))
        zf.writestr('seances.csv', _rows_to_csv(seances, SEANCE_COLUMNS))
    buf.seek(0)
    return buf
