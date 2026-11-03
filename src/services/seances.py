"""Séances d'un projet (mini-journal) : numérotation, validation, totaux d'essais.

Une séance = un jour où l'on a travaillé un projet (date, nombre d'essais, commentaire). Les séances
sont numérotées 1, 2, 3… par projet, et le total d'essais du projet (`nb_essais_projet`) est toujours
recalculé à partir d'elles.
"""
from datetime import datetime

from .formatting import fmt_date


def sync_essais_projet(conn, asc_id):
    """nb_essais_projet = somme des essais de toutes les séances de l'ascension."""
    conn.execute("""UPDATE ascension SET nb_essais_projet =
                    (SELECT COALESCE(SUM(nb_essais), 0) FROM seance WHERE ascension_id=?) WHERE id=?""",
                 (asc_id, asc_id))


def next_seance_numero(conn, asc_id):
    """Numéro à donner à la prochaine séance du projet (1 s'il n'y en a pas encore)."""
    row = conn.execute("SELECT COALESCE(MAX(numero), 0) FROM seance WHERE ascension_id=?", (asc_id,)).fetchone()
    return row[0] + 1


def seance_dict(row):
    """Séance (ligne SQL) en dictionnaire, avec la date au format JJ/MM/AAAA dans `date_fmt`."""
    d = dict(row)
    d['date_fmt'] = fmt_date(d.get('date'))
    return d


def clean_iso_date(v):
    """Date AAAA-MM-JJ valide saisie par l'utilisateur, sinon None (on ne met jamais « aujourd'hui » d'office)."""
    if not isinstance(v, str):
        return None
    v = v.strip()
    try:
        datetime.strptime(v, '%Y-%m-%d')
    except ValueError:
        return None
    return v


def parse_seance_payload(data, partial=False):
    """Valide les champs d'une séance. partial=True (modification) : seuls les champs fournis sont lus.

    Retourne (champs, erreur) : en cas de problème `champs` vaut None et `erreur` est le message
    à afficher ; sinon `erreur` vaut None. Règles : date AAAA-MM-JJ obligatoire à la création (vide
    possible en modification), essais entre 1 et 999, commentaire de 5000 caractères maximum.
    """
    fields = {}
    # ─── Date ─── (une valeur qui n'est pas du texte est traitée comme vide)
    if not partial or 'date' in data:
        d = (data.get('date') or '').strip() if isinstance(data.get('date'), str) or data.get('date') is None else ''
        if d:
            try:
                datetime.strptime(d, '%Y-%m-%d')
            except ValueError:
                return None, 'Date invalide.'
            fields['date'] = d
        elif not partial:
            return None, 'La date de la séance est requise.'
        else:
            fields['date'] = None
    # ─── Nombre d'essais ───
    if not partial or 'nb_essais' in data:
        try:
            n = int(data.get('nb_essais'))
        except (TypeError, ValueError):
            return None, "Nombre d'essais invalide."
        if n < 1 or n > 999:
            return None, "Le nombre d'essais doit être compris entre 1 et 999."
        fields['nb_essais'] = n
    # ─── Commentaire (facultatif : vide = None) ───
    if not partial or 'commentaire' in data:
        c = data.get('commentaire')
        c = c.strip() if isinstance(c, str) else ''
        if len(c) > 5000:
            return None, 'Le commentaire est trop long (5000 caractères maximum).'
        fields['commentaire'] = c or None
    return fields, None


def get_seance_owned(conn, seance_id, uid):
    """La séance si elle appartient à une ascension de l'utilisateur, sinon None."""
    return conn.execute("""SELECT s.* FROM seance s JOIN ascension a ON s.ascension_id=a.id
                           WHERE s.id=? AND a.user_id=?""", (seance_id, uid)).fetchone()


def list_seances(conn, asc_id):
    """Séances d'une ascension, de la première à la dernière."""
    rows = conn.execute("SELECT * FROM seance WHERE ascension_id=? ORDER BY numero", (asc_id,)).fetchall()
    return [seance_dict(r) for r in rows]


def total_essais(seances):
    """Total des essais d'une liste de séances (un nombre d'essais vide compte pour 0)."""
    return sum(s['nb_essais'] or 0 for s in seances)


def delete_seance(conn, seance):
    """Supprime une séance et renumérote les suivantes (1, 2, 3…)."""
    asc_id = seance['ascension_id']
    # Après une suppression au milieu, on recolle les numéros pour ne pas laisser de « trou »
    conn.execute("DELETE FROM seance WHERE id=?", (seance['id'],))
    rows = conn.execute("SELECT id FROM seance WHERE ascension_id=? ORDER BY numero, id", (asc_id,)).fetchall()
    for i, r in enumerate(rows, 1):
        conn.execute("UPDATE seance SET numero=? WHERE id=?", (i, r['id']))
    sync_essais_projet(conn, asc_id)
