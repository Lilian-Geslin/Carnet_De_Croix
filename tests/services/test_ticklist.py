"""src/services/ticklist.py."""
import pytest

from src.errors import NotFoundError, ValidationError
from src.services import ticklist
from tests.helpers import add_ascension, scalar


def envie(conn, uid, **kw):
    return add_ascension(conn, uid, statut='ticklist', **{'nom': 'Envie', **kw})


def test_list_only_ticklist_of_user(conn, uid, uid2):
    envie(conn, uid)
    add_ascension(conn, uid, 'Log')
    add_ascension(conn, uid, 'Proj', statut='projet')
    envie(conn, uid2, nom='Autre')
    assert [e['nom'] for e in ticklist.list_envies(conn, uid)] == ['Envie']


def test_list_sorted_case_insensitive(conn, uid):
    for n in ('zèbre', 'Alpha', 'beta'):
        envie(conn, uid, nom=n)
    assert [e['nom'] for e in ticklist.list_envies(conn, uid)] == ['Alpha', 'beta', 'zèbre']


def test_fields_of_an_envie(conn, uid):
    envie(conn, uid, nom='E', cotation='7a', hauteur=12, commentaire='beau', type_depart='assis',
          envie_categorie='performance', place={'sous_secteur': 'Nord'})
    e = ticklist.list_envies(conn, uid)[0]
    assert (e['type'], e['type_label'], e['cotation'], e['hauteur'], e['commentaire'], e['categorie']) == (
        'bloc', 'Bloc', '7a', 12, 'beau', 'performance')
    assert e['chemin'] == 'France › Bouches-du-Rhône › Marseille › Calanques'
    assert (e['site'], e['secteur'], e['sous_secteur']) == ('Calanques', 'En-Vau', 'Nord')
    assert e['depart'] and e['palier'] is not None


def test_invalid_stored_category_is_blank(conn, uid):
    a = envie(conn, uid)
    conn.execute("UPDATE ascension SET envie_categorie='bidon' WHERE id=?", (a,))
    assert ticklist.list_envies(conn, uid)[0]['categorie'] == ''


def test_grande_voie_cotation_text_with_alpine(conn, uid):
    envie(conn, uid, type='grande_voie', cotation='5c', cotation_haute='6c')
    text = ticklist.list_envies(conn, uid)[0]['cotation']
    assert text.startswith('5c → 6c (') and text.endswith(')')


def test_grande_voie_without_low_grade(conn, uid):
    envie(conn, uid, type='grande_voie', cotation=None, cotation_haute='6c')
    assert ticklist.list_envies(conn, uid)[0]['cotation'].startswith('6c (')


def test_grande_voie_without_high_grade_shows_base_grade(conn, uid):
    envie(conn, uid, type='grande_voie', cotation='5c')
    assert ticklist.list_envies(conn, uid)[0]['cotation'] == '5c'


def test_missing_cotation_is_empty_text_and_negative_rank(conn, uid):
    envie(conn, uid, cotation=None)
    e = ticklist.list_envies(conn, uid)[0]
    assert e['cotation'] == '' and e['rank'] < 0 and e['above_max'] is None


def test_above_max_compares_within_the_same_discipline(conn, uid):
    add_ascension(conn, uid, 'Fait', cotation='6b')
    envie(conn, uid, nom='Plus dur', cotation='7a')
    envie(conn, uid, nom='Moins dur', cotation='6a')
    envie(conn, uid, nom='Egal', cotation='6b')
    envie(conn, uid, nom='Voie', type='voie', cotation='9a')       # aucune voie réalisée
    got = {e['nom']: e['above_max'] for e in ticklist.list_envies(conn, uid)}
    assert got == {'Plus dur': True, 'Moins dur': False, 'Egal': False, 'Voie': None}


def test_above_max_ignores_projects_and_other_users(conn, uid, uid2):
    add_ascension(conn, uid, 'Proj', statut='projet', cotation='8a')
    add_ascension(conn, uid2, 'Autre', cotation='8a')
    envie(conn, uid, cotation='6a')
    assert ticklist.list_envies(conn, uid)[0]['above_max'] is None


def test_above_max_uses_high_grade_of_big_walls(conn, uid):
    add_ascension(conn, uid, 'GV faite', type='grande_voie', cotation='5a', cotation_haute='6a')
    envie(conn, uid, nom='GV envie', type='grande_voie', cotation='5a', cotation_haute='6c')
    assert ticklist.list_envies(conn, uid)[0]['above_max'] is True


# ─── Catégorie ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize('cat', ['performance', 'beaute', 'majeure', None])
def test_set_categorie(conn, uid, cat):
    a = envie(conn, uid, envie_categorie='beaute')
    ticklist.set_categorie(conn, uid, a, cat)
    assert scalar(conn, 'SELECT envie_categorie FROM ascension WHERE id=?', a) == cat


def test_set_categorie_invalid(conn, uid):
    a = envie(conn, uid)
    with pytest.raises(ValidationError):
        ticklist.set_categorie(conn, uid, a, 'inconnue')


def test_set_categorie_not_found_cases(conn, uid, uid2):
    a = envie(conn, uid)
    log = add_ascension(conn, uid, 'Log')
    for who, target in ((uid2, a), (uid, log), (uid, 9999)):
        with pytest.raises(NotFoundError):
            ticklist.set_categorie(conn, who, target, 'beaute')
