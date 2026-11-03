"""src/services/infos.py : validation de topo, ouverture, liens et rééquipements (sans base)."""
from datetime import date

import pytest

from src.errors import ValidationError
from src.services.infos import _clean_link, _clean_text, _clean_year, clean_reequipements, parse_infos_payload

NEXT_YEAR = date.today().year + 1


# ─── Texte, année, lien ──────────────────────────────────────────────────────

def test_clean_text():
    assert _clean_text(None, 10) == (None, None)
    assert _clean_text('  abc ', 10) == ('abc', None)
    assert _clean_text('   ', 10) == (None, None)
    assert _clean_text(12, 10)[1] == 'Texte invalide.'
    assert _clean_text('x' * 11, 10)[1] == 'Texte trop long (10 caractères maximum).'
    assert _clean_text('x' * 10, 10) == ('x' * 10, None)


@pytest.mark.parametrize('raw, expected', [
    (None, None), ('', None), ('  ', None), ('1998', 1998), (1998, 1998), (1800, 1800), (NEXT_YEAR, NEXT_YEAR),
])
def test_clean_year_valid(raw, expected):
    assert _clean_year(raw, 'Année') == (expected, None)


@pytest.mark.parametrize('raw', ['abc', 1799, NEXT_YEAR + 1, '12,5', [], '1e3x'])
def test_clean_year_invalid(raw):
    value, err = _clean_year(raw, 'Année')
    assert value is None and err.startswith('Année : année invalide')


@pytest.mark.parametrize('raw, expected', [
    ('https://exemple.fr/topo.pdf', 'https://exemple.fr/topo.pdf'),
    ('HTTP://Exemple.fr', 'HTTP://Exemple.fr'),
    ('exemple.fr/topo.pdf', 'https://exemple.fr/topo.pdf'),
    ('site.fr:8080/topo', 'https://site.fr:8080/topo'),
    ('  https://a.fr  ', 'https://a.fr'),
    (None, None), ('', None),
])
def test_clean_link_accepted(raw, expected):
    assert _clean_link(raw) == (expected, None)


@pytest.mark.parametrize('raw', ['javascript:alert(1)', 'data:text/html,x', 'file:///etc/passwd', 'mailto:a@b.fr', 'ftp://a.fr'])
def test_clean_link_refuses_other_schemes(raw):
    value, err = _clean_link(raw)
    assert value is None and err == 'Le lien doit commencer par http:// ou https://.'


def test_clean_link_refuses_spaces_and_too_long():
    assert _clean_link('https://a.fr/un topo')[1] == "Le lien ne doit pas contenir d'espace."
    assert 'trop long' in _clean_link('https://a.fr/' + 'x' * 500)[1]


# ─── Rééquipements ───────────────────────────────────────────────────────────

def test_reequipements_absent_means_untouched():
    assert clean_reequipements(None) == (None, None)


def test_reequipements_keep_order_and_skip_empty_lines():
    raw = [{'nom': 'Pierre', 'annee': '2015'}, {'nom': '', 'annee': ''}, {'nom': None, 'annee': 2020}, {'nom': ' Paul '}]
    assert clean_reequipements(raw) == ([('Pierre', 2015), (None, 2020), ('Paul', None)], None)


@pytest.mark.parametrize('raw', ['pas une liste', [1], [['x']], [{'nom': 'a'}] * 21])
def test_reequipements_invalid_structure(raw):
    value, err = clean_reequipements(raw)
    assert value is False and err


def test_reequipements_invalid_content():
    assert clean_reequipements([{'nom': 'x' * 101}])[1].startswith('Rééquipé par : ')
    assert 'Année de rééquipement' in clean_reequipements([{'nom': 'a', 'annee': 'zz'}])[1]


def test_reequipements_max_is_accepted():
    value, err = clean_reequipements([{'nom': f'n{i}'} for i in range(20)])
    assert err is None and len(value) == 20


# ─── Payload complet ─────────────────────────────────────────────────────────

def test_payload_empty_gives_empty_fields():
    fields, reeq = parse_infos_payload({})
    assert all(v is None for v in fields.values()) and reeq is None


def test_payload_paper_topo():
    fields, _ = parse_infos_payload({'topo_type': 'papier', 'topo_nom': 'Escalade en Provence', 'topo_edition': '2e',
                                     'topo_annee': '2019', 'topo_page': '42', 'topo_lien': 'https://ignore.fr',
                                     'annee_ouverture': 1985, 'ouvreur': 'Jean'})
    assert fields['topo_type'] == 'papier' and fields['topo_nom'] == 'Escalade en Provence'
    assert fields['topo_edition'] == '2e' and fields['topo_annee'] == 2019 and fields['topo_page'] == '42'
    assert fields['topo_lien'] is None          # champ de l'autre type : effacé
    assert fields['annee_ouverture'] == 1985 and fields['ouvreur'] == 'Jean'


def test_payload_pdf_topo_clears_paper_fields():
    fields, _ = parse_infos_payload({'topo_type': 'pdf', 'topo_nom': 'Topo', 'topo_lien': 'exemple.fr/t.pdf',
                                     'topo_edition': 'ignoré', 'topo_page': '3'})
    assert fields['topo_lien'] == 'https://exemple.fr/t.pdf'
    assert fields['topo_edition'] is None and fields['topo_page'] is None and fields['topo_annee'] is None


def test_payload_without_topo_type_ignores_topo_fields():
    fields, _ = parse_infos_payload({'topo_nom': 'Topo', 'topo_lien': 'https://a.fr'})
    assert fields['topo_type'] is None and fields['topo_nom'] is None and fields['topo_lien'] is None


def test_payload_invalid_topo_type():
    with pytest.raises(ValidationError, match='Type de topo invalide.'):
        parse_infos_payload({'topo_type': 'video'})


@pytest.mark.parametrize('payload, fragment', [
    ({'annee_ouverture': 'abc'}, "Année d'ouverture"),
    ({'topo_type': 'papier', 'topo_annee': 3000}, 'Année de publication'),
    ({'topo_type': 'pdf', 'topo_lien': 'javascript:alert(1)'}, 'http'),
    ({'ouvreur': 'x' * 101}, 'trop long'),
    ({'reequipements': 'non'}, 'Rééquipements'),
])
def test_payload_errors(payload, fragment):
    with pytest.raises(ValidationError) as exc:
        parse_infos_payload(payload)
    assert fragment in exc.value.message


# ─── Topo PDF choisi dans la bibliothèque ────────────────────────────────────

@pytest.mark.parametrize('raw, expected', [(None, None), ('', None), (3, 3)])
def test_clean_topo_id_accepts(raw, expected):
    from src.services.infos import _clean_topo_id
    assert _clean_topo_id(raw) == (expected, None)


@pytest.mark.parametrize('raw', [0, -1, 'abc', 2.5, True, [1]])
def test_clean_topo_id_rejects(raw):
    from src.services.infos import _clean_topo_id
    assert _clean_topo_id(raw) == (None, 'Topo invalide.')


def test_payload_pdf_keeps_topo_id_but_paper_drops_it():
    fields, _ = parse_infos_payload({'topo_type': 'pdf', 'topo_id': 7, 'topo_lien': 'https://a.fr'})
    assert fields['topo_id'] == 7
    fields, _ = parse_infos_payload({'topo_type': 'papier', 'topo_nom': 'Guide', 'topo_id': 7})
    assert fields['topo_id'] is None
    fields, _ = parse_infos_payload({'topo_id': 7})
    assert fields['topo_id'] is None
