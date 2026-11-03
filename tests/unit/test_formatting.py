"""src/services/formatting.py : utilitaires de texte et de dates."""
import pytest

from src.services.formatting import compare_key, fmt_date, sort_name_key, strip_accents, to_int_or_none


@pytest.mark.parametrize('raw, expected', [
    ('éàèùçÉ', 'eaeucE'), ('Rémi Lent', 'Remi Lent'), ('sans accent', 'sans accent'), ('', ''),
])
def test_strip_accents(raw, expected):
    assert strip_accents(raw) == expected


@pytest.mark.parametrize('raw, expected', [
    ('  Étoile ', 'etoile'), ('ZEBRE', 'zebre'), (None, ''), ('', ''),
])
def test_sort_name_key(raw, expected):
    assert sort_name_key(raw) == expected


def test_sort_name_key_orders_accents_like_plain_letters():
    names = ['Zèbre', 'Étoile', 'abeille', 'Eau']
    assert sorted(names, key=sort_name_key) == ['abeille', 'Eau', 'Étoile', 'Zèbre']


@pytest.mark.parametrize('raw, expected', [
    ('  Le  Pas ', 'lepas'), ('LE PAS', 'lepas'), ('Le\tPas\n', 'lepas'), ('Rémi', 'remi'),
    (None, ''), (12, '12'),
])
def test_compare_key(raw, expected):
    assert compare_key(raw) == expected


def test_compare_key_equates_variants_of_same_name():
    assert compare_key('Rémi  Lent') == compare_key('remi lent')


@pytest.mark.parametrize('raw, expected', [
    ('12', 12), (7, 7), (3.0, 3), ('', None), (None, None), ('abc', None), ('1.5', None), ([], None),
])
def test_to_int_or_none(raw, expected):
    assert to_int_or_none(raw) == expected


@pytest.mark.parametrize('raw, expected', [
    ('2026-01-05', '05/01/2026'), ('1999-12-31', '31/12/1999'),
    (None, ''), ('', ''), ('pas-une-date-x-y', 'pas-une-date-x-y'), ('texte', 'texte'), (5, 5),
])
def test_fmt_date(raw, expected):
    assert fmt_date(raw) == expected
