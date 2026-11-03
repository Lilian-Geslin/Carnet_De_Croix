"""src/services/stats.py : chiffres par discipline, modes, mètres, évolution (helpers purs dans tests/unit)."""
from datetime import date

from src.constants import ASCENSION_TYPES
from src.services import stats
from tests.helpers import add_ascension


def rep(conn, asc, grimpe=None, date_='2026-02-01'):
    conn.execute('INSERT INTO repetition(ascension_id, date, grimpe) VALUES(?,?,?)', (asc, date_, grimpe))
    conn.commit()


def test_empty_account(conn, uid):
    s = stats.compute_stats(conn, uid)
    assert s['nb_total'] == 0 and s['total_metres'] == 0 and s['cot_max_global'] in (None, '')
    assert list(s['per_type']) == list(ASCENSION_TYPES)
    assert s['evolution'] == {'seasons': [], 'series': {}}
    assert s['nb_pays'] == 0


def test_counts_only_logs_of_the_user(conn, uid, uid2):
    add_ascension(conn, uid, 'L1')
    add_ascension(conn, uid, 'L2', type='voie', grimpe='tete')
    add_ascension(conn, uid, 'P', statut='projet')
    add_ascension(conn, uid, 'T', statut='ticklist')
    add_ascension(conn, uid2, 'Autre')
    s = stats.compute_stats(conn, uid)
    assert s['nb_total'] == 2
    assert (s['per_type']['bloc']['nb'], s['per_type']['voie']['nb'], s['per_type']['psychobloc']['nb']) == (1, 1, 0)


def test_labels_and_geo_counts_are_present(conn, uid):
    add_ascension(conn, uid)
    s = stats.compute_stats(conn, uid)
    assert s['per_type']['bloc']['label'] == 'Bloc'
    assert (s['nb_pays'], s['nb_sites'], s['nb_secteurs']) == (1, 1, 1)


def test_cot_max_per_type_and_global(conn, uid):
    add_ascension(conn, uid, 'A', cotation='6a')
    add_ascension(conn, uid, 'B', cotation='7a')
    add_ascension(conn, uid, 'C', type='voie', cotation='8a', grimpe='tete')
    s = stats.compute_stats(conn, uid)
    assert s['per_type']['bloc']['cot_max'] == '7a' and s['per_type']['voie']['cot_max'] == '8a'
    assert s['cot_max_global'] == '8a'


def test_grande_voie_uses_high_grade(conn, uid):
    add_ascension(conn, uid, 'GV', type='grande_voie', cotation='5a', cotation_haute='6c', grimpe='tete')
    assert stats.compute_stats(conn, uid)['per_type']['grande_voie']['cot_max'] == '6c'


def test_metres_sum_heights(conn, uid):
    add_ascension(conn, uid, 'A', hauteur=4)
    add_ascension(conn, uid, 'B', hauteur=3.5)
    add_ascension(conn, uid, 'C', hauteur=None)
    s = stats.compute_stats(conn, uid)
    assert s['per_type']['bloc']['metres'] == 7.5 and s['total_metres'] == 7.5


def test_repetitions_add_metres_but_not_counts(conn, uid):
    a = add_ascension(conn, uid, 'A', hauteur=4)
    rep(conn, a)
    rep(conn, a)
    s = stats.compute_stats(conn, uid)['per_type']['bloc']
    assert (s['nb'], s['metres']) == (1, 12)


def test_grande_voie_metres_from_longueurs_when_no_height(conn, uid):
    add_ascension(conn, uid, 'GV', type='grande_voie', cotation='5a', cotation_haute='6a', grimpe='tete',
                  longueurs=[{'cotation': '5a', 'hauteur': 30}, {'cotation': '6a', 'hauteur': 25}])
    add_ascension(conn, uid, 'GV2', type='grande_voie', cotation='5a', cotation_haute='6a', grimpe='tete',
                  hauteur=100, longueurs=[{'cotation': '5a', 'hauteur': 10}])
    assert stats.compute_stats(conn, uid)['per_type']['grande_voie']['metres'] == 155


def test_grande_voie_repetition_counts_longueurs_height_again(conn, uid):
    a = add_ascension(conn, uid, 'GV', type='grande_voie', cotation='5a', cotation_haute='6a', grimpe='tete',
                      longueurs=[{'cotation': '5a', 'hauteur': 30}])
    rep(conn, a, 'tete')
    assert stats.compute_stats(conn, uid)['per_type']['grande_voie']['metres'] == 60


def test_style_distribution_groups(conn, uid):
    add_ascension(conn, uid, 'A', style='a_vue')
    add_ascension(conn, uid, 'B', style='flash')
    add_ascension(conn, uid, 'C', style='essais_3')
    add_ascension(conn, uid, 'D', style='plus_5')
    add_ascension(conn, uid, 'E', style=None)
    b = stats.compute_stats(conn, uid)['per_type']['bloc']
    assert b['style_distrib'] == {'a_vue': 1, 'flash': 1, 'travaille': 2} and b['nb'] == 5


def test_distribution_groups_in_between_grades_with_base_grade(conn, uid):
    add_ascension(conn, uid, 'A', cotation='7a')
    add_ascension(conn, uid, 'B', cotation='7a/+')
    add_ascension(conn, uid, 'C', cotation=None)
    d = stats.compute_stats(conn, uid)['per_type']['bloc']['distrib']
    assert d == {'7a': 2, 'Inconnue': 1}


def test_cotation_perso_overrides_cotation(conn, uid):
    add_ascension(conn, uid, 'A', cotation='6a', cotation_perso='6b')
    assert stats.compute_stats(conn, uid)['per_type']['bloc']['cot_max'] in ('6b', '6a')


def test_style_max_per_group(conn, uid):
    add_ascension(conn, uid, 'A', cotation='6a', style='a_vue')
    add_ascension(conn, uid, 'B', cotation='6c', style='a_vue')
    add_ascension(conn, uid, 'C', cotation='7a', style='essais_2')
    sm = stats.compute_stats(conn, uid)['per_type']['bloc']['style_max']
    assert sm['a_vue'] == '6c' and sm['travaille'] == '7a' and not sm['flash']


# ─── Seules les grimpes « en tête » comptent pour les voies et le trad (voie) ─

import pytest


@pytest.mark.parametrize('typ', ['voie', 'trad_voie'])
def test_only_lead_counts_for_voie_and_trad(conn, uid, typ):
    add_ascension(conn, uid, 'T', type=typ, grimpe='tete', hauteur=20, cotation='6a')
    add_ascension(conn, uid, 'M', type=typ, grimpe='moulinette', hauteur=10, cotation='7a')
    v = stats.compute_stats(conn, uid)
    t = v['per_type'][typ]
    assert (t['nb'], t['metres'], t['cot_max']) == (1, 20, '6a')
    assert v['nb_total'] == 1 and v['total_metres'] == 20 and v['cot_max_global'] == '6a'
    assert 'modes' not in t


@pytest.mark.parametrize('typ', ['grande_voie', 'trad_gv'])
def test_big_walls_count_in_every_mode(conn, uid, typ):
    add_ascension(conn, uid, 'T', type=typ, grimpe='tete', hauteur=100, cotation='5a', cotation_haute='6a')
    add_ascension(conn, uid, 'M', type=typ, grimpe='moulinette', hauteur=50, cotation='5a', cotation_haute='6c')
    add_ascension(conn, uid, 'Ancienne', type=typ, hauteur=10, cotation='5a', cotation_haute='6a')
    t = stats.compute_stats(conn, uid)['per_type'][typ]
    assert (t['nb'], t['metres'], t['cot_max']) == (3, 160, '6c') and 'sans_mode' not in t


def test_boulders_are_unaffected(conn, uid):
    add_ascension(conn, uid, 'B', hauteur=4)
    add_ascension(conn, uid, 'P', type='psychobloc', hauteur=6)
    s = stats.compute_stats(conn, uid)['per_type']
    assert (s['bloc']['nb'], s['psychobloc']['nb']) == (1, 1)


def test_moulinette_repetition_of_a_lead_ascension_is_ignored(conn, uid):
    a = add_ascension(conn, uid, 'V', type='voie', grimpe='tete', hauteur=20)
    rep(conn, a, 'moulinette')
    rep(conn, a, 'tete')
    rep(conn, a, None)
    v = stats.compute_stats(conn, uid)['per_type']['voie']
    assert (v['nb'], v['metres']) == (1, 40)         # l'ascension + la seule répétition en tête


def test_repetitions_of_big_walls_always_count(conn, uid):
    a = add_ascension(conn, uid, 'GV', type='grande_voie', cotation='5a', cotation_haute='6a', grimpe='tete', hauteur=100)
    rep(conn, a, 'moulinette')
    assert stats.compute_stats(conn, uid)['per_type']['grande_voie']['metres'] == 200


def test_ascension_without_mode_is_left_out_and_reported(conn, uid):
    add_ascension(conn, uid, 'Vieille', type='voie', hauteur=15)       # ancienne ascension sans mode
    add_ascension(conn, uid, 'Vieille 2', type='trad_voie', hauteur=15)
    add_ascension(conn, uid, 'Valeur bidon', type='voie', grimpe='bidon')
    add_ascension(conn, uid, 'Bonne', type='voie', grimpe='tete', hauteur=5)
    s = stats.compute_stats(conn, uid)
    assert s['per_type']['voie']['nb'] == 1 and s['per_type']['voie']['sans_mode'] == 2
    assert s['per_type']['trad_voie']['nb'] == 0 and s['per_type']['trad_voie']['sans_mode'] == 1
    assert s['nb_total'] == 1


def test_moulinette_is_ignored_by_the_evolution(conn, uid):
    add_ascension(conn, uid, 'M', type='voie', grimpe='moulinette', cotation='8a', date='2025-04-10')
    assert stats.compute_stats(conn, uid)['evolution'] == {'seasons': [], 'series': {}}


def test_exploration_counts_still_include_moulinette(conn, uid):
    add_ascension(conn, uid, 'M', type='voie', grimpe='moulinette')
    assert stats.compute_stats(conn, uid)['nb_sites'] == 1


@pytest.mark.parametrize('typ, grimpe, expected', [
    ('voie', 'tete', True), ('voie', 'moulinette', False), ('voie', None, False),
    ('trad_voie', 'tete', True), ('trad_voie', 'moulinette', False),
    ('grande_voie', 'moulinette', True), ('trad_gv', None, True), ('bloc', None, True), ('psychobloc', 'x', True),
])
def test_counts_in_stats(typ, grimpe, expected):
    assert stats.counts_in_stats(typ, grimpe) is expected


# ─── Évolution ───────────────────────────────────────────────────────────────

def test_evolution_series_start_at_first_season_of_type(conn, uid):
    add_ascension(conn, uid, 'A', cotation='6a', date='2025-04-10')    # printemps 2025
    add_ascension(conn, uid, 'B', cotation='6c', date='2025-04-20')
    add_ascension(conn, uid, 'V', type='voie', cotation='6a', grimpe='tete', date='2025-11-01')   # automne 2025
    e = stats.compute_stats(conn, uid)['evolution']
    assert e['seasons'][0] == {'name': 'Printemps', 'year': '2025'}
    assert e['seasons'][2] == {'name': 'Automne', 'year': '2025'}
    assert len(e['series']['bloc']) == len(e['series']['voie']) == len(e['seasons'])
    assert e['series']['bloc'][0] >= 0 and e['series']['bloc'][1] == -1      # rien l'été
    assert e['series']['voie'][:2] == [None, None] and e['series']['voie'][2] >= 0


def test_evolution_extends_to_current_season(conn, uid):
    add_ascension(conn, uid, 'A', date='2020-04-10')
    e = stats.compute_stats(conn, uid)['evolution']
    assert e['seasons'][-1] == stats.season_label(stats.season_index(date.today().isoformat()))


def test_evolution_ignores_logs_without_date_or_grade(conn, uid):
    add_ascension(conn, uid, 'SansDate', date=None)
    add_ascension(conn, uid, 'SansCot', cotation=None, date='2025-05-05')
    assert stats.compute_stats(conn, uid)['evolution'] == {'seasons': [], 'series': {}}


def test_winter_label_spans_two_years(conn, uid):
    add_ascension(conn, uid, 'A', date='2025-12-25')
    e = stats.compute_stats(conn, uid)['evolution']
    assert e['seasons'][0] == {'name': 'Hiver', 'year': '2025-26'}
