"""src/schema.py : création du schéma et migrations depuis d'anciennes bases."""
import sqlite3

import pytest

from src.schema import init_db

TABLES = {'user', 'pays', 'departement', 'localisation', 'site', 'secteur', 'sous_secteur', 'ascension',
          'longueur', 'repetition', 'seance', 'reequipement', 'tag_option', 'tag_seed', 'ascension_tag', 'topo', 'topo_lieu', 'auth_attempt'}


def tables(path):
    c = sqlite3.connect(path)
    try:
        return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    finally:
        c.close()


def columns(path, table):
    c = sqlite3.connect(path)
    try:
        return [r[1] for r in c.execute(f'PRAGMA table_info({table})')]
    finally:
        c.close()


def test_fresh_database_has_every_table(tmp_path):
    path = str(tmp_path / 'a.db')
    init_db(path)
    assert tables(path) == TABLES


def test_init_is_idempotent(tmp_path):
    path = str(tmp_path / 'a.db')
    init_db(path)
    c = sqlite3.connect(path)
    c.execute("INSERT INTO user(name,email,password) VALUES('a','a@a.fr','x')")
    c.commit()
    c.close()
    init_db(path)
    init_db(path)
    c = sqlite3.connect(path)
    assert c.execute('SELECT COUNT(*) FROM user').fetchone()[0] == 1
    c.close()


def test_ascension_has_all_columns(tmp_path):
    path = str(tmp_path / 'a.db')
    init_db(path)
    cols = set(columns(path, 'ascension'))
    assert {'cotation_haute', 'sous_secteur_id', 'topo_type', 'topo_lien', 'annee_ouverture', 'ouvreur',
            'envie_categorie', 'grimpe', 'nb_longueurs'} <= cols


def test_unique_constraints(tmp_path):
    path = str(tmp_path / 'a.db')
    init_db(path)
    c = sqlite3.connect(path)
    c.execute("INSERT INTO user(name,email,password) VALUES('a','a@a.fr','x')")
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO user(name,email,password) VALUES('b','a@a.fr','y')")
    c.execute("INSERT INTO pays(user_id,name) VALUES(1,'France')")
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO pays(user_id,name) VALUES(1,'France')")
    c.close()


def make_legacy_db(path):
    """Base telle que créée par une toute première version : « falaise », pas de colonnes récentes."""
    c = sqlite3.connect(path)
    c.executescript("""
    CREATE TABLE user (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL);
    CREATE TABLE pays (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL);
    CREATE TABLE departement (id INTEGER PRIMARY KEY AUTOINCREMENT, pays_id INTEGER NOT NULL, name TEXT NOT NULL);
    CREATE TABLE falaise (id INTEGER PRIMARY KEY AUTOINCREMENT, departement_id INTEGER NOT NULL, name TEXT NOT NULL);
    CREATE TABLE site (id INTEGER PRIMARY KEY AUTOINCREMENT, falaise_id INTEGER NOT NULL, name TEXT NOT NULL);
    CREATE TABLE secteur (id INTEGER PRIMARY KEY AUTOINCREMENT, site_id INTEGER NOT NULL, name TEXT NOT NULL);
    CREATE TABLE ascension (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, secteur_id INTEGER,
        type TEXT NOT NULL, statut TEXT NOT NULL DEFAULT 'log', nom TEXT NOT NULL, cotation TEXT, cotation_perso TEXT,
        style TEXT, nb_essais_projet INTEGER DEFAULT 0, pieds_nus INTEGER DEFAULT 0, hauteur REAL, note_beaute INTEGER,
        date TEXT, commentaire TEXT, type_depart TEXT, type_arrivee TEXT, nb_longueurs INTEGER, grimpe TEXT);
    CREATE TABLE repetition (id INTEGER PRIMARY KEY AUTOINCREMENT, ascension_id INTEGER NOT NULL, date TEXT NOT NULL,
        nb_essais TEXT, cotation_perso TEXT, pieds_nus INTEGER DEFAULT 0, note_beaute INTEGER, commentaire TEXT);
    INSERT INTO user(name,email,password) VALUES('Lilian','l@l.fr','x');
    INSERT INTO pays(user_id,name) VALUES(1,'France');
    INSERT INTO departement(pays_id,name) VALUES(1,'Gard');
    INSERT INTO falaise(departement_id,name) VALUES(1,'La Capelle');
    INSERT INTO site(falaise_id,name) VALUES(1,'Grand Cirque');
    INSERT INTO secteur(site_id,name) VALUES(1,'Eléphant');
    INSERT INTO ascension(user_id,secteur_id,type,statut,nom,cotation,grimpe,date) VALUES(1,1,'voie','log','Vieille voie','6a','tete','2025-10-05');
    INSERT INTO ascension(user_id,secteur_id,type,statut,nom,cotation,nb_essais_projet) VALUES(1,1,'bloc','projet','Vieux projet','7a',7);
    INSERT INTO ascension(user_id,secteur_id,type,statut,nom,cotation,nb_essais_projet) VALUES(1,1,'bloc','projet','Projet vide','6c',0);
    INSERT INTO repetition(ascension_id,date) VALUES(1,'2025-11-01');
    """)
    c.commit()
    c.close()


def test_legacy_database_is_migrated_without_losing_data(tmp_path):
    path = str(tmp_path / 'old.db')
    make_legacy_db(path)
    init_db(path)

    assert 'falaise' not in tables(path) and 'localisation' in tables(path)
    assert 'localisation_id' in columns(path, 'site') and 'falaise_id' not in columns(path, 'site')
    assert 'ressenti' in columns(path, 'secteur') and 'ressenti' in columns(path, 'sous_secteur')
    assert {'cotation_haute', 'topo_type', 'envie_categorie', 'sous_secteur_id'} <= set(columns(path, 'ascension'))
    assert TABLES <= tables(path)

    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    assert c.execute('SELECT name FROM localisation').fetchone()['name'] == 'La Capelle'
    assert c.execute('SELECT localisation_id FROM site').fetchone()[0] == 1
    assert c.execute("SELECT COUNT(*) FROM ascension").fetchone()[0] == 3
    c.close()


def test_legacy_projects_get_a_first_seance(tmp_path):
    path = str(tmp_path / 'old.db')
    make_legacy_db(path)
    init_db(path)
    c = sqlite3.connect(path)
    rows = c.execute('SELECT ascension_id, numero, date, nb_essais FROM seance').fetchall()
    c.close()
    assert rows == [(2, 1, None, 7)]          # seul le projet avec des essais en reçoit une


def test_legacy_migration_does_not_duplicate_seances_on_second_run(tmp_path):
    path = str(tmp_path / 'old.db')
    make_legacy_db(path)
    init_db(path)
    init_db(path)
    c = sqlite3.connect(path)
    assert c.execute('SELECT COUNT(*) FROM seance').fetchone()[0] == 1
    c.close()


def test_legacy_repetitions_inherit_the_mode_of_their_ascension(tmp_path):
    path = str(tmp_path / 'old.db')
    make_legacy_db(path)
    init_db(path)
    c = sqlite3.connect(path)
    assert c.execute('SELECT grimpe FROM repetition').fetchone()[0] == 'tete'
    c.close()


def test_topo_tables_columns(tmp_path):
    path = str(tmp_path / 'a.db')
    init_db(path)
    assert columns(path, 'topo') == ['id', 'user_id', 'nom', 'fichier_nom', 'taille', 'sha256', 'contenu', 'date_ajout']
    assert columns(path, 'topo_lieu') == ['topo_id', 'niveau', 'lieu_id']
    assert 'topo_id' in columns(path, 'ascension')
    assert 'topo_fichier' not in tables(path)


def test_topo_is_unique_per_account_and_content(tmp_path):
    path = str(tmp_path / 'a.db')
    init_db(path)
    c = sqlite3.connect(path)
    ins = "INSERT INTO topo(user_id, nom, fichier_nom, taille, sha256, contenu) VALUES(?,?,?,?,?,?)"
    c.execute(ins, (1, 'a', 'a.pdf', 1, 'abc', b'x'))
    c.execute(ins, (2, 'a', 'a.pdf', 1, 'abc', b'x'))             # autre compte : accepté
    with pytest.raises(sqlite3.IntegrityError):
        c.execute(ins, (1, 'b', 'b.pdf', 1, 'abc', b'x'))         # même compte, même contenu : refusé
    c.close()


def test_legacy_database_gets_the_topo_tables(tmp_path):
    path = str(tmp_path / 'old.db')
    make_legacy_db(path)
    init_db(path)
    assert {'topo', 'topo_lieu', 'auth_attempt'} <= tables(path) and 'topo_id' in columns(path, 'ascension')


def make_db_with_topo_fichier(path):
    """Base de la version précédente : un PDF copié pour chaque ascension (table `topo_fichier`)."""
    init_db(path)
    c = sqlite3.connect(path)
    c.executescript("""
    DROP TABLE topo; DROP TABLE topo_lieu;
    CREATE TABLE topo_fichier (ascension_id INTEGER PRIMARY KEY, nom TEXT NOT NULL, taille INTEGER NOT NULL,
        contenu BLOB NOT NULL, date_ajout TEXT);
    INSERT INTO user(name,email,password) VALUES('a','a@a.fr','x'), ('b','b@b.fr','x');
    INSERT INTO ascension(user_id,type,statut,nom) VALUES (1,'bloc','log','A1'), (1,'bloc','log','A2'),
        (1,'bloc','log','A3'), (2,'bloc','log','B1'), (1,'bloc','log','Sans PDF');
    """)
    pdf1, pdf2 = b'%PDF-1.4 premier', b'%PDF-1.4 second'
    c.executemany("INSERT INTO topo_fichier(ascension_id, nom, taille, contenu, date_ajout) VALUES(?,?,?,?,?)", [
        (1, 'Verdon.pdf', len(pdf1), pdf1, '2026-10-01'),
        (2, 'copie-du-meme.pdf', len(pdf1), pdf1, '2026-10-02'),      # même contenu : fusionné avec le précédent
        (3, 'Autre.PDF', len(pdf2), pdf2, '2026-10-03'),
        (4, 'Verdon.pdf', len(pdf1), pdf1, '2026-10-04'),             # même contenu, autre compte : topo distinct
        (99, 'orphelin.pdf', len(pdf1), pdf1, '2026-10-05'),          # ascension disparue : ignoré
    ])
    c.commit()
    c.close()
    return pdf1, pdf2


def test_topo_fichier_is_migrated_to_the_shared_library(tmp_path):
    path = str(tmp_path / 'prev.db')
    pdf1, pdf2 = make_db_with_topo_fichier(path)
    init_db(path)
    assert 'topo_fichier' not in tables(path)
    c = sqlite3.connect(path)
    topos = c.execute('SELECT user_id, nom, fichier_nom, taille, contenu FROM topo ORDER BY id').fetchall()
    assert topos == [(1, 'Verdon', 'Verdon.pdf', len(pdf1), pdf1), (1, 'Autre', 'Autre.PDF', len(pdf2), pdf2),
                     (2, 'Verdon', 'Verdon.pdf', len(pdf1), pdf1)]
    link = dict(c.execute('SELECT nom, topo_id FROM ascension').fetchall())
    assert link['A1'] == link['A2'] == 1 and link['A3'] == 2 and link['B1'] == 3 and link['Sans PDF'] is None
    c.close()


def test_topo_fichier_migration_is_idempotent(tmp_path):
    path = str(tmp_path / 'prev.db')
    make_db_with_topo_fichier(path)
    init_db(path)
    init_db(path)
    c = sqlite3.connect(path)
    assert c.execute('SELECT COUNT(*) FROM topo').fetchone()[0] == 3
    c.close()


def test_classique_envies_become_majeure(tmp_path):
    path = str(tmp_path / 'a.db')
    init_db(path)
    c = sqlite3.connect(path)
    c.execute("INSERT INTO user(name,email,password) VALUES('a','a@a.fr','x')")
    for nom, cat in (('A', 'classique'), ('B', 'beaute'), ('C', 'performance'), ('D', None)):
        c.execute("INSERT INTO ascension(user_id,type,statut,nom,envie_categorie) VALUES(1,'voie','ticklist',?,?)", (nom, cat))
    c.commit()
    c.close()

    init_db(path)
    init_db(path)                                  # idempotent
    c = sqlite3.connect(path)
    got = dict(c.execute('SELECT nom, envie_categorie FROM ascension').fetchall())
    c.close()
    assert got == {'A': 'majeure', 'B': 'beaute', 'C': 'performance', 'D': None}
