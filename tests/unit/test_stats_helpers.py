"""src/services/stats.py : saisons et libellés (sans base)."""
import pytest

from src.services.stats import season_index, season_label


@pytest.mark.parametrize('iso, year, k', [
    ('2026-03-19', 2025, 3),   # hiver (jusqu'au 19/03)
    ('2026-03-20', 2026, 0),   # printemps
    ('2026-06-20', 2026, 0),
    ('2026-06-21', 2026, 1),   # été
    ('2026-09-21', 2026, 1),
    ('2026-09-22', 2026, 2),   # automne
    ('2026-12-20', 2026, 2),
    ('2026-12-21', 2026, 3),   # hiver (rattaché à l'année où il débute)
    ('2026-12-31', 2026, 3),
    ('2026-01-01', 2025, 3),
    ('2026-02-28', 2025, 3),
])
def test_season_index_boundaries(iso, year, k):
    assert season_index(iso) == year * 4 + k


def test_season_index_is_monotonic_over_a_year():
    from datetime import date, timedelta
    d, last = date(2025, 1, 1), -1
    while d.year < 2027:
        n = season_index(d.isoformat())
        assert n >= last
        last = n
        d += timedelta(days=1)


def test_season_label():
    assert season_label(2026 * 4 + 0) == {'name': 'Printemps', 'year': '2026'}
    assert season_label(2026 * 4 + 1) == {'name': 'Été', 'year': '2026'}
    assert season_label(2026 * 4 + 2) == {'name': 'Automne', 'year': '2026'}
    assert season_label(2026 * 4 + 3) == {'name': 'Hiver', 'year': '2026-27'}
    assert season_label(2099 * 4 + 3)['year'] == '2099-00'
