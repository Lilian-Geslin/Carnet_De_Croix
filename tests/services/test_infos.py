"""src/services/infos.py : lecture / écriture de la fiche « Plus d'informations »."""
import pytest

from src.errors import NotFoundError, ValidationError
from src.services import infos
from tests.helpers import add_ascension, scalar


def test_get_infos_structure_for_bloc(conn, uid):
    a = add_ascension(conn, uid, 'Bloc')
    d = infos.get_infos(conn, uid, a)
    assert (d['nom'], d['type'], d['statut'], d['nb_seances'], d['total_essais']) == ('Bloc', 'bloc', 'log', 0, 0)
    assert [c['key'] for c in d['cats']] == ['grimpe', 'roche']
    assert d['topo']['topo_type'] is None and d['ouverture'] == {'annee': None, 'ouvreur': None}
    assert d['reequipements'] == [] and set(d['options']) == {'grimpe', 'roche'}


@pytest.mark.parametrize('typ, cats', [
    ('voie', ['grimpe', 'roche', 'fixation']), ('grande_voie', ['grimpe', 'roche', 'fixation']),
    ('trad_voie', ['grimpe', 'roche', 'coinceur']), ('trad_gv', ['grimpe', 'roche', 'coinceur']),
    ('psychobloc', ['grimpe', 'roche']),
])
def test_get_infos_categories_depend_on_type(conn, uid, typ, cats):
    a = add_ascension(conn, uid, type=typ, grimpe='tete')
    assert [c['key'] for c in infos.get_infos(conn, uid, a)['cats']] == cats


def test_get_infos_not_found_for_other_user(conn, uid, uid2):
    a = add_ascension(conn, uid)
    with pytest.raises(NotFoundError):
        infos.get_infos(conn, uid2, a)
    with pytest.raises(NotFoundError):
        infos.get_infos(conn, uid, 9999)


def test_get_infos_includes_seances_and_totals(conn, uid):
    a = add_ascension(conn, uid, statut='projet', nb_essais_projet=4)
    d = infos.get_infos(conn, uid, a)
    assert (d['nb_seances'], d['total_essais']) == (1, 4)


FULL = {'topo_type': 'papier', 'topo_nom': 'Guide Calanques', 'topo_edition': 'Gap', 'topo_annee': 2019,
        'topo_page': '42', 'annee_ouverture': 1985, 'ouvreur': 'Dupont',
        'reequipements': [{'nom': 'Club', 'annee': 2010}, {'nom': '', 'annee': ''}],
        'tags': {'roche': ['Calcaire'], 'fixation': ['Broches']}}


def test_update_roundtrip(conn, uid):
    a = add_ascension(conn, uid, type='voie', grimpe='tete')
    infos.update_infos(conn, uid, a, FULL)
    d = infos.get_infos(conn, uid, a)
    assert d['topo']['topo_nom'] == 'Guide Calanques' and d['topo']['topo_annee'] == 2019
    assert d['ouverture'] == {'annee': 1985, 'ouvreur': 'Dupont'}
    assert d['reequipements'] == [{'nom': 'Club', 'annee': 2010}]
    assert d['tags'] == {'grimpe': [], 'roche': ['Calcaire'], 'fixation': ['Broches']}


def test_update_pdf_topo_clears_paper_fields(conn, uid):
    a = add_ascension(conn, uid)
    infos.update_infos(conn, uid, a, FULL)
    infos.update_infos(conn, uid, a, {'topo_type': 'pdf', 'topo_nom': 'N', 'topo_lien': 'exemple.fr/t.pdf', 'topo_page': '9'})
    t = infos.get_infos(conn, uid, a)['topo']
    assert t['topo_lien'] == 'https://exemple.fr/t.pdf' and t['topo_page'] is None and t['topo_edition'] is None


def test_update_without_topo_type_clears_topo(conn, uid):
    a = add_ascension(conn, uid)
    infos.update_infos(conn, uid, a, FULL)
    infos.update_infos(conn, uid, a, {})
    assert infos.get_infos(conn, uid, a)['topo']['topo_type'] is None


def test_update_reequipements_none_keeps_existing(conn, uid):
    a = add_ascension(conn, uid)
    infos.update_infos(conn, uid, a, FULL)
    infos.update_infos(conn, uid, a, {'topo_type': None})
    assert len(infos.get_reequipements(conn, a)) == 1
    infos.update_infos(conn, uid, a, {'reequipements': []})
    assert infos.get_reequipements(conn, a) == []


def test_update_ignores_tag_categories_not_allowed_for_type(conn, uid):
    a = add_ascension(conn, uid, type='bloc')
    infos.update_infos(conn, uid, a, {'tags': {'fixation': ['Spits'], 'roche': ['Grès']}})
    assert scalar(conn, "SELECT COUNT(*) FROM ascension_tag WHERE ascension_id=? AND categorie='fixation'", a) == 0
    assert infos.get_infos(conn, uid, a)['tags']['roche'] == ['Grès']


def test_update_validation_error_leaves_data_untouched(conn, uid):
    a = add_ascension(conn, uid)
    infos.update_infos(conn, uid, a, FULL)
    with pytest.raises(ValidationError):
        infos.update_infos(conn, uid, a, {'topo_type': 'inconnu'})
    assert infos.get_infos(conn, uid, a)['topo']['topo_nom'] == 'Guide Calanques'


def test_update_not_found(conn, uid, uid2):
    a = add_ascension(conn, uid)
    with pytest.raises(NotFoundError):
        infos.update_infos(conn, uid2, a, {})
    assert infos.get_infos(conn, uid, a)['topo']['topo_type'] is None


def test_known_names(conn, uid, uid2):
    a = add_ascension(conn, uid, 'Zèbre', place={'sous_secteur': 'Face Nord'})
    add_ascension(conn, uid, 'alpha')
    add_ascension(conn, uid2, 'Autre compte', place={'pays': 'Italie'})
    infos.update_infos(conn, uid, a, {'topo_type': 'papier', 'topo_nom': 'Topo Z', 'ouvreur': 'Bob',
                                      'reequipements': [{'nom': 'Alice', 'annee': 2000}]})
    k = infos.known_names(conn, uid)
    assert k['ascensions'] == ['alpha', 'Zèbre']
    assert k['ouvreurs'] == ['Alice', 'Bob'] and k['topos'] == ['Topo Z']
    assert {'France', 'Calanques', 'En-Vau', 'Face Nord', 'Marseille'} <= set(k['lieux'])
    assert 'Italie' not in k['lieux'] and 'Autre compte' not in k['ascensions']


def test_known_names_empty(conn, uid):
    assert infos.known_names(conn, uid) == {'ascensions': [], 'lieux': [], 'ouvreurs': [], 'topos': []}


def test_update_infos_saves_and_clears_the_chosen_topo_pdf(conn, uid, uid2):
    from src.services import topo_pdf
    a = add_ascension(conn, uid)
    mine, _ = topo_pdf.add_topo(conn, uid, 'mien.pdf', b'%PDF-1.4 a')
    foreign, _ = topo_pdf.add_topo(conn, uid2, 'leur.pdf', b'%PDF-1.4 b')
    infos.update_infos(conn, uid, a, {'topo_type': 'pdf', 'topo_id': mine['id']})
    assert infos.get_infos(conn, uid, a)['topo_pdf']['id'] == mine['id']
    with pytest.raises(ValidationError, match='Topo inconnu'):
        infos.update_infos(conn, uid, a, {'topo_type': 'pdf', 'topo_id': foreign['id']})
    assert infos.get_infos(conn, uid, a)['topo_pdf']['id'] == mine['id']          # rien n'a été écrit
    infos.update_infos(conn, uid, a, {'topo_type': 'pdf'})
    assert infos.get_infos(conn, uid, a)['topo_pdf'] is None
