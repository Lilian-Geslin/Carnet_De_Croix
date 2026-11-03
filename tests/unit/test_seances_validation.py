"""src/services/seances.py : validation des saisies (sans base)."""
import pytest

from src.services.seances import clean_iso_date, parse_seance_payload, total_essais


@pytest.mark.parametrize('raw, expected', [
    ('2026-01-31', '2026-01-31'), ('  2026-01-31 ', '2026-01-31'),
    ('2026-02-30', None), ('31/01/2026', None), ('', None), (None, None), (20260131, None), ('abc', None),
])
def test_clean_iso_date(raw, expected):
    assert clean_iso_date(raw) == expected


def test_parse_complete_payload():
    fields, err = parse_seance_payload({'date': '2026-03-01', 'nb_essais': 4, 'commentaire': '  bien  '})
    assert err is None
    assert fields == {'date': '2026-03-01', 'nb_essais': 4, 'commentaire': 'bien'}


def test_parse_accepts_numeric_string_essais_and_empty_comment():
    fields, _ = parse_seance_payload({'date': '2026-03-01', 'nb_essais': '12', 'commentaire': '   '})
    assert fields['nb_essais'] == 12 and fields['commentaire'] is None


@pytest.mark.parametrize('payload, message', [
    ({'nb_essais': 3}, 'La date de la séance est requise.'),
    ({'date': '', 'nb_essais': 3}, 'La date de la séance est requise.'),
    ({'date': '2026-13-01', 'nb_essais': 3}, 'Date invalide.'),
    ({'date': 'hier', 'nb_essais': 3}, 'Date invalide.'),
    ({'date': '2026-03-01'}, "Nombre d'essais invalide."),
    ({'date': '2026-03-01', 'nb_essais': 'x'}, "Nombre d'essais invalide."),
    ({'date': '2026-03-01', 'nb_essais': 0}, "Le nombre d'essais doit être compris entre 1 et 999."),
    ({'date': '2026-03-01', 'nb_essais': 1000}, "Le nombre d'essais doit être compris entre 1 et 999."),
    ({'date': '2026-03-01', 'nb_essais': 2, 'commentaire': 'x' * 5001}, 'Le commentaire est trop long (5000 caractères maximum).'),
])
def test_parse_rejects_invalid_payloads(payload, message):
    fields, err = parse_seance_payload(payload)
    assert fields is None and err == message


def test_parse_bounds_are_accepted():
    for n in (1, 999):
        assert parse_seance_payload({'date': '2026-03-01', 'nb_essais': n})[1] is None
    assert parse_seance_payload({'date': '2026-03-01', 'nb_essais': 1, 'commentaire': 'x' * 5000})[1] is None


def test_parse_non_string_comment_becomes_none():
    fields, _ = parse_seance_payload({'date': '2026-03-01', 'nb_essais': 1, 'commentaire': 42})
    assert fields['commentaire'] is None


def test_partial_only_reads_given_fields():
    assert parse_seance_payload({}, partial=True) == ({}, None)
    assert parse_seance_payload({'nb_essais': 5}, partial=True) == ({'nb_essais': 5}, None)
    assert parse_seance_payload({'commentaire': 'ok'}, partial=True) == ({'commentaire': 'ok'}, None)


def test_partial_empty_date_clears_it():
    assert parse_seance_payload({'date': ''}, partial=True) == ({'date': None}, None)
    assert parse_seance_payload({'date': None}, partial=True) == ({'date': None}, None)


def test_partial_still_validates_given_fields():
    assert parse_seance_payload({'date': 'bad'}, partial=True)[1] == 'Date invalide.'
    assert parse_seance_payload({'nb_essais': 0}, partial=True)[1] == "Le nombre d'essais doit être compris entre 1 et 999."


def test_total_essais_ignores_missing_values():
    assert total_essais([{'nb_essais': 2}, {'nb_essais': None}, {'nb_essais': 3}]) == 5
    assert total_essais([]) == 0
