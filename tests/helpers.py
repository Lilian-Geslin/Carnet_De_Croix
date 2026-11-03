"""Outils partagés par les tests : fabrication d'utilisateurs, de lieux et d'ascensions."""
from werkzeug.security import generate_password_hash

from src.services import ascensions as asc_service
from src.services import geo as geo_service

DEFAULT_PLACE = {
    'pays': 'France', 'departement': 'Bouches-du-Rhône', 'localisation': 'Marseille',
    'site': 'Calanques', 'secteur': 'En-Vau',
}


def create_user(conn, name='Lilian', email='lilian@example.fr', password='secret'):
    """Insère un utilisateur directement en base et renvoie son identifiant."""
    cur = conn.execute("INSERT INTO user(name, email, password) VALUES(?,?,?)",
                       (name, email, generate_password_hash(password)))
    conn.commit()
    return cur.lastrowid


def add_ascension(conn, uid, nom='Bloc A', type='bloc', statut='log', cotation='6a', place=None, **fields):
    """Crée une ascension (avec toute sa chaîne de lieux) via les services et renvoie son identifiant.

    `place` complète/remplace DEFAULT_PLACE (pays, departement, localisation, site, secteur, sous_secteur).
    """
    loc = {**DEFAULT_PLACE, **(place or {})}
    secteur_id, sous_secteur_id = geo_service.resolve_location(conn, uid, loc)
    data = {'type': type, 'statut': statut, 'nom': nom, 'cotation': cotation, **fields}
    if statut == 'log':
        data.setdefault('date', '2026-01-10')
    asc_id = asc_service.insert_ascension(conn, uid, secteur_id, sous_secteur_id, data)
    conn.commit()
    return asc_id


def asc_payload(**over):
    """Corps JSON d'une création d'ascension (bloc loguée) ; `over` remplace ou ajoute des champs."""
    payload = {
        **DEFAULT_PLACE, 'type': 'bloc', 'statut': 'log', 'nom': 'Bloc A', 'cotation': '6a',
        'date': '2026-01-10', 'style': 'a_vue', 'hauteur': 4, 'note_beaute': 2,
    }
    payload.update(over)
    return payload


def row(conn, sql, *params):
    return conn.execute(sql, params).fetchone()


def scalar(conn, sql, *params):
    return conn.execute(sql, params).fetchone()[0]
