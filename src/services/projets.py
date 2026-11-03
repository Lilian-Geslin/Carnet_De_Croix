"""Page Projets : ascensions en cours de travail avec leurs séances.

Un projet est une ascension de statut « projet » : une voie ou un bloc qu'on travaille sans l'avoir
encore réussi. Chaque séance de travail (date + nombre d'essais) est gérée par seances.py.
"""
from .ascensions import GEO_COLUMNS, GEO_JOINS
from .grades import effective_cotation, grade_index
from .seances import seance_dict


def list_projets(conn, uid):
    """Projets de l'utilisateur (par nom), chacun enrichi de ses séances et de ses totaux.

    Champs ajoutés à chaque projet : seances, nb_seances, total_essais, next_numero (numéro de la
    prochaine séance), last_seance, last_date, max_essais (record sur une séance) et cot_idx
    (position de la cotation, pour trier ; -1 si inconnue).
    """
    # Projets avec leurs lieux ; site_id et secteur_id_geo servent à construire les liens côté page
    rows = conn.execute(f"""
        SELECT a.*, {GEO_COLUMNS}, si.id as site_id, sec.id as secteur_id_geo
        FROM ascension a {GEO_JOINS}
        WHERE a.user_id=? AND a.statut='projet'
        ORDER BY a.nom
    """, (uid,)).fetchall()

    # Une seule requête pour toutes les séances (plutôt qu'une par projet), regroupées par ascension
    seances_by_asc = {}
    ids = [r['id'] for r in rows]
    if ids:
        marks = ','.join('?' for _ in ids)
        for sc in conn.execute(f"SELECT * FROM seance WHERE ascension_id IN ({marks}) ORDER BY ascension_id, numero", ids):
            seances_by_asc.setdefault(sc['ascension_id'], []).append(seance_dict(sc))

    projets = []
    for r in rows:
        a = dict(r)
        sc = seances_by_asc.get(a['id'], [])
        a['seances'] = sc
        a['nb_seances'] = len(sc)
        a['total_essais'] = sum(x['nb_essais'] or 0 for x in sc)
        a['next_numero'] = len(sc) + 1
        a['last_seance'] = sc[-1] if sc else None
        dates = [x['date'] for x in sc if x['date']]
        a['last_date'] = max(dates) if dates else ''
        a['max_essais'] = max((x['nb_essais'] or 0 for x in sc), default=0)
        a['cot_idx'] = grade_index(effective_cotation(a) or '')
        projets.append(a)
    return projets
