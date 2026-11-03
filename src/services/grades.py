"""Cotations : comparaison, tri, « entre deux » (7a/+), conversion alpine, paliers.

Les cotations sont des textes (« 6c+ », « 7a/+ »…). GRADE_ORDER (dans constants.py) donne l'ordre
de la plus facile à la plus dure ; on compare donc des positions, jamais des textes.

Une cotation « entre deux » s'écrit avec un slash : « 7a/+ » signifie « entre 7a et 7a+ ». Pour les
stats, filtres et recherches elle compte comme son niveau avant le slash (7a) ; pour le tri et le
« max », elle se place juste au-dessus de 7a et sous 7a+ (voir grade_rank).
"""
from ..constants import ALPINE_ANCHORS, GRADE_ORDER, GV_TYPES
from .formatting import sort_name_key


def base_grade(g):
    """Cotation « entre deux » (7a/+, 7a+/b) -> niveau avant le slash (7a, 7a+). Sans slash : inchangée."""
    if not isinstance(g, str):
        return g
    return g.split('/')[0].strip()


def grade_index(g):
    """Position dans GRADE_ORDER (-1 si inconnue). Une cotation « entre deux » compte comme son
    niveau avant le slash (stats, filtres, recherche)."""
    try:
        return GRADE_ORDER.index(base_grade(g))
    except ValueError:
        return -1


def grade_rank(g):
    """Comme grade_index, mais 7a/+ se classe juste au-dessus de 7a (et sous 7a+) : sert au tri et au « max »."""
    i = grade_index(g)
    # +0.5 : strictement entre le niveau de base et le suivant (7a < 7a/+ < 7a+)
    if i >= 0 and isinstance(g, str) and '/' in g:
        return i + 0.5
    return i


def max_grade(grades):
    """La plus haute des cotations données (None s'il n'y en a aucune de valide)."""
    # On renvoie la cotation d'origine (avec son éventuel « /+ »), pas sa position
    valid = [(g, grade_rank(g)) for g in grades if grade_index(g) >= 0]
    if not valid:
        return None
    return max(valid, key=lambda x: x[1])[0]


def effective_cotation(a):
    """Cotation à utiliser pour tout calcul de difficulté (stats, tri, max…).

    Pour une grande voie / trad GV, c'est la cotation haute (le passage le plus dur)
    qui représente la difficulté réelle, pas la cotation basse.
    """
    if a['type'] in GV_TYPES and a['cotation_haute']:
        return a['cotation_haute']
    return a['cotation']


def alpine_from_classic(grade):
    """Cotation alpine du palier correspondant à une cotation technique (ex : '5c+' -> 'D+'),
    à partir de la cotation la plus haute (passage obligé) d'une grande voie.

    ALPINE_ANCHORS associe chaque cotation alpine (F, PD, AD, D, TD, ED…) à la cotation technique
    à partir de laquelle on l'atteint ; on garde la dernière ancre dont le seuil est <= `grade`.
    Renvoie None si `grade` est vide ou inconnue.
    """
    if not grade:
        return None
    idx = grade_index(grade)
    if idx < 0:
        return None
    result = 'PD'  # plancher pour tout ce qui est >= 3a mais avant le premier vrai ancrage
    for label, anchor in ALPINE_ANCHORS:
        if anchor == '2':
            continue  # hors échelle GRADE_ORDER : « F » ne peut pas être déduit d'une cotation technique
        if grade_index(anchor) <= idx:
            result = label
        else:
            break
    return result


def sort_ascensions(rows):
    """Ordre d'affichage des ascensions d'un secteur / sous-secteur :
    1) cotation la plus dure d'abord, 2) à cotation égale date la plus récente d'abord,
    3) à date égale ordre alphabétique (sans casse ni accents)."""
    # Trois tris successifs : Python garde l'ordre précédent à égalité, donc on trie du critère
    # le moins important au plus important.
    rows = sorted(rows, key=lambda a: sort_name_key(a['nom']))                                  # 3) nom A→Z
    rows = sorted(rows, key=lambda a: a['date'] or '', reverse=True)                            # 2) date récente d'abord
    rows = sorted(rows, key=lambda a: grade_rank(effective_cotation(a) or ''), reverse=True)    # 1) plus dur d'abord
    return rows


def palier_of(cotation):
    """Palier de cotation d'une envie pour la vue « Paliers » : 5c+ et en dessous regroupés,
    puis un palier par niveau (6a = 6a et 6a+, 6b = 6b et 6b+, …). Sans cotation : à part."""
    i = grade_index(cotation or '')
    # Renvoie {'key', 'label', 'order'} : `order` sert à classer les paliers (le groupe « Sans cotation » en dernier)
    if i < 0:
        return {'key': 'none', 'label': 'Sans cotation', 'order': 999}
    base = GRADE_ORDER[i]
    # base = « 6a+ » : num = 6, letter = « a » (le « + » est volontairement ignoré)
    num, letter = int(base[0]), base[1]
    if num < 6:
        return {'key': 'lt6', 'label': '≤ 5c+', 'order': -1}
    return {'key': f'{num}{letter}', 'label': f'{num}{letter}', 'order': num * 3 + 'abc'.index(letter)}
