"""src/services/tags.py : listes personnalisables, choix d'une ascension."""
import pytest

from src.constants import MAX_TAGS_PER_LIST, TAG_CATS, TAG_MAX_LEN, TAG_ORDER
from src.errors import ValidationError
from src.services import tags
from tests.helpers import add_ascension, scalar


def test_options_are_seeded_on_first_access(conn, uid):
    assert tags.get_options(conn, uid, 'fixation') == TAG_CATS['fixation']['defaults']


def test_options_are_per_user(conn, uid, uid2):
    tags.add_option(conn, uid, 'roche', 'Silex')
    assert 'Silex' not in tags.get_options(conn, uid2, 'roche')


def test_all_options_covers_every_category(conn, uid):
    assert list(tags.all_options(conn, uid)) == TAG_ORDER


def test_deleting_all_options_does_not_reseed(conn, uid):
    for nom in list(tags.get_options(conn, uid, 'coinceur')):
        tags.delete_option(conn, uid, 'coinceur', nom)
    assert tags.get_options(conn, uid, 'coinceur') == []


def test_add_option_appends_and_returns_flag(conn, uid):
    assert tags.add_option(conn, uid, 'roche', '  Silex  ') == ('Silex', False)
    assert tags.get_options(conn, uid, 'roche')[-1] == 'Silex'


def test_add_option_case_insensitive_returns_existing(conn, uid):
    assert tags.add_option(conn, uid, 'roche', 'grès') == ('Grès', True)
    assert len(tags.get_options(conn, uid, 'roche')) == len(TAG_CATS['roche']['defaults'])


def test_add_option_collapses_inner_spaces(conn, uid):
    assert tags.add_option(conn, uid, 'roche', 'Roche   très   dure')[0] == 'Roche très dure'


@pytest.mark.parametrize('name', ['', '   ', None, 5, 'x' * (TAG_MAX_LEN + 1)])
def test_add_option_invalid_name(conn, uid, name):
    with pytest.raises(ValidationError):
        tags.add_option(conn, uid, 'roche', name)


def test_add_option_unknown_category(conn, uid):
    with pytest.raises(ValidationError):
        tags.add_option(conn, uid, 'inconnue', 'x')


def test_add_option_max_length_accepted(conn, uid):
    nom = 'x' * TAG_MAX_LEN
    assert tags.add_option(conn, uid, 'roche', nom) == (nom, False)


def test_add_option_list_limit(conn, uid):
    n = len(tags.get_options(conn, uid, 'roche'))
    for i in range(MAX_TAGS_PER_LIST - n):
        tags.add_option(conn, uid, 'roche', f'R{i}')
    with pytest.raises(ValidationError):
        tags.add_option(conn, uid, 'roche', 'de trop')


def test_delete_option_case_insensitive(conn, uid):
    tags.delete_option(conn, uid, 'roche', 'GRÈS')   # accent différent : ne correspond pas
    assert 'Grès' in tags.get_options(conn, uid, 'roche')
    tags.delete_option(conn, uid, 'roche', 'grès')
    assert 'Grès' not in tags.get_options(conn, uid, 'roche')


def test_delete_option_errors(conn, uid):
    with pytest.raises(ValidationError):
        tags.delete_option(conn, uid, 'inconnue', 'x')
    with pytest.raises(ValidationError):
        tags.delete_option(conn, uid, 'roche', '  ')


def test_delete_option_unknown_name_is_harmless(conn, uid):
    tags.delete_option(conn, uid, 'roche', 'Inexistante')
    assert len(tags.get_options(conn, uid, 'roche')) == len(TAG_CATS['roche']['defaults'])


def test_delete_option_keeps_choice_on_ascensions(conn, uid):
    a = add_ascension(conn, uid)
    tags.replace_ascension_tags(conn, a, {'roche': ['Grès']})
    tags.delete_option(conn, uid, 'roche', 'Grès')
    assert tags.get_ascension_tags(conn, a, ['roche']) == {'roche': ['Grès']}


# ─── Choix d'une ascension ───────────────────────────────────────────────────

def test_clean_selection_limits_to_allowed_and_dedups():
    sel = tags.clean_tag_selection({'roche': ['Grès', 'grès', ' Calcaire '], 'fixation': ['Broches']}, ['roche'])
    assert sel == {'roche': ['Grès', 'Calcaire']}


def test_clean_selection_non_dict_gives_empty_lists():
    assert tags.clean_tag_selection(None, ['roche', 'grimpe']) == {'roche': [], 'grimpe': []}
    assert tags.clean_tag_selection('x', ['roche']) == {'roche': []}


def test_clean_selection_invalid_list():
    with pytest.raises(ValidationError):
        tags.clean_tag_selection({'roche': 'Grès'}, ['roche'])
    with pytest.raises(ValidationError):
        tags.clean_tag_selection({'roche': ['a'] * (MAX_TAGS_PER_LIST + 1)}, ['roche'])


def test_replace_and_get_ascension_tags(conn, uid):
    a = add_ascension(conn, uid)
    tags.replace_ascension_tags(conn, a, {'roche': ['Grès', 'Calcaire'], 'fixation': ['Spits']})
    assert tags.get_ascension_tags(conn, a, ['roche', 'fixation', 'coinceur']) == {
        'roche': ['Grès', 'Calcaire'], 'fixation': ['Spits'], 'coinceur': []}
    tags.replace_ascension_tags(conn, a, {'roche': ['Granite']})
    assert tags.get_ascension_tags(conn, a, ['roche', 'fixation']) == {'roche': ['Granite'], 'fixation': []}


def test_get_ascension_tags_only_requested_categories(conn, uid):
    a = add_ascension(conn, uid)
    tags.replace_ascension_tags(conn, a, {'roche': ['Grès'], 'fixation': ['Spits']})
    assert tags.get_ascension_tags(conn, a, ['roche']) == {'roche': ['Grès']}
