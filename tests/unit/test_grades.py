"""src/services/grades.py : cotations, « entre deux », conversion alpine, tri, paliers."""
import pytest

from src.constants import ALPINE_ANCHORS, GRADE_ORDER
from src.services.grades import (alpine_from_classic, base_grade, effective_cotation, grade_index, grade_rank,
                                 max_grade, palier_of, sort_ascensions)


def asc(nom='x', cotation='6a', date='2026-01-01', type='bloc', cotation_haute=None):
    return {'nom': nom, 'cotation': cotation, 'date': date, 'type': type, 'cotation_haute': cotation_haute}


# ─── base_grade / grade_index / grade_rank ──────────────────────────────────

@pytest.mark.parametrize('raw, expected', [
    ('7a/+', '7a'), ('7a+/b', '7a+'), ('7c+/8a', '7c+'), ('7a', '7a'), (' 7a /+', '7a'), ('', ''),
])
def test_base_grade(raw, expected):
    assert base_grade(raw) == expected


def test_base_grade_keeps_non_strings():
    assert base_grade(None) is None
    assert base_grade(5) == 5


def test_grade_index_known_and_unknown():
    assert grade_index('3a') == 0
    assert grade_index('9c') == len(GRADE_ORDER) - 1
    assert grade_index('7a') == GRADE_ORDER.index('7a')
    for unknown in ('', None, 'xx', '10a', '2'):
        assert grade_index(unknown) == -1


def test_grade_index_between_grade_counts_as_its_base():
    assert grade_index('7a/+') == grade_index('7a')
    assert grade_index('7a+/b') == grade_index('7a+')


def test_grade_rank_between_grade_sits_between_neighbours():
    assert grade_rank('7a') < grade_rank('7a/+') < grade_rank('7a+')
    assert grade_rank('7a+') < grade_rank('7a+/b') < grade_rank('7b')


def test_grade_rank_unknown_is_negative():
    assert grade_rank('') == -1 and grade_rank(None) == -1 and grade_rank('abc') == -1


def test_grade_order_is_strictly_increasing_in_rank():
    ranks = [grade_rank(g) for g in GRADE_ORDER]
    assert ranks == sorted(ranks) and len(set(ranks)) == len(ranks)


# ─── max_grade / effective_cotation ─────────────────────────────────────────

def test_max_grade():
    assert max_grade(['6a', '7a', '5c']) == '7a'
    assert max_grade(['7a', '7a/+']) == '7a/+'
    assert max_grade(['7a/+', '7a+']) == '7a+'


def test_max_grade_ignores_invalid_and_handles_empty():
    assert max_grade(['', None, 'zz', '5b']) == '5b'
    assert max_grade([]) is None
    assert max_grade(['', None]) is None


def test_effective_cotation_uses_high_grade_for_gv():
    for t in ('grande_voie', 'trad_gv'):
        assert effective_cotation(asc(type=t, cotation='6a', cotation_haute='7a')) == '7a'


def test_effective_cotation_falls_back_to_low_grade():
    assert effective_cotation(asc(type='grande_voie', cotation='6a', cotation_haute=None)) == '6a'
    assert effective_cotation(asc(type='grande_voie', cotation='6a', cotation_haute='')) == '6a'


def test_effective_cotation_ignores_high_grade_on_other_types():
    assert effective_cotation(asc(type='voie', cotation='6a', cotation_haute='7a')) == '6a'


# ─── Cotation alpine ────────────────────────────────────────────────────────

@pytest.mark.parametrize('classic, alpine', [
    ('3a', 'PD'), ('3c+', 'PD'), ('4a', 'AD-'), ('4a+', 'AD-'), ('4b', 'AD'), ('4c', 'AD+'),
    ('5a', 'D-'), ('5b', 'D'), ('5c', 'D+'), ('5c+', 'D+'), ('6a', 'TD-'), ('6a+', 'TD-'),
    ('6b', 'TD'), ('6c', 'TD+'), ('7a', 'ED-'), ('7b', 'ED'), ('7c+', 'ED+'),
    ('8a', 'ABO-'), ('8b', 'ABO'), ('8c', 'ABO+'), ('9c', 'ABO+'),
])
def test_alpine_from_classic(classic, alpine):
    assert alpine_from_classic(classic) == alpine


def test_alpine_between_grade_uses_base():
    assert alpine_from_classic('7a/+') == 'ED-'


@pytest.mark.parametrize('bad', [None, '', 'xx', '2'])
def test_alpine_unknown_grade_is_none(bad):
    assert alpine_from_classic(bad) is None


def test_alpine_is_monotonic_over_the_scale():
    labels = [a for a, _ in ALPINE_ANCHORS]
    seen = [labels.index(alpine_from_classic(g)) for g in GRADE_ORDER]
    assert seen == sorted(seen)


# ─── Tri des ascensions ─────────────────────────────────────────────────────

def test_sort_hardest_first():
    rows = [asc('a', '5c'), asc('b', '7a'), asc('c', '6b')]
    assert [r['nom'] for r in sort_ascensions(rows)] == ['b', 'c', 'a']


def test_sort_same_grade_most_recent_first():
    rows = [asc('a', '6a', '2026-01-01'), asc('b', '6a', '2026-03-01'), asc('c', '6a', '2026-02-01')]
    assert [r['nom'] for r in sort_ascensions(rows)] == ['b', 'c', 'a']


def test_sort_same_grade_and_date_alphabetical_ignoring_case_and_accents():
    rows = [asc('zèbre'), asc('Étoile'), asc('abeille')]
    assert [r['nom'] for r in sort_ascensions(rows)] == ['abeille', 'Étoile', 'zèbre']


def test_sort_between_grade_above_base_below_next():
    rows = [asc('plus', '7a+'), asc('base', '7a'), asc('between', '7a/+')]
    assert [r['nom'] for r in sort_ascensions(rows)] == ['plus', 'between', 'base']


def test_sort_uses_high_grade_for_gv_and_puts_ungraded_last():
    rows = [asc('sans', None), asc('gv', '5a', type='grande_voie', cotation_haute='7a'), asc('b', '6c')]
    assert [r['nom'] for r in sort_ascensions(rows)] == ['gv', 'b', 'sans']


def test_sort_handles_missing_dates():
    rows = [asc('a', '6a', None), asc('b', '6a', '2026-01-01')]
    assert [r['nom'] for r in sort_ascensions(rows)] == ['b', 'a']


# ─── Paliers (tick list) ────────────────────────────────────────────────────

@pytest.mark.parametrize('grade', ['3a', '4c', '5c', '5c+'])
def test_palier_below_6_is_grouped(grade):
    assert palier_of(grade) == {'key': 'lt6', 'label': '≤ 5c+', 'order': -1}


@pytest.mark.parametrize('grade, key', [('6a', '6a'), ('6a+', '6a'), ('6b', '6b'), ('6c+', '6c'), ('7a', '7a'), ('9c', '9c')])
def test_palier_per_level_from_6(grade, key):
    p = palier_of(grade)
    assert p['key'] == key and p['label'] == key


def test_palier_between_grade_uses_base():
    assert palier_of('6b/+')['key'] == '6b'


@pytest.mark.parametrize('bad', [None, '', 'zz'])
def test_palier_without_grade(bad):
    assert palier_of(bad) == {'key': 'none', 'label': 'Sans cotation', 'order': 999}


def test_palier_order_increases_with_difficulty():
    keys = ['6a', '6b', '6c', '7a', '7b', '7c', '8a']
    orders = [palier_of(k)['order'] for k in keys]
    assert orders == sorted(orders) and palier_of('5a')['order'] < orders[0] < palier_of(None)['order']
