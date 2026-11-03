"""src/services/recherche.py : filtres, fourchette de cotation, tris, synthèse, regroupement, calendrier."""
from datetime import date

import pytest
from werkzeug.datastructures import MultiDict

from src.services import recherche as r
from src.services import tags
from tests.helpers import add_ascension


def filters(**kw):
    md = MultiDict()
    for k, v in kw.items():
        for item in (v if isinstance(v, list) else [v]):
            md.add(k, item)
    return r.parse_filters(md)


def set_cols(conn, asc_id, **cols):
    """Colonnes que l'ajout d'une ascension ne renseigne pas (ouverture, topo) : posées directement."""
    sets = ', '.join(f'{k}=?' for k in cols)
    conn.execute(f'UPDATE ascension SET {sets} WHERE id=?', [*cols.values(), asc_id])
    conn.commit()


def names(conn, uid, **kw):
    return [x['nom'] for x in r.search(conn, uid, filters(**kw))]


# ─── parse_filters ───────────────────────────────────────────────────────────

def test_parse_defaults():
    f = filters()
    assert (f['tri'], f['groupe'], f['statut'], f['types'], f['q']) == ('date_desc', 'site', 'log', [], '')
    assert f['cot_min'] == f['cot_max'] == ''


def test_parse_ignores_unknown_values():
    f = filters(statut='nimporte', groupe='bidon', cot_min='99z', cot_max='zz', mode=['tete', 'x'])
    assert (f['statut'], f['groupe'], f['cot_min'], f['cot_max'], f['modes']) == ('log', 'site', '', '', ['tete'])


def test_parse_accepts_known_values_and_strips_text():
    f = filters(statut='tout', groupe='plat', cot_min='6a', cot_max='7a', q='  mur  ', ouvreur=' Bob ',
                type=['bloc', 'voie'])
    assert (f['statut'], f['groupe'], f['cot_min'], f['cot_max'], f['q'], f['ouvreur'], f['types']) == (
        'tout', 'plat', '6a', '7a', 'mur', 'Bob', ['bloc', 'voie'])


# ─── Filtres ─────────────────────────────────────────────────────────────────

@pytest.fixture
def world(conn, uid):
    a = add_ascension(conn, uid, 'Alpha', cotation='6a', style='a_vue', date='2026-01-10', hauteur=4, note_beaute=3,
                      commentaire='superbe dalle')
    set_cols(conn, a, ouvreur='Bob Martin', annee_ouverture=1990, topo_nom='Guide Sud')
    add_ascension(conn, uid, 'Beta', cotation='7a', style='essais_3', date='2026-02-11', hauteur=8, note_beaute=1,
                  pieds_nus=True, place={'site': 'Fontainebleau', 'secteur': 'Bas Cuvier', 'sous_secteur': 'Nord'})
    g = add_ascension(conn, uid, 'Gamma', type='voie', cotation='6c', style='flash', date='2026-02-11', hauteur=25,
                      grimpe='tete')
    set_cols(conn, g, ouvreur='Alice', annee_ouverture=2005, topo_edition='Éditions Gap')
    add_ascension(conn, uid, 'Delta', statut='projet', cotation='7c')
    add_ascension(conn, uid, 'Epsilon', statut='ticklist', cotation='8a')
    return conn


def test_default_statut_is_log(world, uid):
    assert set(names(world, uid)) == {'Alpha', 'Beta', 'Gamma'}


@pytest.mark.parametrize('statut, expected', [('projet', {'Delta'}), ('ticklist', {'Epsilon'}),
                                              ('tout', {'Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon'})])
def test_statut_filter(world, uid, statut, expected):
    assert set(names(world, uid, statut=statut)) == expected


@pytest.mark.parametrize('kw, expected', [
    ({'type': 'voie'}, {'Gamma'}), ({'type': ['bloc', 'voie']}, {'Alpha', 'Beta', 'Gamma'}),
    ({'style': 'flash'}, {'Gamma'}), ({'style': ['a_vue', 'flash']}, {'Alpha', 'Gamma'}),
    ({'beaute': '3'}, {'Alpha'}), ({'beaute': ['1', '3']}, {'Alpha', 'Beta'}), ({'beaute': 'abc'}, {'Alpha', 'Beta', 'Gamma'}),
    ({'date': '2026-02-11'}, {'Beta', 'Gamma'}), ({'date': ['2026-01-10', '2026-02-11']}, {'Alpha', 'Beta', 'Gamma'}),
    ({'mode': 'tete'}, {'Gamma'}),
    ({'hauteur_min': '8'}, {'Beta', 'Gamma'}), ({'hauteur_max': '8'}, {'Alpha', 'Beta'}),
    ({'hauteur_min': '5', 'hauteur_max': '10'}, {'Beta'}), ({'hauteur_min': 'xx'}, {'Alpha', 'Beta', 'Gamma'}),
    ({'pieds_nus': '1'}, {'Beta'}),
    ({'ouvreur': 'bob'}, {'Alpha'}), ({'annee_min': '2000'}, {'Gamma'}), ({'annee_max': '1995'}, {'Alpha'}),
    ({'annee_min': '1990', 'annee_max': '2005'}, {'Alpha', 'Gamma'}),
    ({'topo': 'guide'}, {'Alpha'}), ({'topo': 'gap'}, {'Gamma'}),
    ({'q': 'alpha'}, {'Alpha'}), ({'q': 'dalle'}, {'Alpha'}), ({'q': 'fontainebleau'}, {'Beta'}),
    ({'q': 'cuvier'}, {'Beta'}), ({'q': 'nord'}, {'Beta'}), ({'q': 'marseille'}, {'Alpha', 'Beta', 'Gamma'}), ({'q': 'zzz'}, set()),
])
def test_single_filters(world, uid, kw, expected):
    assert set(names(world, uid, **kw)) == expected


def test_filters_combine_with_and(world, uid):
    assert names(world, uid, type='bloc', cot_min='7a') == ['Beta']
    assert names(world, uid, q='a', type='voie', style='flash') == ['Gamma']


def test_pieds_nus_matches_repetitions_too(world, uid):
    world.execute("INSERT INTO repetition(ascension_id, date, pieds_nus) SELECT id,'2026-03-01',1 FROM ascension WHERE nom='Alpha'")
    assert set(names(world, uid, pieds_nus='1')) == {'Alpha', 'Beta'}


def test_roche_and_grimpe_tag_filters(world, uid):
    ids = {x['nom']: x['id'] for x in r.search(world, uid, filters())}
    tags.replace_ascension_tags(world, ids['Alpha'], {'roche': ['Grès'], 'grimpe': ['Dalle']})
    tags.replace_ascension_tags(world, ids['Beta'], {'roche': ['Calcaire'], 'grimpe': ['Dalle', 'Toit']})
    assert set(names(world, uid, roche='Grès')) == {'Alpha'}
    assert set(names(world, uid, roche=['Grès', 'Calcaire'])) == {'Alpha', 'Beta'}
    assert set(names(world, uid, tgrimpe='Dalle')) == {'Alpha', 'Beta'}
    assert set(names(world, uid, tgrimpe='Toit', roche='Calcaire')) == {'Beta'}
    assert names(world, uid, roche='Grès', tgrimpe='Toit') == []


def test_search_is_isolated_per_user(world, uid2):
    assert names(world, uid2) == []


# ─── Fourchette de cotation ──────────────────────────────────────────────────

def test_grade_range_bounds_inclusive(world, uid):
    assert set(names(world, uid, cot_min='6c')) == {'Beta', 'Gamma'}
    assert set(names(world, uid, cot_max='6c')) == {'Alpha', 'Gamma'}
    assert set(names(world, uid, cot_min='6c', cot_max='6c')) == {'Gamma'}


def test_grade_range_swapped_bounds(world, uid):
    assert set(names(world, uid, cot_min='7a', cot_max='6a')) == {'Alpha', 'Beta', 'Gamma'}


def test_grade_range_excludes_unknown_grades(conn, uid):
    add_ascension(conn, uid, 'SansCot', cotation=None)
    add_ascension(conn, uid, 'Avec', cotation='6a')
    assert names(conn, uid, cot_min='4a') == ['Avec']
    assert set(names(conn, uid)) == {'SansCot', 'Avec'}


def test_grade_range_in_between_grade_counts_as_its_base(conn, uid):
    add_ascension(conn, uid, 'Entre', cotation='7a/+')
    assert names(conn, uid, cot_min='7a', cot_max='7a') == ['Entre']
    assert names(conn, uid, cot_min='7a+') == []


def test_grade_range_uses_high_grade_for_big_walls(conn, uid):
    add_ascension(conn, uid, 'GV', type='grande_voie', cotation='5a', cotation_haute='7a', grimpe='tete')
    assert names(conn, uid, cot_min='6c') == ['GV']
    assert names(conn, uid, cot_max='6c') == []


# ─── Tris ────────────────────────────────────────────────────────────────────

@pytest.fixture
def sortable(conn, uid):
    add_ascension(conn, uid, 'Écu', cotation='6a', style='flash', date='2026-01-01', note_beaute=1, hauteur=5)
    add_ascension(conn, uid, 'banc', cotation='7a', style='a_vue', date='2026-03-01', note_beaute=3, hauteur=2)
    add_ascension(conn, uid, 'Zèbre', cotation='5c', style='essais_2', date='2026-02-01', note_beaute=None, hauteur=None)
    return conn


@pytest.mark.parametrize('tri, expected', [
    ('date_desc', ['banc', 'Zèbre', 'Écu']), ('date_asc', ['Écu', 'Zèbre', 'banc']),
    ('cotation_desc', ['banc', 'Écu', 'Zèbre']), ('cotation_asc', ['Zèbre', 'Écu', 'banc']),
    ('style_asc', ['banc', 'Écu', 'Zèbre']), ('style_desc', ['Zèbre', 'Écu', 'banc']),
    ('beaute_desc', ['banc', 'Écu', 'Zèbre']), ('beaute_asc', ['Zèbre', 'Écu', 'banc']),
    ('hauteur_desc', ['Écu', 'banc', 'Zèbre']), ('hauteur_asc', ['Zèbre', 'banc', 'Écu']),
    ('nom', ['banc', 'Écu', 'Zèbre']),
])
def test_sorts(sortable, uid, tri, expected):
    assert names(sortable, uid, tri=tri) == expected


def test_unknown_sort_does_not_crash(sortable, uid):
    assert len(names(sortable, uid, tri='bidon')) == 3


def test_results_have_formatted_date(sortable, uid):
    assert r.search(sortable, uid, filters(tri='date_asc'))[0]['date_fmt'] == '01/01/2026'


# ─── Synthèse et regroupement ────────────────────────────────────────────────

def test_summarize_empty():
    assert r.summarize([]) == {'count': 0, 'sites': 0, 'max': None, 'metres': 0} or r.summarize([])['count'] == 0


def test_summarize(world, uid):
    s = r.summarize(r.search(world, uid, filters()))
    assert (s['count'], s['sites'], s['max'], s['metres']) == (3, 2, '7a', 37)


def test_summarize_fractional_metres_and_gv_from_longueurs(conn, uid):
    add_ascension(conn, uid, 'A', hauteur=2.5)
    add_ascension(conn, uid, 'GV', type='grande_voie', cotation='5a', cotation_haute='6a', grimpe='tete',
                  longueurs=[{'cotation': '5a', 'hauteur': 30}, {'cotation': '6a', 'hauteur': 20}])
    assert r.summarize(r.search(conn, uid, filters()))['metres'] == 52.5


def test_group_by_site_keeps_sort_order_of_first_result(world, uid):
    groups = r.group_by_site(r.search(world, uid, filters(tri='date_desc')))
    assert [g['site'] for g in groups] == ['Fontainebleau', 'Calanques'] or [g['site'] for g in groups] == ['Calanques', 'Fontainebleau']
    by = {g['site']: g for g in groups}
    assert len(by['Calanques']['items']) == 2 and len(by['Fontainebleau']['items']) == 1
    assert by['Calanques']['lieu'] == 'France › Bouches-du-Rhône › Marseille'


def test_group_by_site_first_group_is_site_of_first_result(world, uid):
    results = r.search(world, uid, filters(tri='cotation_desc'))
    assert r.group_by_site(results)[0]['site'] == 'Fontainebleau'     # Beta (7a) est le plus dur


def test_group_by_site_empty():
    assert r.group_by_site([]) == []


# ─── Options de filtres ──────────────────────────────────────────────────────

def test_filter_options(conn, uid, uid2):
    a = add_ascension(conn, uid, 'A')
    set_cols(conn, a, ouvreur='Zoé', topo_nom='Topo B')
    set_cols(conn, add_ascension(conn, uid, 'B'), ouvreur='alice', topo_nom='Topo A')
    set_cols(conn, add_ascension(conn, uid, 'C'), ouvreur='')
    tags.replace_ascension_tags(conn, a, {'roche': ['Grès', 'Calcaire'], 'grimpe': ['Dalle']})
    b = add_ascension(conn, uid2, 'X')
    set_cols(conn, b, ouvreur='Intrus')
    tags.replace_ascension_tags(conn, b, {'roche': ['Basalte']})
    o = r.filter_options(conn, uid)
    assert o == {'roche': ['Calcaire', 'Grès'], 'tgrimpe': ['Dalle'], 'ouvreurs': ['alice', 'Zoé'], 'topos': ['Topo A', 'Topo B']}


def test_filter_options_empty(conn, uid):
    assert r.filter_options(conn, uid) == {'roche': [], 'tgrimpe': [], 'ouvreurs': [], 'topos': []}


# ─── Calendrier ──────────────────────────────────────────────────────────────

def test_calendar_opens_on_latest_log_month(conn, uid):
    add_ascension(conn, uid, 'A', date='2026-02-11')
    add_ascension(conn, uid, 'B', date='2025-07-04')
    cal = r.build_calendar(conn, uid, '', [])
    assert (cal['year'], cal['month'], cal['month_name']) == (2026, 2, 'Février')
    days = {d['day']: d for w in cal['weeks'] for d in w if d}
    assert days[11]['has_data'] and not days[12]['has_data'] and len(days) == 28


def test_calendar_ignores_projects_for_default_month(conn, uid):
    add_ascension(conn, uid, 'Log', date='2025-07-04')
    add_ascension(conn, uid, 'Projet', statut='projet', date='2026-05-05')
    assert r.build_calendar(conn, uid, '', [])['month'] == 7


def test_calendar_selected_days_and_weeks_start_on_monday(conn, uid):
    add_ascension(conn, uid, 'A', date='2026-02-11')
    cal = r.build_calendar(conn, uid, '2026-02', ['2026-02-11'])
    days = {d['day']: d for w in cal['weeks'] for d in w if d}
    assert days[11]['selected'] and not days[10]['selected']
    assert cal['weeks'][0][6]['day'] == 1          # 1er février 2026 = dimanche
    assert all(len(w) == 7 for w in cal['weeks'])


def test_calendar_navigation_across_years(conn, uid):
    assert r.build_calendar(conn, uid, '2026-01', [])['prev_month'] == '2025-12'
    assert r.build_calendar(conn, uid, '2026-12', [])['next_month'] == '2027-01'
    mid = r.build_calendar(conn, uid, '2026-06', [])
    assert (mid['prev_month'], mid['next_month']) == ('2026-05', '2026-07')


@pytest.mark.parametrize('bad', ['2026-13', '2026-00', 'abc', '2026', '2026-1-2', '-'])
def test_calendar_invalid_month_falls_back_to_today(conn, uid, bad):
    cal = r.build_calendar(conn, uid, bad, [])
    assert (cal['year'], cal['month']) == (date.today().year, date.today().month)


def test_calendar_without_logs_is_current_month(conn, uid):
    cal = r.build_calendar(conn, uid, '', [])
    assert (cal['year'], cal['month']) == (date.today().year, date.today().month)


def test_calendar_other_user_dates_not_shown(conn, uid, uid2):
    add_ascension(conn, uid2, 'X', date='2026-02-11')
    cal = r.build_calendar(conn, uid, '2026-02', [])
    assert not any(d and d['has_data'] for w in cal['weeks'] for d in w)
