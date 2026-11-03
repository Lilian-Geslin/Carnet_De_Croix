"""Schéma de la base SQLite et migrations.

Hiérarchie des lieux : pays > departement > localisation > site > secteur > sous_secteur (facultatif).
Chaque ascension est rattachée à un secteur (et éventuellement un sous-secteur) ; ses longueurs,
répétitions, séances, rééquipements et choix (tags) sont dans des tables enfants. Les tables de lieux
descendent de `user` via `pays.user_id` : chaque utilisateur ne voit que ses propres données.

Les migrations réparent les bases créées par d'anciennes versions : elles testent d'abord si la
correction est nécessaire (colonne ou table absente) avant d'agir.

`init_db` est idempotent : on peut l'appeler à chaque démarrage (et après une restauration)
sur une base neuve comme sur une base créée par une ancienne version de l'application.
"""
import hashlib
import sqlite3


def init_db(path):
    """Crée les tables manquantes et applique les migrations nécessaires."""
    conn = sqlite3.connect(path)
    try:
        _create_user_and_top_levels(conn)
        _rename_falaise_to_localisation(conn)
        _create_geo_tables(conn)
        _create_ascension_table(conn)
        _migrate_ascension_columns(conn)
        _migrate_ressenti_columns(conn)
        _migrate_envie_classique_to_majeure(conn)
        _create_longueur_table(conn)
        _create_repetition_table(conn)
        _create_seance_table(conn)
        _create_reequipement_table(conn)
        _create_tag_tables(conn)
        _create_topo_tables(conn)
        _migrate_topo_fichier(conn)
        _create_auth_attempt_table(conn)
        conn.commit()
    finally:
        conn.close()


def _columns(conn, table):
    """Noms des colonnes d'une table (sert à savoir si une migration est déjà faite)."""
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


# ─── Création des tables ─────────────────────────────────────────────────────

def _create_user_and_top_levels(conn):
    """Tables `user` (compte : mot de passe stocké haché), `pays` et `departement` (niveaux hauts des lieux).
    UNIQUE(user_id, name) / UNIQUE(pays_id, name) : pas deux fois le même nom au même endroit."""
    conn.execute("""
    CREATE TABLE IF NOT EXISTS user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS pays (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        UNIQUE(user_id, name),
        FOREIGN KEY(user_id) REFERENCES user(id)
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS departement (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pays_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        UNIQUE(pays_id, name),
        FOREIGN KEY(pays_id) REFERENCES pays(id)
    )
    """)


def _rename_falaise_to_localisation(conn):
    """Migration : le niveau « falaise » s'appelle désormais « localisation » (bases existantes).
    Répare les bases de l'ancienne version où la table s'appelait `falaise` (et `site.falaise_id`).
    Fait avant la création des tables suivantes pour travailler directement avec les nouveaux noms.
    Idempotent : ne renomme que si l'ancien nom est encore là et le nouveau absent ; sur une base
    neuve ou déjà migrée, aucune des conditions n'est vraie et il ne se passe rien."""
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    if 'falaise' in tables and 'localisation' not in tables:
        conn.execute("ALTER TABLE falaise RENAME TO localisation")
    if 'site' in tables:
        site_cols = _columns(conn, 'site')
        if 'falaise_id' in site_cols and 'localisation_id' not in site_cols:
            conn.execute("ALTER TABLE site RENAME COLUMN falaise_id TO localisation_id")


def _create_geo_tables(conn):
    """Localisation, site, secteur et sous-secteur (niveau optionnel sous le secteur)."""
    conn.execute("""
    CREATE TABLE IF NOT EXISTS localisation (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        departement_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        UNIQUE(departement_id, name),
        FOREIGN KEY(departement_id) REFERENCES departement(id)
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS site (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        localisation_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        UNIQUE(localisation_id, name),
        FOREIGN KEY(localisation_id) REFERENCES localisation(id)
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS secteur (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        site_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        ressenti TEXT,
        UNIQUE(site_id, name),
        FOREIGN KEY(site_id) REFERENCES site(id)
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS sous_secteur (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        secteur_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        ressenti TEXT,
        UNIQUE(secteur_id, name),
        FOREIGN KEY(secteur_id) REFERENCES secteur(id)
    )
    """)


def _create_ascension_table(conn):
    """Table centrale `ascension` : une ligne = une voie / un bloc, quel que soit son statut
    (log, projet, ticklist). Colonnes importantes : `type` et `statut` (voir constants.py), `cotation`
    (+ `cotation_haute` pour les grandes voies), `cotation_perso` (ressenti de l'utilisateur), `style`
    (à vue, flash, nombre d'essais), `grimpe` (tête / moulinette), `note_beaute`, `date`.
    Les colonnes ajoutées plus tard sont dans _ASCENSION_EXTRA_COLUMNS (voir _migrate_ascension_columns)."""
    conn.execute("""
    CREATE TABLE IF NOT EXISTS ascension (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        secteur_id INTEGER,
        sous_secteur_id INTEGER,
        type TEXT NOT NULL,
        statut TEXT NOT NULL DEFAULT 'log',
        nom TEXT NOT NULL,
        cotation TEXT,
        cotation_haute TEXT,
        cotation_perso TEXT,
        style TEXT,
        nb_essais_projet INTEGER DEFAULT 0,
        pieds_nus INTEGER DEFAULT 0,
        hauteur REAL,
        note_beaute INTEGER,
        date TEXT,
        commentaire TEXT,
        type_depart TEXT,
        type_arrivee TEXT,
        nb_longueurs INTEGER,
        grimpe TEXT,
        FOREIGN KEY(user_id) REFERENCES user(id),
        FOREIGN KEY(secteur_id) REFERENCES secteur(id),
        FOREIGN KEY(sous_secteur_id) REFERENCES sous_secteur(id)
    )
    """)


def _create_longueur_table(conn):
    """Longueurs d'une grande voie : une ligne par longueur (`numero`), avec sa propre cotation et son style."""
    conn.execute("""
    CREATE TABLE IF NOT EXISTS longueur (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ascension_id INTEGER NOT NULL,
        numero INTEGER NOT NULL,
        cotation TEXT,
        cotation_perso TEXT,
        style TEXT,
        pieds_nus INTEGER DEFAULT 0,
        hauteur REAL,
        note_beaute INTEGER,
        grimpe TEXT,
        FOREIGN KEY(ascension_id) REFERENCES ascension(id)
    )
    """)


def _create_repetition_table(conn):
    """Répétitions : ascensions d'une voie déjà loguée, refaites à une autre date (`date` obligatoire)."""
    conn.execute("""
    CREATE TABLE IF NOT EXISTS repetition (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ascension_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        nb_essais TEXT,
        cotation_perso TEXT,
        pieds_nus INTEGER DEFAULT 0,
        note_beaute INTEGER,
        commentaire TEXT,
        FOREIGN KEY(ascension_id) REFERENCES ascension(id)
    )
    """)
    # Migration : mode de grimpe (en tête / moulinette) de chaque répétition. Les répétitions déjà
    # enregistrées reprennent celui de leur ascension (modifiable ensuite).
    # Répare les bases d'avant l'ajout de cette colonne. Idempotent : la colonne n'est ajoutée (et
    # remplie) que si elle manque, donc les valeurs déjà saisies ne sont jamais écrasées.
    if 'grimpe' not in _columns(conn, 'repetition'):
        conn.execute("ALTER TABLE repetition ADD COLUMN grimpe TEXT")
        conn.execute("""UPDATE repetition SET grimpe = (SELECT a.grimpe FROM ascension a WHERE a.id = repetition.ascension_id)
                        WHERE grimpe IS NULL""")


def _create_seance_table(conn):
    """Séances d'un projet : numéro, date, nombre d'essais, mini-journal. Elles restent attachées
    à l'ascension quand le projet est ajouté au carnet."""
    conn.execute("""
    CREATE TABLE IF NOT EXISTS seance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ascension_id INTEGER NOT NULL,
        numero INTEGER NOT NULL,
        date TEXT,
        nb_essais INTEGER NOT NULL DEFAULT 0,
        commentaire TEXT,
        FOREIGN KEY(ascension_id) REFERENCES ascension(id)
    )
    """)
    # Migration : un projet qui avait déjà un total d'essais mais aucune séance reçoit une
    # séance n°1 (sans date) portant ce total, pour ne rien perdre de l'ancien compteur.
    # Répare les bases d'avant l'existence des séances (seul `nb_essais_projet` existait).
    # Idempotent : le NOT EXISTS ignore toute ascension qui a déjà au moins une séance, donc
    # relancer cette requête à chaque démarrage n'ajoute rien.
    conn.execute("""
        INSERT INTO seance(ascension_id, numero, date, nb_essais, commentaire)
        SELECT a.id, 1, NULL, a.nb_essais_projet, NULL FROM ascension a
        WHERE a.nb_essais_projet > 0
          AND NOT EXISTS (SELECT 1 FROM seance s WHERE s.ascension_id = a.id)
    """)


def _create_reequipement_table(conn):
    """Rééquipements d'une voie : qui l'a rééquipée et en quelle année (plusieurs possibles, ordre conservé
    grâce à la colonne `ordre`)."""
    conn.execute("""
    CREATE TABLE IF NOT EXISTS reequipement (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ascension_id INTEGER NOT NULL,
        nom TEXT,
        annee INTEGER,
        ordre INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(ascension_id) REFERENCES ascension(id)
    )
    """)


def _create_tag_tables(conn):
    """Listes de propositions par utilisateur (fixations, coinceurs, roche, type de grimpe) et choix retenus.
    Trois tables : `tag_option` (la liste de l'utilisateur), `tag_seed` (remplissage initial déjà fait)
    et `ascension_tag` (ce qui a été choisi pour chaque ascension). Catégories : voir TAG_CATS (constants.py)."""
    conn.execute("""
    CREATE TABLE IF NOT EXISTS tag_option (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        categorie TEXT NOT NULL,
        nom TEXT NOT NULL,
        UNIQUE(user_id, categorie, nom)
    )
    """)
    # tag_seed garde la trace du remplissage initial : si l'utilisateur supprime toutes ses
    # propositions, elles ne reviennent pas toutes seules.
    conn.execute("""
    CREATE TABLE IF NOT EXISTS tag_seed (
        user_id INTEGER NOT NULL,
        categorie TEXT NOT NULL,
        PRIMARY KEY(user_id, categorie)
    )
    """)
    # Choix retenus pour une ascension (on garde le texte : retirer une proposition de la liste
    # n'efface pas ce qui a déjà été renseigné sur les ascensions).
    conn.execute("""
    CREATE TABLE IF NOT EXISTS ascension_tag (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ascension_id INTEGER NOT NULL,
        categorie TEXT NOT NULL,
        nom TEXT NOT NULL,
        UNIQUE(ascension_id, categorie, nom),
        FOREIGN KEY(ascension_id) REFERENCES ascension(id)
    )
    """)


def _create_topo_tables(conn):
    """Bibliothèque de topos PDF enregistrés dans le site : deux tables.

    `topo` : un PDF par ligne, stocké dans la base elle-même (BLOB) pour que la sauvegarde / restauration de
    `carnet.db` l'emporte. `nom` est le titre affiché (modifiable), `fichier_nom` le nom d'origine du fichier,
    `taille` sa taille en octets, `sha256` l'empreinte du contenu : le couple (user_id, sha256) est unique, donc
    un même fichier n'est jamais enregistré deux fois pour un même compte. Plusieurs ascensions partagent un topo
    en pointant vers lui avec `ascension.topo_id`.

    `topo_lieu` : rattache un topo à un lieu (niveau localisation, site, secteur ou sous-secteur) quand on l'ajoute
    depuis le bouton « Topo » de ce lieu ou depuis la fiche d'une ascension. Les topos affichés par le bouton « Topo »
    d'un lieu sont ceux qui lui sont rattachés ou qui sont utilisés par une ascension en dessous de lui.
    Idempotent (CREATE IF NOT EXISTS)."""
    conn.execute("""
    CREATE TABLE IF NOT EXISTS topo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        nom TEXT NOT NULL,
        fichier_nom TEXT NOT NULL,
        taille INTEGER NOT NULL,
        sha256 TEXT NOT NULL,
        contenu BLOB NOT NULL,
        date_ajout TEXT,
        UNIQUE(user_id, sha256),
        FOREIGN KEY(user_id) REFERENCES user(id)
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS topo_lieu (
        topo_id INTEGER NOT NULL,
        niveau TEXT NOT NULL,
        lieu_id INTEGER NOT NULL,
        PRIMARY KEY (topo_id, niveau, lieu_id),
        FOREIGN KEY(topo_id) REFERENCES topo(id)
    )
    """)


def _migrate_topo_fichier(conn):
    """Migration : l'ancienne table `topo_fichier` (un PDF copié pour chaque ascension) est remplacée par la
    bibliothèque `topo`. Chaque PDF devient un topo (les contenus identiques d'un même compte sont fusionnés en un
    seul), l'ascension pointe dessus par `topo_id`, puis l'ancienne table est supprimée. Idempotent : sans ancienne
    table, il n'y a rien à faire."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='topo_fichier'").fetchone():
        return
    rows = conn.execute("""SELECT f.ascension_id, f.nom, f.taille, f.contenu, f.date_ajout, a.user_id
                           FROM topo_fichier f JOIN ascension a ON a.id=f.ascension_id""").fetchall()
    for asc_id, nom, taille, contenu, date_ajout, user_id in rows:
        contenu = bytes(contenu)
        sha = hashlib.sha256(contenu).hexdigest()
        row = conn.execute("SELECT id FROM topo WHERE user_id=? AND sha256=?", (user_id, sha)).fetchone()
        if row:
            topo_id = row[0]
        else:
            titre = nom[:-4] if nom.lower().endswith('.pdf') else nom
            topo_id = conn.execute(
                "INSERT INTO topo(user_id, nom, fichier_nom, taille, sha256, contenu, date_ajout) VALUES(?,?,?,?,?,?,?)",
                (user_id, titre or nom, nom, taille, sha, contenu, date_ajout)).lastrowid
        conn.execute("UPDATE ascension SET topo_id=? WHERE id=?", (topo_id, asc_id))
    conn.execute("DROP TABLE topo_fichier")


# ─── Migrations de colonnes ──────────────────────────────────────────────────

# Colonnes ajoutées à `ascension` après la première version : (nom, définition SQL).
_ASCENSION_EXTRA_COLUMNS = (
    ('cotation_haute',  'TEXT'),                                  # grandes voies : cotation haute
    ('sous_secteur_id', 'INTEGER REFERENCES sous_secteur(id)'),
    # fenêtre « Plus d'informations » : topo consulté (papier : titre/édition/année/page ; pdf : titre/lien)
    ('topo_type',       'TEXT'),                                  # 'papier' | 'pdf' | NULL
    ('topo_nom',        'TEXT'),
    ('topo_edition',    'TEXT'),
    ('topo_annee',      'INTEGER'),
    ('topo_page',       'TEXT'),
    ('topo_lien',       'TEXT'),
    ('annee_ouverture', 'INTEGER'),                               # ouverture de la voie
    ('ouvreur',         'TEXT'),
    ('envie_categorie', 'TEXT'),                                  # tick list : 'performance' | 'beaute' | 'majeure' | NULL
    ('topo_id',         'INTEGER REFERENCES topo(id)'),           # topo PDF de la bibliothèque (table `topo`) utilisé, ou NULL
)


def _migrate_ascension_columns(conn):
    """Migration : ajoute à `ascension` les colonnes de _ASCENSION_EXTRA_COLUMNS qui manquent.
    Répare les bases créées avant l'arrivée de ces fonctions (grandes voies, sous-secteurs, topo,
    tick list). Idempotent : on ne touche que les colonnes absentes, donc rien ne se passe sur une
    base à jour (SQLite refuserait d'ajouter deux fois la même colonne)."""
    existing = _columns(conn, 'ascension')
    for col, ddl in _ASCENSION_EXTRA_COLUMNS:
        if col not in existing:
            conn.execute(f"ALTER TABLE ascension ADD COLUMN {col} {ddl}")


def _migrate_envie_classique_to_majeure(conn):
    """Migration : la catégorie d'envie « classique » de la tick list s'appelle désormais « majeure ».
    Répare les bases (et sauvegardes restaurées) d'avant ce changement de nom. Idempotent : une fois les
    lignes converties, plus aucune ne vaut « classique » et la requête ne modifie rien."""
    conn.execute("UPDATE ascension SET envie_categorie='majeure' WHERE envie_categorie='classique'")


def _migrate_ressenti_columns(conn):
    """Migration : ajoute la colonne `ressenti` (voir RESSENTI_LABELS) aux secteurs et sous-secteurs
    des bases créées avant cette fonction. Idempotent : n'agit que si la colonne manque."""
    for table in ('secteur', 'sous_secteur'):
        if 'ressenti' not in _columns(conn, table):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN ressenti TEXT")


def _create_auth_attempt_table(conn):
    """Table des tentatives (connexion, inscription) : sert à bloquer les essais répétés (services/ratelimit.py).

    Une ligne = un échec (ou une action comptée) dans un « seau » (ex. « login:pair:email|ip ») à un instant donné.
    """
    conn.execute("""
    CREATE TABLE IF NOT EXISTS auth_attempt (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bucket TEXT NOT NULL,
        ts INTEGER NOT NULL
    )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_auth_attempt ON auth_attempt(bucket, ts)")
