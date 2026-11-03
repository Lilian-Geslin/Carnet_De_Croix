"""Petits utilitaires de texte et de dates.

Servent à trier et comparer des noms sans se soucier des accents / majuscules / espaces (détection
de doublons, tri alphabétique), et à afficher les dates au format français.
"""
import unicodedata


def strip_accents(value):
    """Retire les accents (« é » → « e »)."""
    decomposed = unicodedata.normalize('NFKD', value)
    return ''.join(ch for ch in decomposed if not unicodedata.combining(ch))


def sort_name_key(name):
    """Clé de tri alphabétique d'un nom : sans casse, sans accents, sans espaces autour."""
    return strip_accents(name or '').lower().strip()


def compare_key(value):
    """Texte normalisé pour comparer deux saisies : sans casse, sans accents, sans aucun espace."""
    if value is None:
        return ''
    return ''.join(strip_accents(str(value)).lower().split())


def to_int_or_none(value):
    """Entier tiré de `value`, ou None si vide / absent / non numérique (jamais d'exception)."""
    try:
        return int(value) if value not in (None, '') else None
    except (TypeError, ValueError):
        return None


def fmt_date(d):
    """Convertit AAAA-MM-JJ en JJ/MM/AAAA pour l'affichage."""
    if not d:
        return ''
    if not isinstance(d, str):
        return d
    parts = d.split('-')
    if len(parts) == 3:
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return d
