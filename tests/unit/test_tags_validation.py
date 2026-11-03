"""src/services/tags.py : fonctions pures (catégories, nettoyage, sélection)."""
import pytest

from src.constants import MAX_TAGS_PER_LIST, TAG_MAX_LEN
from src.errors import ValidationError
from src.services.tags import cats_for_type, clean_tag_name, clean_tag_selection


@pytest.mark.parametrize('asc_type, cats', [
    ('bloc', ['grimpe', 'roche']),
    ('psychobloc', ['grimpe', 'roche']),
    ('voie', ['grimpe', 'roche', 'fixation']),
    ('grande_voie', ['grimpe', 'roche', 'fixation']),
    ('trad_voie', ['grimpe', 'roche', 'coinceur']),
    ('trad_gv', ['grimpe', 'roche', 'coinceur']),
])
def test_cats_for_type(asc_type, cats):
    assert cats_for_type(asc_type) == cats


def test_cats_for_unknown_type_only_universal_categories():
    assert cats_for_type('inconnu') == ['grimpe', 'roche']


@pytest.mark.parametrize('raw, expected', [
    ('Friends', 'Friends'), ('  Mur   vertical ', 'Mur vertical'), ('a' * TAG_MAX_LEN, 'a' * TAG_MAX_LEN),
    ('', None), ('   ', None), (None, None), (5, None), ('a' * (TAG_MAX_LEN + 1), None),
])
def test_clean_tag_name(raw, expected):
    assert clean_tag_name(raw) == expected


def test_selection_keeps_only_allowed_categories():
    sel = clean_tag_selection({'roche': ['Grès'], 'fixation': ['Spits'], 'coinceur': ['Friends']}, ['roche', 'fixation'])
    assert sel == {'roche': ['Grès'], 'fixation': ['Spits']}


def test_selection_dedupes_ignoring_case_and_drops_invalid_names():
    sel = clean_tag_selection({'roche': ['Grès', 'grès', ' GRÈS ', '', 'Calcaire']}, ['roche'])
    assert sel == {'roche': ['Grès', 'Calcaire']}


def test_selection_missing_category_is_empty_list():
    assert clean_tag_selection({}, ['roche', 'grimpe']) == {'roche': [], 'grimpe': []}
    assert clean_tag_selection(None, ['roche']) == {'roche': []}
    assert clean_tag_selection('n importe quoi', ['roche']) == {'roche': []}


def test_selection_rejects_non_list_values():
    with pytest.raises(ValidationError):
        clean_tag_selection({'roche': 'Grès'}, ['roche'])


def test_selection_rejects_too_many_values():
    with pytest.raises(ValidationError):
        clean_tag_selection({'roche': [f'r{i}' for i in range(MAX_TAGS_PER_LIST + 1)]}, ['roche'])
