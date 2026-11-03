"""src/services/export_csv.py et export_pdf.py."""
import csv
import io
import zipfile

from src.services import export_csv, export_pdf, tags
from tests.helpers import add_ascension


def read_zip(buf):
    z = zipfile.ZipFile(buf)
    out = {}
    for name in z.namelist():
        out[name] = list(csv.DictReader(io.StringIO(z.read(name).decode('utf-8'))))
    return z.namelist(), out


# ─── CSV ─────────────────────────────────────────────────────────────────────

def test_zip_contains_four_csv_files_even_when_empty(conn, uid):
    files, data = read_zip(export_csv.build_export_zip(conn, uid))
    assert files == ['ascensions.csv', 'longueurs.csv', 'repetitions.csv', 'seances.csv']
    assert all(rows == [] for rows in data.values())


def test_headers_follow_declared_columns(conn, uid):
    z = zipfile.ZipFile(export_csv.build_export_zip(conn, uid))
    for name, cols in (('ascensions.csv', export_csv.ASCENSION_COLUMNS), ('longueurs.csv', export_csv.LONGUEUR_COLUMNS),
                       ('repetitions.csv', export_csv.REPETITION_COLUMNS), ('seances.csv', export_csv.SEANCE_COLUMNS)):
        assert z.read(name).decode().splitlines()[0].split(',') == cols


def test_ascension_row_content(conn, uid):
    add_ascension(conn, uid, 'Bloc é', cotation='6b', date='2026-02-02', commentaire='a, "b"', place={'sous_secteur': 'Nord'})
    _, data = read_zip(export_csv.build_export_zip(conn, uid))
    row = data['ascensions.csv'][0]
    assert (row['nom'], row['cotation'], row['statut'], row['date'], row['commentaire']) == ('Bloc é', '6b', 'log', '2026-02-02', 'a, "b"')
    assert (row['pays_name'], row['site_name'], row['secteur_name'], row['sous_secteur_name']) == ('France', 'Calanques', 'En-Vau', 'Nord')


def test_all_statuts_are_exported(conn, uid):
    add_ascension(conn, uid, 'L')
    add_ascension(conn, uid, 'P', statut='projet')
    add_ascension(conn, uid, 'T', statut='ticklist', envie_categorie='beaute')
    _, data = read_zip(export_csv.build_export_zip(conn, uid))
    assert {r['statut'] for r in data['ascensions.csv']} == {'log', 'projet', 'ticklist'}
    assert [r['envie_categorie'] for r in data['ascensions.csv'] if r['statut'] == 'ticklist'] == ['beaute']


def test_tags_and_reequipements_are_concatenated(conn, uid):
    a = add_ascension(conn, uid, 'V', type='voie', grimpe='tete')
    tags.replace_ascension_tags(conn, a, {'roche': ['Calcaire', 'Grès'], 'fixation': ['Spits'], 'grimpe': ['Dalle']})
    conn.execute("INSERT INTO reequipement(ascension_id, nom, annee, ordre) VALUES(?, 'Club', 2010, 0)", (a,))
    conn.execute("INSERT INTO reequipement(ascension_id, nom, annee, ordre) VALUES(?, 'Bob', NULL, 1)", (a,))
    conn.execute("INSERT INTO reequipement(ascension_id, nom, annee, ordre) VALUES(?, NULL, 1999, 2)", (a,))
    conn.commit()
    _, data = read_zip(export_csv.build_export_zip(conn, uid))
    row = data['ascensions.csv'][0]
    assert row['roche'] == 'Calcaire | Grès' and row['fixations'] == 'Spits' and row['type_grimpe'] == 'Dalle' and row['coinceurs'] == ''
    assert row['reequipements'] == 'Club (2010) | Bob | (1999)'


def test_children_files(conn, uid):
    a = add_ascension(conn, uid, 'GV', type='grande_voie', cotation='5a', cotation_haute='6a', grimpe='tete',
                      longueurs=[{'cotation': '5a'}, {'cotation': '6a'}])
    conn.execute("INSERT INTO repetition(ascension_id, date, nb_essais) VALUES(?, '2026-05-01', '2')", (a,))
    conn.execute("INSERT INTO seance(ascension_id, numero, date, nb_essais) VALUES(?, 1, '2026-01-01', 3)", (a,))
    conn.commit()
    _, data = read_zip(export_csv.build_export_zip(conn, uid))
    assert [(r['numero'], r['cotation'], r['ascension_nom']) for r in data['longueurs.csv']] == [('1', '5a', 'GV'), ('2', '6a', 'GV')]
    assert data['repetitions.csv'][0]['ascension_id'] == str(a) and data['repetitions.csv'][0]['date'] == '2026-05-01'
    assert data['seances.csv'][0]['nb_essais'] == '3'


def test_export_is_isolated_per_user(conn, uid, uid2):
    add_ascension(conn, uid2, 'Autre')
    _, data = read_zip(export_csv.build_export_zip(conn, uid))
    assert data['ascensions.csv'] == []


def test_rows_to_csv_missing_key_gives_empty_cell(conn, uid):
    add_ascension(conn, uid)
    rows = conn.execute('SELECT id FROM ascension').fetchall()
    out = export_csv._rows_to_csv(rows, ['id', 'inexistante'])
    assert out.splitlines()[1].endswith(',')


# ─── PDF ─────────────────────────────────────────────────────────────────────

def load(conn, uid):
    return export_pdf._load_data(conn, uid)


def test_pdf_is_a_pdf_even_when_empty(conn, uid):
    assert export_pdf.build_pdf(conn, uid, 'Lilian').read(5) == b'%PDF-'


def test_pdf_with_data_is_larger(conn, uid):
    empty = len(export_pdf.build_pdf(conn, uid, 'Lilian').getvalue())
    a = add_ascension(conn, uid, 'Élégance', hauteur=4)
    add_ascension(conn, uid, 'GV', type='grande_voie', cotation='5a', cotation_haute='6a', grimpe='tete')
    conn.execute("INSERT INTO repetition(ascension_id, date) VALUES(?, '2026-05-01')", (a,))
    conn.commit()
    assert len(export_pdf.build_pdf(conn, uid, 'Lilian').getvalue()) > empty


def test_load_data_only_logs_newest_first(conn, uid, uid2):
    add_ascension(conn, uid, 'Vieux', date='2025-01-01')
    add_ascension(conn, uid, 'Récent', date='2026-01-01')
    add_ascension(conn, uid, 'Projet', statut='projet')
    add_ascension(conn, uid2, 'Autre')
    ascs, reps = load(conn, uid)
    assert [a['nom'] for a in ascs] == ['Récent', 'Vieux'] and reps == []


def test_per_type_summary(conn, uid):
    a = add_ascension(conn, uid, 'A', cotation='6a', hauteur=4)
    add_ascension(conn, uid, 'B', cotation='7a', hauteur=6)
    add_ascension(conn, uid, 'GV', type='grande_voie', cotation='5a', cotation_haute='6c', grimpe='tete',
                  longueurs=[{'cotation': '5a', 'hauteur': 30}, {'cotation': '6c', 'hauteur': 20}])
    conn.execute("INSERT INTO repetition(ascension_id, date) VALUES(?, '2026-05-01')", (a,))
    conn.commit()
    per_type, cot_max, total = export_pdf._per_type_summary(conn, *load(conn, uid))
    assert per_type['bloc'] == {'nb': 2, 'metres': 14, 'cot_max': '7a'}
    assert per_type['grande_voie']['metres'] == 50 and per_type['grande_voie']['cot_max'] == '6c'
    assert per_type['voie']['nb'] == 0 and cot_max == '7a' and total == 64


def test_chronological_rows_merge_logs_and_repetitions(conn, uid):
    a = add_ascension(conn, uid, 'Bloc', cotation='6a', date='2026-01-10', place={'sous_secteur': 'Nord'})
    add_ascension(conn, uid, 'GV', type='grande_voie', cotation='5a', cotation_haute='6c', grimpe='tete', date='2026-03-01')
    conn.execute("INSERT INTO repetition(ascension_id, date, cotation_perso) VALUES(?, '2026-02-01', '6b')", (a,))
    conn.commit()
    rows = export_pdf._chronological_rows(*load(conn, uid))
    assert [(r['nom'], r['repetition']) for r in rows] == [('GV', False), ('Bloc', True), ('Bloc', False)]
    assert rows[0]['cotation'].startswith('5a → 6c (')
    assert rows[1]['cotation'] == '6b' and rows[2]['cotation'] == '6a'
    assert rows[2]['lieu'] == 'Marseille › Calanques › En-Vau › Nord'


def test_chronological_rows_missing_cotation_dash(conn, uid):
    add_ascension(conn, uid, 'X', cotation=None)
    assert export_pdf._chronological_rows(*load(conn, uid))[0]['cotation'] == '—'


def test_pdf_metres_match_the_stats_page(conn, uid):
    """Le PDF et la page Stats doivent donner exactement les mêmes mètres, par discipline et au total."""
    from src.services import stats
    b = add_ascension(conn, uid, 'B', hauteur=4)
    gv = add_ascension(conn, uid, 'GV', type='grande_voie', cotation='5a', cotation_haute='6a', grimpe='tete',
                       longueurs=[{'cotation': '5a', 'hauteur': 30}, {'cotation': '6a', 'hauteur': 20}])
    gv2 = add_ascension(conn, uid, 'GV2', type='grande_voie', cotation='5a', cotation_haute='6a', grimpe='tete',
                        hauteur=100, longueurs=[{'cotation': '5a', 'hauteur': 10}])
    for a in (b, b, gv, gv2):
        conn.execute("INSERT INTO repetition(ascension_id, date, grimpe) VALUES(?, '2026-05-01', 'tete')", (a,))
    conn.commit()
    per_type, _, total = export_pdf._per_type_summary(conn, *export_pdf._load_data(conn, uid))
    s = stats.compute_stats(conn, uid)
    for t, v in s['per_type'].items():
        assert per_type[t]['metres'] == v['metres'], t
    assert round(total, 1) == s['total_metres'] == 4 * 3 + 50 * 2 + 100 * 2


def test_pdf_summary_counts_only_lead_for_voie_and_trad(conn, uid):
    add_ascension(conn, uid, 'T', type='voie', grimpe='tete', hauteur=20, cotation='6a')
    m = add_ascension(conn, uid, 'M', type='voie', grimpe='moulinette', hauteur=10, cotation='7a')
    add_ascension(conn, uid, 'GV', type='grande_voie', cotation='5a', cotation_haute='6a', grimpe='moulinette', hauteur=100)
    conn.execute("INSERT INTO repetition(ascension_id, date, grimpe) VALUES(?, '2026-05-01', 'tete')", (m,))
    conn.commit()
    per_type, cot_max, total = export_pdf._per_type_summary(conn, *export_pdf._load_data(conn, uid))
    assert per_type['voie'] == {'nb': 1, 'metres': 20, 'cot_max': '6a'}
    assert per_type['grande_voie']['nb'] == 1 and total == 120 and cot_max == '6a'
    # la liste chronologique, elle, montre toujours tout
    assert len(export_pdf._chronological_rows(*export_pdf._load_data(conn, uid))) == 4


def test_csv_gives_the_title_of_the_chosen_topo_pdf_but_not_the_file(conn, uid):
    from src.services import topo_pdf
    a = add_ascension(conn, uid, 'Avec topo')
    add_ascension(conn, uid, 'Sans topo')
    topo, _ = topo_pdf.add_topo(conn, uid, 'Verdon.pdf', b'%PDF-1.4 contenu secret')
    conn.execute('UPDATE ascension SET topo_id=? WHERE id=?', (topo['id'], a))
    conn.commit()
    _, data = read_zip(export_csv.build_export_zip(conn, uid))
    rows = {r['nom']: r for r in data['ascensions.csv']}
    assert rows['Avec topo']['topo_pdf'] == 'Verdon' and rows['Sans topo']['topo_pdf'] == ''
    assert 'contenu secret' not in str(data)
