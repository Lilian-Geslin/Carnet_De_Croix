"""src/services/seances.py (la validation pure est dans tests/unit)."""
from src.services import seances as svc
from tests.helpers import add_ascension, scalar


def add_seance(conn, asc, numero, nb, date='2026-02-01'):
    return conn.execute('INSERT INTO seance(ascension_id, numero, date, nb_essais) VALUES(?,?,?,?)',
                        (asc, numero, date, nb)).lastrowid


def test_next_numero_starts_at_one_and_follows_max(conn, uid):
    a = add_ascension(conn, uid, statut='projet')
    assert svc.next_seance_numero(conn, a) == 1
    add_seance(conn, a, 1, 2)
    add_seance(conn, a, 5, 2)
    assert svc.next_seance_numero(conn, a) == 6


def test_sync_essais_is_sum_of_seances(conn, uid):
    a = add_ascension(conn, uid, statut='projet')
    add_seance(conn, a, 1, 3)
    add_seance(conn, a, 2, 4)
    svc.sync_essais_projet(conn, a)
    assert scalar(conn, 'SELECT nb_essais_projet FROM ascension WHERE id=?', a) == 7


def test_sync_essais_zero_without_seance(conn, uid):
    a = add_ascension(conn, uid, statut='projet')
    conn.execute('UPDATE ascension SET nb_essais_projet=9 WHERE id=?', (a,))
    svc.sync_essais_projet(conn, a)
    assert scalar(conn, 'SELECT nb_essais_projet FROM ascension WHERE id=?', a) == 0


def test_list_seances_ordered_with_formatted_date(conn, uid):
    a = add_ascension(conn, uid, statut='projet')
    add_seance(conn, a, 2, 1, '2026-03-02')
    add_seance(conn, a, 1, 1, None)
    out = svc.list_seances(conn, a)
    assert [s['numero'] for s in out] == [1, 2]
    assert out[1]['date_fmt'] == '02/03/2026' and not out[0]['date_fmt']


def test_total_essais_handles_none():
    assert svc.total_essais([{'nb_essais': 2}, {'nb_essais': None}, {'nb_essais': 5}]) == 7
    assert svc.total_essais([]) == 0


def test_get_seance_owned(conn, uid, uid2):
    a = add_ascension(conn, uid, statut='projet')
    s = add_seance(conn, a, 1, 2)
    assert svc.get_seance_owned(conn, s, uid)['id'] == s
    assert svc.get_seance_owned(conn, s, uid2) is None
    assert svc.get_seance_owned(conn, 9999, uid) is None


def test_delete_seance_renumbers_and_resyncs(conn, uid):
    a = add_ascension(conn, uid, statut='projet')
    s1, s2, s3 = add_seance(conn, a, 1, 1), add_seance(conn, a, 2, 2), add_seance(conn, a, 3, 4)
    svc.sync_essais_projet(conn, a)
    svc.delete_seance(conn, svc.get_seance_owned(conn, s2, uid))
    rows = conn.execute('SELECT id, numero FROM seance WHERE ascension_id=? ORDER BY numero', (a,)).fetchall()
    assert [tuple(r) for r in rows] == [(s1, 1), (s3, 2)]
    assert scalar(conn, 'SELECT nb_essais_projet FROM ascension WHERE id=?', a) == 5


def test_delete_last_seance_leaves_zero_attempts(conn, uid):
    a = add_ascension(conn, uid, statut='projet', nb_essais_projet=3)
    s = svc.get_seance_owned(conn, scalar(conn, 'SELECT id FROM seance WHERE ascension_id=?', a), uid)
    svc.delete_seance(conn, s)
    assert scalar(conn, 'SELECT nb_essais_projet FROM ascension WHERE id=?', a) == 0
