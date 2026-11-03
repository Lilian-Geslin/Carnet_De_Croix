"""src/constants.py : cohérence des listes de référence."""
from src import constants as c


def test_grade_order_has_no_duplicates_and_expected_bounds():
    assert len(set(c.GRADE_ORDER)) == len(c.GRADE_ORDER)
    assert c.GRADE_ORDER[0] == '3a' and c.GRADE_ORDER[-1] == '9c'


def test_every_type_has_a_label():
    assert set(c.TYPE_LABELS) == set(c.ASCENSION_TYPES)


def test_trad_labels_are_short():
    assert c.TYPE_LABELS['trad_voie'] == 'Trad' and c.TYPE_LABELS['trad_gv'] == 'Trad GV'


def test_gv_and_rope_types_are_valid_types():
    assert set(c.GV_TYPES) <= set(c.ASCENSION_TYPES)
    assert set(c.ROPE_TYPES) <= set(c.ASCENSION_TYPES)
    assert set(c.GV_TYPES) <= set(c.ROPE_TYPES)
    assert 'bloc' not in c.ROPE_TYPES and 'psychobloc' not in c.ROPE_TYPES


def test_styles_are_all_grouped_and_labelled():
    assert set(c.STYLE_ORDER) == set(c.STYLE_LABELS) == set(c.STYLE_GROUPS)
    assert set(c.STYLE_GROUPS.values()) == {'a_vue', 'flash', 'travaille'}


def test_alpine_anchors_reference_valid_grades():
    for label, anchor in c.ALPINE_ANCHORS:
        assert anchor == '2' or anchor in c.GRADE_ORDER, label


def test_tag_categories_are_consistent():
    assert set(c.TAG_ORDER) == set(c.TAG_CATS)
    for cat in c.TAG_CATS.values():
        assert cat['defaults'] and len(set(cat['defaults'])) == len(cat['defaults'])
        assert all(len(d) <= c.TAG_MAX_LEN for d in cat['defaults'])
        assert cat['types'] is None or set(cat['types']) <= set(c.ASCENSION_TYPES)


def test_geo_tables_in_hierarchy_order():
    assert c.GEO_TABLES == ('pays', 'departement', 'localisation', 'site', 'secteur', 'sous_secteur')


def test_statuts_and_modes():
    assert c.STATUTS == ('log', 'projet', 'ticklist')
    assert c.GRIMPE_MODES == ('tete', 'moulinette')


def test_envie_categories_are_performance_beaute_majeure():
    assert c.ENVIE_CATS == {'performance': 'Performance', 'beaute': 'Beauté', 'majeure': 'Majeure'}
    assert 'classique' not in c.ENVIE_CATS


def test_topo_pdf_limit_is_20_mo():
    assert c.TOPO_PDF_MAX_BYTES == 20 * 1024 * 1024


def test_topo_levels_exclude_country_and_departement():
    assert c.TOPO_NIVEAUX == ('localisation', 'site', 'secteur', 'sous_secteur')
    assert 'topo_id' in c.TOPO_FIELDS
