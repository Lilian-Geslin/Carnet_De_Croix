"""Page Recherche : filtres combinables, tri, regroupement par site, synthèse, calendrier.

Déroulé d'une recherche : parse_filters lit les paramètres de l'URL, search construit la requête
SQL (_build_query), applique la fourchette de cotation en Python (les cotations sont des textes
qu'on ne sait pas comparer en SQL) puis trie. summarize, group_by_site, filter_options et
build_calendar préparent ensuite l'affichage.
"""
import calendar as calendar_module
from datetime import date

from ..constants import GRADE_ORDER, GRIMPE_MODES, GV_TYPES, STYLE_ORDER
from .ascensions import GEO_COLUMNS, GEO_JOINS
from .formatting import fmt_date, sort_name_key
from .grades import effective_cotation, grade_index, grade_rank, max_grade

# Noms des mois affichés au-dessus du calendrier (index 0 = janvier)
MONTH_NAMES = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet',
               'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
# Valeurs acceptées pour les paramètres d'URL « statut » et « groupe » ; toute autre valeur est ignorée
STATUT_CHOICES = ('log', 'projet', 'ticklist', 'tout')
GROUP_CHOICES = ('site', 'plat')
# Tris pour lesquels on classe du plus grand au plus petit (sinon ordre croissant)
DESCENDING_SORTS = ('date_desc', 'cotation_desc', 'style_desc', 'beaute_desc', 'hauteur_desc')


# ─── Lecture des critères ────────────────────────────────────────────────────

def parse_filters(args):
    """Critères de recherche lus dans les paramètres de l'URL (valeurs inconnues ignorées).

    `args` est un dictionnaire de requête de type Flask (méthodes get et getlist) : les filtres à
    choix multiples (type, style, date…) sont des listes, les autres du texte. Les cotations min /
    max ne sont gardées que si elles existent dans GRADE_ORDER.
    """
    def text(name):
        return args.get(name, '').strip()

    statut = args.get('statut', 'log')
    groupe = args.get('groupe', 'site')
    cot_min, cot_max = args.get('cot_min', ''), args.get('cot_max', '')
    return {
        'tri':        args.get('tri', 'date_desc'),
        'groupe':     groupe if groupe in GROUP_CHOICES else 'site',
        'statut':     statut if statut in STATUT_CHOICES else 'log',
        'types':      args.getlist('type'),
        'styles':     args.getlist('style'),
        'beautes':    args.getlist('beaute'),
        'dates':      args.getlist('date'),
        'roches':     args.getlist('roche'),
        'tgrimpes':   args.getlist('tgrimpe'),
        'modes':      [m for m in args.getlist('mode') if m in GRIMPE_MODES],
        'cot_min':    cot_min if cot_min in GRADE_ORDER else '',
        'cot_max':    cot_max if cot_max in GRADE_ORDER else '',
        'hauteur_min': text('hauteur_min'),
        'hauteur_max': text('hauteur_max'),
        'pieds_nus':  args.get('pieds_nus', ''),
        'ouvreur':    text('ouvreur'),
        'annee_min':  text('annee_min'),
        'annee_max':  text('annee_max'),
        'topo':       text('topo'),
        'q':          text('q'),
    }


def _num(value):
    """Nombre décimal tiré de `value`, ou None si vide / invalide."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ─── Requête ─────────────────────────────────────────────────────────────────

def _in_clause(column, values):
    """Morceau de SQL « AND colonne IN (?,?,…) » avec autant de « ? » que de valeurs."""
    return f" AND {column} IN ({','.join('?' for _ in values)})"


def _build_query(uid, f):
    """SQL et paramètres correspondant aux critères (hors fourchette de cotation, appliquée ensuite).

    Le SQL est assemblé morceau par morceau, un « AND » par filtre renseigné ; les valeurs saisies
    passent toujours par des paramètres « ? » (jamais collées dans le texte SQL).
    """
    # Ascensions de l'utilisateur avec leurs lieux, et la somme des hauteurs des longueurs (grandes voies)
    sql = f"""
        SELECT a.*, {GEO_COLUMNS}, si.id as site_id,
               (SELECT SUM(l.hauteur) FROM longueur l WHERE l.ascension_id = a.id) as hauteur_longueurs
        FROM ascension a {GEO_JOINS}
        WHERE a.user_id=?
    """
    params = [uid]

    # « tout » = log + projet + tick list ; sinon un seul statut
    if f['statut'] == 'tout':
        sql += " AND a.statut IN ('log','projet','ticklist')"
    else:
        sql += " AND a.statut=?"
        params.append(f['statut'])

    # Filtres à choix multiples : l'ascension doit avoir l'une des valeurs cochées
    for column, key in (('a.type', 'types'), ('a.style', 'styles'), ('a.date', 'dates'), ('a.grimpe', 'modes')):
        if f[key]:
            sql += _in_clause(column, f[key])
            params += f[key]
    beautes = [int(b) for b in f['beautes'] if b.isdigit()]
    if beautes:
        sql += _in_clause('a.note_beaute', beautes)
        params += beautes

    h_min, h_max = _num(f['hauteur_min']), _num(f['hauteur_max'])
    if h_min is not None:
        sql += " AND a.hauteur >= ?"
        params.append(h_min)
    if h_max is not None:
        sql += " AND a.hauteur <= ?"
        params.append(h_max)

    # Pieds nus : sur l'ascension elle-même ou sur au moins une de ses répétitions
    if f['pieds_nus']:
        sql += """ AND (a.pieds_nus = 1 OR EXISTS (
            SELECT 1 FROM repetition rep WHERE rep.ascension_id = a.id AND rep.pieds_nus = 1
        ))"""

    # ouverture : année (fourchette) et ouvreur
    a_min, a_max = _num(f['annee_min']), _num(f['annee_max'])
    if a_min is not None:
        sql += " AND a.annee_ouverture >= ?"
        params.append(int(a_min))
    if a_max is not None:
        sql += " AND a.annee_ouverture <= ?"
        params.append(int(a_max))
    if f['ouvreur']:
        sql += " AND a.ouvreur LIKE ?"
        params.append(f"%{f['ouvreur']}%")

    # topo : titre ou édition
    if f['topo']:
        sql += " AND (a.topo_nom LIKE ? OR a.topo_edition LIKE ?)"
        params += [f"%{f['topo']}%"] * 2

    # type de roche / type de grimpe : au moins un des choix cochés (les choix sont dans la table ascension_tag)
    for cat, key in (('roche', 'roches'), ('grimpe', 'tgrimpes')):
        if f[key]:
            sql += (" AND EXISTS (SELECT 1 FROM ascension_tag t WHERE t.ascension_id = a.id"
                    f" AND t.categorie = ? AND t.nom IN ({','.join('?' for _ in f[key])}))")
            params += [cat] + f[key]

    # Recherche libre : dans le nom de la voie, les lieux ou le commentaire
    if f['q']:
        sql += (" AND (a.nom LIKE ? OR si.name LIKE ? OR loc.name LIKE ? OR sec.name LIKE ?"
                " OR ss.name LIKE ? OR a.commentaire LIKE ?)")
        params += [f"%{f['q']}%"] * 6
    return sql, params


def _within_grade_range(rows, cot_min, cot_max):
    """Garde les ascensions dont la cotation est dans la fourchette. Une cotation « entre deux »
    (7a/+) compte comme son niveau avant le slash."""
    # Bornes déjà validées par parse_filters ; une borne vide = pas de limite de ce côté
    i_min = GRADE_ORDER.index(cot_min) if cot_min else None
    i_max = GRADE_ORDER.index(cot_max) if cot_max else None
    if i_min is None and i_max is None:
        return rows
    # Min et max saisis à l'envers : on les remet dans l'ordre plutôt que de ne rien trouver
    if i_min is not None and i_max is not None and i_min > i_max:
        i_min, i_max = i_max, i_min
    kept = []
    for a in rows:
        # Sans cotation reconnue (gi < 0) : écartée dès qu'une borne est donnée
        gi = grade_index(effective_cotation(a) or '')
        if gi < 0 or (i_min is not None and gi < i_min) or (i_max is not None and gi > i_max):
            continue
        kept.append(a)
    return kept


def _sort_key(tri):
    """Fonction de clé pour `sorted` selon le tri demandé (date, cotation, style, beauté, hauteur, nom).

    Les valeurs absentes sont remplacées par une valeur neutre (texte vide, 0, ou 99 pour un style
    inconnu) afin de ne jamais comparer None avec un nombre.
    """
    def key(a):
        if tri in ('date_desc', 'date_asc'):
            return a['date'] or ''
        if tri in ('cotation_desc', 'cotation_asc'):
            return grade_rank(effective_cotation(a) or '')
        if tri in ('style_asc', 'style_desc'):
            st = a['style'] or ''
            return STYLE_ORDER.index(st) if st in STYLE_ORDER else 99
        if tri in ('beaute_desc', 'beaute_asc'):
            return a['note_beaute'] or 0
        if tri in ('hauteur_desc', 'hauteur_asc'):
            return a['hauteur'] or 0
        if tri == 'nom':
            return sort_name_key(a['nom'])
        return ''
    return key


def search(conn, uid, f):
    """Ascensions correspondant aux critères, triées, sous forme de dictionnaires."""
    sql, params = _build_query(uid, f)
    # La cotation se filtre en Python (voir _within_grade_range), puis on trie
    rows = _within_grade_range(conn.execute(sql, params).fetchall(), f['cot_min'], f['cot_max'])
    rows = sorted(rows, key=_sort_key(f['tri']), reverse=f['tri'] in DESCENDING_SORTS)
    results = []
    for a in rows:
        d = dict(a)
        d['date_fmt'] = fmt_date(d.get('date'))
        results.append(d)
    return results


# ─── Présentation des résultats ──────────────────────────────────────────────

def summarize(results):
    """Synthèse : nombre de résultats, de sites, cotation max, mètres.

    Pour une grande voie sans hauteur saisie, on prend la somme de ses longueurs. Les mètres sont
    renvoyés en entier s'ils tombent juste, sinon arrondis à une décimale.
    """
    sites = {a['site_id'] for a in results if a['site_id']}
    best = max_grade([effective_cotation(a) for a in results if effective_cotation(a)])
    metres = 0.0
    for a in results:
        h = a['hauteur']
        if not h and a['type'] in GV_TYPES:
            h = a['hauteur_longueurs']
        metres += h or 0
    return {'count': len(results), 'sites': len(sites), 'max': best,
            'metres': int(metres) if metres == int(metres) else round(metres, 1)}


def group_by_site(results):
    """Résultats regroupés par site, dans l'ordre du tri (le site du premier résultat passe en premier)."""
    groups, index = [], {}
    for a in results:
        # Les ascensions sans site (id vide) sont regroupées sous la clé 0 (« Sans site »)
        key = a['site_id'] or 0
        if key not in index:
            index[key] = {
                'site': a['site_name'] or 'Sans site',
                'lieu': ' › '.join(x for x in (a['pays_name'], a['departement_name'], a['localisation_name']) if x),
                'items': [],
            }
            groups.append(index[key])
        index[key]['items'].append(a)
    return groups


def filter_options(conn, uid):
    """Valeurs proposées dans les filtres : types de roche / de grimpe, ouvreurs et topos déjà saisis."""
    def tag_values(cat):
        # Choix de cette catégorie réellement utilisés sur au moins une ascension de l'utilisateur
        return [r['nom'] for r in conn.execute(
            """SELECT DISTINCT t.nom FROM ascension_tag t JOIN ascension a ON a.id = t.ascension_id
               WHERE a.user_id=? AND t.categorie=? ORDER BY t.nom COLLATE NOCASE""", (uid, cat)).fetchall()]

    def distinct(column):
        # Valeurs distinctes non vides de la colonne (le nom de colonne vient du code, pas de l'utilisateur)
        return [r[0] for r in conn.execute(
            f"SELECT DISTINCT {column} FROM ascension WHERE user_id=? AND {column} IS NOT NULL AND {column}<>'' "
            f"ORDER BY {column} COLLATE NOCASE", (uid,)).fetchall()]

    return {
        'roche': tag_values('roche'),
        'tgrimpe': tag_values('grimpe'),
        'ouvreurs': distinct('ouvreur'),
        'topos': distinct('topo_nom'),
    }


# ─── Calendrier ──────────────────────────────────────────────────────────────

def build_calendar(conn, uid, month_param, selected_dates):
    """Calendrier mensuel : jours ayant au moins un log (cliquables) et jours déjà sélectionnés.

    Sans mois demandé, on ouvre le mois du log le plus récent (sinon le mois courant).
    """
    # Jours où il y a au moins un log : seuls ceux-là seront cliquables dans le calendrier
    dates_with_data = {r['date'] for r in conn.execute(
        "SELECT DISTINCT date FROM ascension WHERE user_id=? AND statut='log' AND date IS NOT NULL ORDER BY date", (uid,))}

    # Mois affiché : celui demandé (« AAAA-MM »), sinon celui du dernier log, sinon le mois courant
    today = date.today()
    year, month = today.year, today.month
    if month_param:
        try:
            year, month = map(int, month_param.split('-'))
            if not 1 <= month <= 12:
                raise ValueError
        except ValueError:
            year, month = today.year, today.month
    elif dates_with_data:
        latest = max(dates_with_data)
        year, month = int(latest[:4]), int(latest[5:7])

    calendar_module.setfirstweekday(0)  # lundi
    # `monthcalendar` renvoie des semaines de 7 jours ; 0 = case vide (jour d'un autre mois)
    weeks = []
    for week in calendar_module.monthcalendar(year, month):
        days = []
        for day in week:
            if day == 0:
                days.append(None)
                continue
            iso = f"{year:04d}-{month:02d}-{day:02d}"
            days.append({'day': day, 'date': iso, 'has_data': iso in dates_with_data, 'selected': iso in selected_dates})
        weeks.append(days)

    # Mois précédent / suivant pour les flèches, avec passage d'une année à l'autre
    prev_month = f"{year - 1}-12" if month == 1 else f"{year}-{month - 1:02d}"
    next_month = f"{year + 1}-01" if month == 12 else f"{year}-{month + 1:02d}"
    return {'weeks': weeks, 'month_name': MONTH_NAMES[month - 1], 'year': year, 'month': month,
            'prev_month': prev_month, 'next_month': next_month}
