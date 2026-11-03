"""Page Carnet : arbre des lieux (pays › … › secteur) contenant uniquement des ascensions loguées.

Seuls les « log » apparaissent ici : les projets ont leur page (projets.py) et les envies leur
tick list (ticklist.py).
"""
from .formatting import fmt_date
from .grades import sort_ascensions


def build_carnet_tree(conn, uid):
    """Arbre pays › département › localisation › site › secteur (› sous-secteur) de l'utilisateur.

    Les niveaux qui ne contiennent aucun log (seulement des projets, des envies de tick list, ou
    rien) sont omis.
    """
    # Un niveau est ajouté à l'arbre seulement si, en dessous, quelque chose a survécu
    # (la ligne « if secteurs / sites / localisations / departements » de chaque boucle)
    tree = []
    for pays in conn.execute("SELECT * FROM pays WHERE user_id=? ORDER BY name", (uid,)).fetchall():
        departements = []
        for dep in conn.execute("SELECT * FROM departement WHERE pays_id=? ORDER BY name", (pays['id'],)).fetchall():
            localisations = []
            for loc in conn.execute("SELECT * FROM localisation WHERE departement_id=? ORDER BY name", (dep['id'],)).fetchall():
                sites = []
                for site in conn.execute("SELECT * FROM site WHERE localisation_id=? ORDER BY name", (loc['id'],)).fetchall():
                    secteurs = [node for node in (
                        _secteur_node(conn, uid, sec)
                        for sec in conn.execute("SELECT * FROM secteur WHERE site_id=? ORDER BY name", (site['id'],)).fetchall()
                    ) if node]
                    if secteurs:
                        sites.append({'site': dict(site), 'secteurs': secteurs})
                if sites:
                    localisations.append({'localisation': dict(loc), 'sites': sites})
            if localisations:
                departements.append({'departement': dict(dep), 'localisations': localisations})
        if departements:
            tree.append({'pays': dict(pays), 'departements': departements})
    return tree


def _secteur_node(conn, uid, sec):
    """Nœud d'un secteur avec ses ascensions et celles de ses sous-secteurs ; None s'il n'a aucun log."""
    # Logs directement sous le secteur (pas de sous-secteur), du plus récent au plus ancien
    directes = conn.execute("""
        SELECT * FROM ascension WHERE secteur_id=? AND sous_secteur_id IS NULL
            AND user_id=? AND statut='log'
        ORDER BY date DESC
    """, (sec['id'], uid)).fetchall()

    # Sous-secteurs de ce secteur, chacun avec ses propres ascensions (ceux sans log sont masqués)
    sous_secteurs = []
    for ss in conn.execute("SELECT * FROM sous_secteur WHERE secteur_id=? ORDER BY name", (sec['id'],)).fetchall():
        rows = conn.execute("""
            SELECT * FROM ascension WHERE sous_secteur_id=? AND user_id=? AND statut='log'
            ORDER BY date DESC
        """, (ss['id'], uid)).fetchall()
        if rows:
            sous_secteurs.append({'sous_secteur': dict(ss), 'ascensions': _ascension_cards(conn, rows)})

    # Secteur sans aucun log (ni direct, ni en sous-secteur) : on ne l'affiche pas
    total = len(directes) + sum(len(ss['ascensions']) for ss in sous_secteurs)
    if total == 0:
        return None
    return {
        'sec': dict(sec),
        'ascensions': _ascension_cards(conn, directes),
        'sous_secteurs': sous_secteurs,
        'total_count': total,
    }


def _ascension_cards(conn, rows):
    """Ascensions triées (plus dures d'abord) avec leurs répétitions et leurs longueurs."""
    # Chaque « carte » = une ascension + ses répétitions (ré-enchaînements) + ses longueurs (grande voie)
    cards = []
    for a in sort_ascensions(rows):
        reps = conn.execute("SELECT * FROM repetition WHERE ascension_id=? ORDER BY date DESC", (a['id'],)).fetchall()
        longueurs = conn.execute("SELECT * FROM longueur WHERE ascension_id=? ORDER BY numero", (a['id'],)).fetchall()
        asc = dict(a)
        asc['date_fmt'] = fmt_date(asc.get('date'))
        reps_list = []
        for r in reps:
            rep = dict(r)
            rep['date_fmt'] = fmt_date(rep.get('date'))
            reps_list.append(rep)
        cards.append({'asc': asc, 'reps': reps_list, 'longueurs': [dict(l) for l in longueurs]})
    return cards
