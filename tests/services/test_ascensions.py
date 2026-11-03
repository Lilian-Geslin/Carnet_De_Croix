"""src/services/ascensions.py : doublons, création, mise à jour, suppression, détail."""
import pytest

from src.services import ascensions as svc
from src.services import geo
from tests.helpers import DEFAULT_PLACE, add_ascension, scalar


def sector(conn, uid, **place):
    return geo.resolve_location(conn, uid, {**DEFAULT_PLACE, **place})


# ─── Propriété ───────────────────────────────────────────────────────────────

def test_ascension_owned(conn, uid, uid2):
    a = add_ascension(conn, uid)
    assert svc.ascension_owned(conn, a, uid) is True
    assert svc.ascension_owned(conn, a, uid2) is False
    assert svc.ascension_owned(conn, 9999, uid) is False


# ─── Doublons ────────────────────────────────────────────────────────────────

def dup(conn, uid, sec=None, ss=None, **data):
    if sec is None:
        sec, ss = sector(conn, uid)
    return svc.find_duplicate(conn, uid, sec, ss, {'type': 'bloc', 'nom': 'Bloc A', 'cotation': '6a', **data})


def test_duplicate_found_on_identical_identity(conn, uid):
    a = add_ascension(conn, uid)
    assert dup(conn, uid)['id'] == a


def test_duplicate_ignores_case_accents_and_spaces(conn, uid):
    a = add_ascension(conn, uid, 'Élégance du Mur')
    assert dup(conn, uid, nom='  elegance  DU mur ')['id'] == a


@pytest.mark.parametrize('change', [
    {'nom': 'Autre'}, {'cotation': '6b'}, {'cotation_haute': '6c'}, {'nb_longueurs': 3},
    {'type_depart': 'assis'}, {'type_arrivee': 'dalle'}, {'type': 'voie'},
])
def test_duplicate_not_found_when_one_criterion_differs(conn, uid, change):
    add_ascension(conn, uid)
    assert dup(conn, uid, **change) is None


@pytest.mark.parametrize('ignored', [
    {'cotation_perso': '6b'}, {'style': 'flash'}, {'date': '2020-01-01'}, {'pieds_nus': True},
    {'hauteur': 9}, {'note_beaute': 3}, {'commentaire': 'x'}, {'grimpe': 'tete'},
])
def test_duplicate_ignores_non_identity_fields(conn, uid, ignored):
    a = add_ascension(conn, uid)
    assert dup(conn, uid, **ignored)['id'] == a


def test_duplicate_default_depart_arrivee_is_normal(conn, uid):
    a = add_ascension(conn, uid, type_depart='normal', type_arrivee=None)
    assert dup(conn, uid, type_depart=None, type_arrivee='normal')['id'] == a


def test_duplicate_is_scoped_to_sector_and_sous_secteur(conn, uid):
    add_ascension(conn, uid, place={'sous_secteur': 'Face Nord'})
    sec, ss = sector(conn, uid, sous_secteur='Face Nord')
    assert svc.find_duplicate(conn, uid, sec, ss, {'type': 'bloc', 'nom': 'Bloc A', 'cotation': '6a'}) is not None
    assert svc.find_duplicate(conn, uid, sec, None, {'type': 'bloc', 'nom': 'Bloc A', 'cotation': '6a'}) is None
    sec2, ss2 = sector(conn, uid, secteur='Ailleurs')
    assert svc.find_duplicate(conn, uid, sec2, ss2, {'type': 'bloc', 'nom': 'Bloc A', 'cotation': '6a'}) is None


def test_duplicate_is_scoped_to_user(conn, uid, uid2):
    add_ascension(conn, uid2)
    assert dup(conn, uid) is None


def test_duplicate_priority_log_then_projet_then_ticklist(conn, uid):
    t = add_ascension(conn, uid, statut='ticklist')
    assert dup(conn, uid)['id'] == t
    p = add_ascension(conn, uid, statut='projet')
    assert dup(conn, uid)['id'] == p
    l = add_ascension(conn, uid, statut='log')
    assert dup(conn, uid)['id'] == l


# ─── Création ────────────────────────────────────────────────────────────────

def test_insert_log_basic_fields(conn, uid):
    sec, ss = sector(conn, uid)
    a = svc.insert_ascension(conn, uid, sec, ss, {'type': 'voie', 'nom': 'V', 'cotation': '6b', 'date': '2026-03-01',
                                                  'pieds_nus': True, 'hauteur': 20, 'note_beaute': 3, 'grimpe': 'tete'})
    r = conn.execute('SELECT * FROM ascension WHERE id=?', (a,)).fetchone()
    assert (r['statut'], r['nom'], r['cotation'], r['pieds_nus'], r['hauteur'], r['grimpe']) == ('log', 'V', '6b', 1, 20, 'tete')
    assert r['nb_essais_projet'] == 0 and r['user_id'] == uid


def test_insert_pieds_nus_falsy_is_zero(conn, uid):
    a = add_ascension(conn, uid, pieds_nus=False)
    assert scalar(conn, 'SELECT pieds_nus FROM ascension WHERE id=?', a) == 0


def test_insert_projet_with_attempts_creates_seance_one(conn, uid):
    a = add_ascension(conn, uid, statut='projet', nb_essais_projet=5, date_seance='2026-02-02')
    s = conn.execute('SELECT numero, date, nb_essais FROM seance WHERE ascension_id=?', (a,)).fetchall()
    assert [tuple(x) for x in s] == [(1, '2026-02-02', 5)]
    assert scalar(conn, 'SELECT nb_essais_projet FROM ascension WHERE id=?', a) == 5


@pytest.mark.parametrize('raw, expected', [(0, None), (None, None), ('abc', None), (-4, None), (5000, 999), ('7', 7)])
def test_insert_projet_attempts_are_clamped(conn, uid, raw, expected):
    a = add_ascension(conn, uid, statut='projet', nb_essais_projet=raw)
    n = scalar(conn, 'SELECT nb_essais FROM seance WHERE ascension_id=?', a) if conn.execute(
        'SELECT 1 FROM seance WHERE ascension_id=?', (a,)).fetchone() else None
    assert n == expected


def test_insert_projet_invalid_seance_date_is_null(conn, uid):
    a = add_ascension(conn, uid, statut='projet', nb_essais_projet=3, date_seance='31/12/2026')
    assert scalar(conn, 'SELECT date FROM seance WHERE ascension_id=?', a) is None


def test_insert_log_never_creates_seance(conn, uid):
    a = add_ascension(conn, uid, nb_essais_projet=4)
    assert scalar(conn, 'SELECT COUNT(*) FROM seance WHERE ascension_id=?', a) == 0


def test_envie_categorie_only_for_ticklist_and_valid(conn, uid):
    ok = add_ascension(conn, uid, 'Envie', statut='ticklist', envie_categorie='beaute')
    bad = add_ascension(conn, uid, 'Envie2', statut='ticklist', envie_categorie='inconnue')
    log = add_ascension(conn, uid, 'Log', envie_categorie='beaute')
    get = lambda i: scalar(conn, 'SELECT envie_categorie FROM ascension WHERE id=?', i)
    assert (get(ok), get(bad), get(log)) == ('beaute', None, None)


def test_insert_grande_voie_saves_numbered_longueurs(conn, uid):
    a = add_ascension(conn, uid, 'GV', type='grande_voie', cotation='5c', cotation_haute='6b', nb_longueurs=2,
                      longueurs=[{'cotation': '5c', 'style': 'a_vue', 'pieds_nus': True, 'hauteur': 30},
                                 {'cotation': '6b', 'cotation_perso': '6a+', 'grimpe': 'moulinette'}])
    rows = conn.execute('SELECT numero, cotation, cotation_perso, pieds_nus, hauteur, grimpe FROM longueur '
                        'WHERE ascension_id=? ORDER BY numero', (a,)).fetchall()
    assert [tuple(r) for r in rows] == [(1, '5c', None, 1, 30, None), (2, '6b', '6a+', 0, None, 'moulinette')]


def test_insert_longueurs_ignored_for_non_gv(conn, uid):
    a = add_ascension(conn, uid, type='voie', longueurs=[{'cotation': '6a'}])
    assert scalar(conn, 'SELECT COUNT(*) FROM longueur WHERE ascension_id=?', a) == 0


# ─── Mise à jour ─────────────────────────────────────────────────────────────

def test_update_changes_fields_and_location(conn, uid):
    a = add_ascension(conn, uid)
    sec, ss = sector(conn, uid, secteur='Nouveau')
    svc.update_ascension(conn, uid, a, sec, ss, {'type': 'bloc', 'nom': 'Renommé', 'cotation': '7a', 'style': 'flash',
                                                 'pieds_nus': True, 'date': '2026-05-05', 'commentaire': 'ok'})
    r = conn.execute('SELECT * FROM ascension WHERE id=?', (a,)).fetchone()
    assert (r['nom'], r['cotation'], r['style'], r['pieds_nus'], r['date'], r['secteur_id']) == (
        'Renommé', '7a', 'flash', 1, '2026-05-05', sec)
    assert (r['statut'], r['type']) == ('log', 'bloc')    # statut et type ne changent pas


def test_update_does_not_touch_other_users_ascension(conn, uid, uid2):
    a = add_ascension(conn, uid)
    sec, ss = sector(conn, uid2)
    svc.update_ascension(conn, uid2, a, sec, ss, {'type': 'bloc', 'nom': 'Piraté'})
    assert scalar(conn, 'SELECT nom FROM ascension WHERE id=?', a) == 'Bloc A'


def test_update_replaces_longueurs_for_gv(conn, uid):
    a = add_ascension(conn, uid, type='grande_voie', cotation='5a', cotation_haute='6a',
                      longueurs=[{'cotation': '5a'}, {'cotation': '5c'}, {'cotation': '6a'}])
    sec, ss = sector(conn, uid)
    svc.update_ascension(conn, uid, a, sec, ss, {'type': 'grande_voie', 'nom': 'GV', 'longueurs': [{'cotation': '6b'}]})
    assert [r[0] for r in conn.execute('SELECT cotation FROM longueur WHERE ascension_id=?', (a,))] == ['6b']


def test_update_keeps_longueurs_when_key_absent(conn, uid):
    a = add_ascension(conn, uid, type='grande_voie', cotation='5a', cotation_haute='6a', longueurs=[{'cotation': '5a'}])
    sec, ss = sector(conn, uid)
    svc.update_ascension(conn, uid, a, sec, ss, {'type': 'grande_voie', 'nom': 'GV'})
    assert scalar(conn, 'SELECT COUNT(*) FROM longueur WHERE ascension_id=?', a) == 1


# ─── Suppression ─────────────────────────────────────────────────────────────

def test_delete_ascensions_removes_dependents(conn, uid):
    a, b = add_ascension(conn, uid, 'A'), add_ascension(conn, uid, 'B')
    for x in (a, b):
        conn.execute("INSERT INTO repetition(ascension_id,date) VALUES(?, '2026-01-01')", (x,))
        conn.execute("INSERT INTO seance(ascension_id,numero,nb_essais) VALUES(?,1,1)", (x,))
        conn.execute("INSERT INTO longueur(ascension_id,numero) VALUES(?,1)", (x,))
        conn.execute("INSERT INTO ascension_tag(ascension_id,categorie,nom) VALUES(?,'roche','Grès')", (x,))
        conn.execute("INSERT INTO reequipement(ascension_id,nom) VALUES(?,'P')", (x,))
    svc.delete_ascensions(conn, [a])
    for t in ('ascension', 'repetition', 'seance', 'longueur', 'ascension_tag', 'reequipement'):
        assert scalar(conn, f'SELECT COUNT(*) FROM {t}') == 1, t


def test_delete_ascensions_empty_list_is_noop(conn, uid):
    add_ascension(conn, uid)
    svc.delete_ascensions(conn, [])
    assert scalar(conn, 'SELECT COUNT(*) FROM ascension') == 1


# ─── Détail ──────────────────────────────────────────────────────────────────

def test_detail_contains_full_location(conn, uid):
    a = add_ascension(conn, uid)
    d = svc.get_ascension_detail(conn, a, uid)['ascension']
    assert (d['pays_name'], d['departement_name'], d['localisation_name'], d['site_name'], d['secteur_name']) == (
        'France', 'Bouches-du-Rhône', 'Marseille', 'Calanques', 'En-Vau')
    assert d['sous_secteur_name'] is None and d['ressenti'] is None


def test_detail_ressenti_comes_from_sous_secteur_when_present(conn, uid):
    sec, ss = sector(conn, uid, sous_secteur='Face Nord')
    geo.apply_ressenti(conn, {'ressenti': 'dur'}, sec, ss)
    a = add_ascension(conn, uid, place={'sous_secteur': 'Face Nord'})
    d = svc.get_ascension_detail(conn, a, uid)['ascension']
    assert d['sous_secteur_name'] == 'Face Nord' and d['ressenti'] == 'dur'


def test_detail_ressenti_from_secteur_without_sous_secteur(conn, uid):
    sec, ss = sector(conn, uid)
    geo.apply_ressenti(conn, {'ressenti': 'facile'}, sec, None)
    a = add_ascension(conn, uid)
    assert svc.get_ascension_detail(conn, a, uid)['ascension']['ressenti'] == 'facile'


def test_detail_includes_ordered_longueurs(conn, uid):
    a = add_ascension(conn, uid, type='grande_voie', cotation='5a', cotation_haute='6a',
                      longueurs=[{'cotation': '5a'}, {'cotation': '6a'}])
    assert [l['numero'] for l in svc.get_ascension_detail(conn, a, uid)['longueurs']] == [1, 2]


def test_detail_none_for_foreign_or_unknown(conn, uid, uid2):
    a = add_ascension(conn, uid)
    assert svc.get_ascension_detail(conn, a, uid2) is None
    assert svc.get_ascension_detail(conn, 9999, uid) is None
