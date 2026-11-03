"""Page Stats : chiffres par discipline (avec le détail en tête / moulinette) et évolution par saison.

Seuls les logs comptent. Pour les voies et le trad (voie), une ascension ne compte que si elle a été
grimpée en tête (voir counts_in_stats). Une cotation « entre deux » (7a/+) est comptée avec son
niveau de base (7a) dans les répartitions, mais classée au-dessus de 7a pour le « max ».
"""
from datetime import date

from ..constants import (ASCENSION_TYPES, GRIMPE_MODES, GV_TYPES, STYLE_GROUPS, TETE_ONLY_TYPES,
                         TYPE_LABELS)
from .geo import get_geo_counts
from .grades import base_grade, effective_cotation, grade_index, max_grade

# Noms des saisons, dans l'ordre utilisé par season_index (0 = printemps … 3 = hiver)
SEASONS = ['Printemps', 'Été', 'Automne', 'Hiver']


# ─── Résumé d'un ensemble d'ascensions ───────────────────────────────────────

def _summarize(ascs, metres):
    """Chiffres et répartitions d'un ensemble d'ascensions.

    Une ascension compte une seule fois, même refaite plusieurs fois : les répétitions
    n'ajoutent que des mètres.
    """
    # Détail renvoyé : répartition par cotation (distrib), par style (style_distrib) et croisée
    # (distrib_by_style) ; les styles sont regroupés en à vue / flash / travaillé (STYLE_GROUPS)
    cotations = [effective_cotation(a) for a in ascs if effective_cotation(a)]
    distrib, distrib_by_style = {}, {}
    style_distrib = {'a_vue': 0, 'flash': 0, 'travaille': 0}
    style_cotations = {'a_vue': [], 'flash': [], 'travaille': []}
    for a in ascs:
        c = base_grade(effective_cotation(a)) or 'Inconnue'      # 7a/+ est compté avec les 7a
        distrib[c] = distrib.get(c, 0) + 1
        grp = STYLE_GROUPS.get(a['style'])
        distrib_by_style.setdefault(c, {'a_vue': 0, 'flash': 0, 'travaille': 0})
        if grp:
            style_distrib[grp] += 1
            distrib_by_style[c][grp] += 1
            if effective_cotation(a):
                style_cotations[grp].append(effective_cotation(a))
    return {
        'nb': len(ascs),
        'metres': round(metres, 1),
        'cot_max': max_grade(cotations),
        'distrib': distrib,
        'style_distrib': style_distrib,
        'distrib_by_style': distrib_by_style,
        'style_max': {k: max_grade(v) for k, v in style_cotations.items()},
    }


def _height_getter(conn):
    """Hauteur d'une ascension : celle saisie ; pour une grande voie sans hauteur, la somme de ses longueurs.

    Renvoie une fonction `asc_height(a)`. Les sommes de longueurs sont calculées une seule fois,
    pour toute la base, plutôt qu'une requête par ascension.
    """
    # Somme des hauteurs des longueurs, par ascension
    long_h = {r['ascension_id']: (r['h'] or 0) for r in conn.execute(
        "SELECT ascension_id, SUM(hauteur) AS h FROM longueur GROUP BY ascension_id")}

    def asc_height(a):
        if a['hauteur'] is not None:
            return a['hauteur']
        return long_h.get(a['id'], 0) if a['type'] in GV_TYPES else 0
    return asc_height


def counts_in_stats(asc_type, grimpe):
    """Une grimpe (ascension ou répétition) compte-t-elle dans les stats ?

    Voies et trad (voie) : seulement si elle est en tête (une moulinette, ou un mode non renseigné, ne
    compte pas). Les autres disciplines, grandes voies comprises, comptent toujours.
    """
    return asc_type not in TETE_ONLY_TYPES or grimpe == 'tete'


def _stats_for_type(asc_type, ascs, repetitions, asc_height):
    """Résumé d'une discipline. `ascs` ne contient déjà que les ascensions qui comptent ; on écarte ici
    les répétitions qui ne comptent pas (voir counts_in_stats)."""
    # Répétitions regroupées par ascension, en ne gardant que celles qui comptent
    ids = {a['id'] for a in ascs}
    reps_by_asc = {}
    for r in repetitions:
        if r['ascension_id'] in ids and counts_in_stats(asc_type, r['grimpe']):
            reps_by_asc.setdefault(r['ascension_id'], []).append(r)

    # Mètres : la hauteur de l'ascension, puis à nouveau pour chaque répétition qui compte
    metres = sum(asc_height(a) * (1 + len(reps_by_asc.get(a['id'], []))) for a in ascs)
    summary = _summarize(ascs, metres)
    summary['label'] = TYPE_LABELS[asc_type]
    return summary


# ─── Évolution par saison ────────────────────────────────────────────────────

def season_index(iso):
    """Numéro de saison (4 par an) d'une date AAAA-MM-JJ.

    Calendrier fixe : l'hiver commence le 21/12 et finit le 19/03, il est rattaché à l'année où il débute.
    """
    y, m, d = int(iso[:4]), int(iso[5:7]), int(iso[8:10])
    md = (m, d)
    if md >= (12, 21):
        return y * 4 + 3
    if md >= (9, 22):
        return y * 4 + 2
    if md >= (6, 21):
        return y * 4 + 1
    if md >= (3, 20):
        return y * 4 + 0
    return (y - 1) * 4 + 3


def season_label(n):
    """Étiquette d'une saison : {'name': « Hiver », 'year': « 2024-25 »}. Seul l'hiver, à cheval sur
    deux années, s'écrit avec les deux ; les autres saisons n'affichent que l'année."""
    y, k = divmod(n, 4)
    return {'name': SEASONS[k], 'year': f"{y}-{(y + 1) % 100:02d}" if k == 3 else str(y)}


def _evolution(ascensions):
    """Cotation max atteinte à chaque saison, par type d'escalade.

    Renvoie {'seasons': [étiquettes de saison], 'series': {type: [valeurs]}} avec une valeur par
    saison : position de la meilleure cotation, -1 si rien cette saison, None avant la première
    saison de ce type (pour que la courbe ne démarre qu'à ce moment-là).
    """
    # Meilleure cotation (en position) de chaque saison, pour chaque type ; les ascensions sans date ni cotation valide sont ignorées
    per_type_season = {}
    for t in ASCENSION_TYPES:
        best = {}
        for a in ascensions:
            c = effective_cotation(a)
            if a['type'] != t or not a['date'] or grade_index(c or '') < 0:
                continue
            n = season_index(a['date'])
            best[n] = max(best.get(n, -1), grade_index(c))
        if best:
            per_type_season[t] = best

    evolution = {'seasons': [], 'series': {}}
    if per_type_season:
        # Axe du temps : de la première saison avec un log jusqu'à la saison en cours (ou la dernière avec un log)
        first = min(min(b) for b in per_type_season.values())
        last = max(season_index(date.today().isoformat()),
                   max(max(b) for b in per_type_season.values()))
        evolution['seasons'] = [season_label(n) for n in range(first, last + 1)]
        for t, best in per_type_season.items():
            start = min(best)
            # None avant la première saison du type ; -1 = « rien cette saison » (bas du graphe)
            evolution['series'][t] = [
                None if n < start else best.get(n, -1) for n in range(first, last + 1)
            ]
    return evolution


# ─── Point d'entrée ──────────────────────────────────────────────────────────

def compute_stats(conn, uid):
    """Toutes les données de la page Stats (compteurs de lieux, évolution, détail par discipline, totaux)."""
    # Tous les logs de l'utilisateur
    logs = conn.execute("SELECT * FROM ascension WHERE user_id=? AND statut='log'", (uid,)).fetchall()
    # Seules les ascensions qui comptent apparaissent dans les chiffres et l'évolution
    ascensions = [a for a in logs if counts_in_stats(a['type'], a['grimpe'])]
    # Répétitions de toutes les ascensions de l'utilisateur (filtrées ensuite par discipline)
    repetitions = conn.execute("""
        SELECT rep.* FROM repetition rep
        JOIN ascension a ON rep.ascension_id=a.id
        WHERE a.user_id=?
    """, (uid,)).fetchall()
    asc_height = _height_getter(conn)

    # Un résumé par discipline, plus la liste de toutes les cotations pour le max global
    per_type = {}
    all_cotations = []
    for t in ASCENSION_TYPES:
        ascs = [a for a in ascensions if a['type'] == t]
        all_cotations.extend(effective_cotation(a) for a in ascs if effective_cotation(a))
        per_type[t] = _stats_for_type(t, ascs, repetitions, asc_height)
        # Voies sans mode renseigné (anciennes ascensions) : écartées des stats, signalées sur la page
        sans_mode = sum(1 for a in logs if a['type'] == t and t in TETE_ONLY_TYPES
                        and a['grimpe'] not in GRIMPE_MODES)
        if sans_mode:
            per_type[t]['sans_mode'] = sans_mode

    total_metres = sum(v['metres'] for v in per_type.values())
    return {
        **get_geo_counts(conn, uid),
        'evolution': _evolution(ascensions),
        'nb_total': len(ascensions),
        'per_type': per_type,
        'total_metres': round(total_metres, 1),
        'cot_max_global': max_grade(all_cotations),
    }
