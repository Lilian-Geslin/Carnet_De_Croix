"""Page Tick List : envies à cocher, catégories, repères par rapport au niveau déjà atteint.

Une envie est une ascension de statut « ticklist » : une voie ou un bloc qu'on aimerait faire un jour.
Chaque envie peut avoir une catégorie (performance, beauté, majeure) et est comparée au meilleur
niveau déjà réalisé dans sa discipline, pour repérer celles qui sont plus dures que tout ce qu'on a fait.
"""
from ..constants import DEPART_LABELS, ENVIE_CATS, GV_TYPES, TYPE_LABELS
from ..errors import NotFoundError, ValidationError
from .ascensions import GEO_COLUMNS, GEO_JOINS
from .grades import alpine_from_classic, effective_cotation, grade_rank, palier_of


def _best_rank_by_type(conn, uid):
    """Meilleure cotation (rang, voir grade_rank) déjà réalisée dans chaque discipline, sous la forme
    {type: rang}. Seuls les logs comptent ; une discipline sans log n'apparaît pas."""
    best = {}
    for log in conn.execute("SELECT * FROM ascension WHERE user_id=? AND statut='log'", (uid,)):
        rank = grade_rank(effective_cotation(log) or '')
        if rank >= 0 and rank > best.get(log['type'], -1):
            best[log['type']] = rank
    return best


def _cotation_text(a):
    """Cotation affichée : « 6a → 6c (TD+) » pour une grande voie, sinon la cotation seule."""
    if a['type'] in GV_TYPES and a['cotation_haute']:
        text = f"{a['cotation']} → {a['cotation_haute']}" if a['cotation'] else a['cotation_haute']
        alpine = alpine_from_classic(a['cotation_haute'])
        return f"{text} ({alpine})" if alpine else text
    return a['cotation'] or ''


def list_envies(conn, uid):
    """Envies de la tick list (par nom), prêtes à être converties en JSON pour la page."""
    # Envies de l'utilisateur avec leurs lieux (et l'id du site, pour regrouper par site côté page)
    rows = conn.execute(f"""
        SELECT a.*, {GEO_COLUMNS}, si.id as site_id
        FROM ascension a {GEO_JOINS}
        WHERE a.user_id=? AND a.statut='ticklist'
        ORDER BY a.nom COLLATE NOCASE
    """, (uid,)).fetchall()
    best = _best_rank_by_type(conn, uid)

    # Une envie = dictionnaire plat, directement sérialisable en JSON pour le JavaScript de la page
    envies = []
    for a in rows:
        # Pour une grande voie on se fie à la cotation haute (cf. effective_cotation)
        eff = effective_cotation(a)
        rank = grade_rank(eff or '')
        envies.append({
            'id': a['id'], 'nom': a['nom'], 'type': a['type'],
            'type_label': TYPE_LABELS.get(a['type'], a['type']),
            'cotation': _cotation_text(a), 'rank': rank, 'palier': palier_of(eff),
            'site_id': a['site_id'], 'site': a['site_name'] or '—',
            'secteur': a['secteur_name'] or '', 'sous_secteur': a['sous_secteur_name'] or '',
            'chemin': ' › '.join(x for x in (a['pays_name'], a['departement_name'], a['localisation_name'], a['site_name']) if x),
            'hauteur': a['hauteur'], 'nb_longueurs': a['nb_longueurs'],
            'depart': DEPART_LABELS.get(a['type_depart'], ''),
            'commentaire': a['commentaire'] or '',
            'categorie': a['envie_categorie'] if a['envie_categorie'] in ENVIE_CATS else '',
            # envie plus dure que ce qu'on a déjà fait dans sa discipline (None : rien encore réalisé dans cette discipline)
            'above_max': (rank > best[a['type']]) if (rank >= 0 and a['type'] in best) else None,
        })
    return envies


def set_categorie(conn, uid, asc_id, categorie):
    """Change la catégorie d'une envie (ou la retire avec None).

    Lève ValidationError si la catégorie n'existe pas, NotFoundError si l'envie n'existe pas, n'est pas
    à l'utilisateur, ou n'est plus une envie (statut différent de « ticklist »).
    """
    if categorie is not None and categorie not in ENVIE_CATS:
        raise ValidationError('Catégorie invalide.')
    cur = conn.execute("UPDATE ascension SET envie_categorie=? WHERE id=? AND user_id=? AND statut='ticklist'",
                       (categorie, asc_id, uid))
    conn.commit()
    if cur.rowcount == 0:
        raise NotFoundError('Envie introuvable.')
