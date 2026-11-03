"""Constantes métier : échelle de cotations, types d'ascension, libellés, listes de choix.

Ce module ne contient que des données de référence, sans logique : il est importé par les routes
(validation des entrées), par les services (stats, recherche, exports, tags…) et, via les routes,
par les templates (listes déroulantes et libellés affichés). Changer une valeur ici change donc
le comportement de toute l'application ; les valeurs stockées en base (ex. 'bloc', 'a_vue') sont
les clés techniques, les libellés français ne servent qu'à l'affichage.
"""

# ─── Cotations ───────────────────────────────────────────────────────────────

# Échelle française complète, de la plus facile à la plus dure. L'ORDRE de la liste sert à comparer
# deux cotations (position = difficulté) : tris, filtres min/max de la Recherche, stats par niveau
# et listes déroulantes des formulaires (via `grades=GRADE_ORDER` dans routes/pages.py).
GRADE_ORDER = [
    '3a', '3a+', '3b', '3b+', '3c', '3c+',
    '4a', '4a+', '4b', '4b+', '4c', '4c+',
    '5a', '5a+', '5b', '5b+', '5c', '5c+',
    '6a', '6a+', '6b', '6b+', '6c', '6c+',
    '7a', '7a+', '7b', '7b+', '7c', '7c+',
    '8a', '8a+', '8b', '8b+', '8c', '8c+',
    '9a', '9a+', '9b', '9b+', '9c'
]

# Correspondance cotation alpine <-> cotation technique (passage obligé).
# Chaque ancrage est le seuil BAS de son palier : un palier couvre tout
# l'intervalle jusqu'au prochain ancrage (ex : AD- couvre 4a et 4a+).
# Utilisé par services/grades.py (fonction `alpine_from_classic`, filtre de template `alpine_grade`)
# pour afficher la cotation alpine des grandes voies. Liste de couples (cotation alpine, cotation technique).
ALPINE_ANCHORS = [
    ('F',    '2'),   # hors échelle GRADE_ORDER (plus facile que 3a)
    ('PD',   '3a'),
    ('AD-',  '4a'),
    ('AD',   '4b'),
    ('AD+',  '4c'),
    ('D-',   '5a'),
    ('D',    '5b'),
    ('D+',   '5c'),
    ('TD-',  '6a'),
    ('TD',   '6b'),
    ('TD+',  '6c'),
    ('ED-',  '7a'),
    ('ED',   '7b'),
    ('ED+',  '7c'),
    ('ABO-', '8a'),
    ('ABO',  '8b'),
    ('ABO+', '8c'),
]

# ─── Ascensions ──────────────────────────────────────────────────────────────

# Types d'ascension acceptés (colonne `ascension.type`) ; toute autre valeur est refusée par les routes.
# psychobloc = bloc au-dessus de l'eau ; trad_* = escalade en équipement mobile (coinceurs).
ASCENSION_TYPES = ('bloc', 'voie', 'grande_voie', 'trad_voie', 'trad_gv', 'psychobloc')
GV_TYPES = ('grande_voie', 'trad_gv')                              # grandes voies (cotation basse → haute)
ROPE_TYPES = ('voie', 'grande_voie', 'trad_voie', 'trad_gv')       # types où l'on précise « en tête / moulinette »
# Statuts d'une ascension (colonne `ascension.statut`) : 'log' = réalisée (apparaît dans le Carnet et les
# stats), 'projet' = essayée sans être terminée (page Projets), 'ticklist' = simple envie (page Tick List).
STATUTS = ('log', 'projet', 'ticklist')

# Dans les stats (et le résumé du PDF), les voies et le trad (voie) ne comptent que les ascensions grimpées
# « en tête » ; les grandes voies sont toujours comptées, quel que soit le mode.
TETE_ONLY_TYPES = ('voie', 'trad_voie')

# Valeurs possibles de `grimpe` (mode de grimpe) ; obligatoire pour les types de ROPE_TYPES quand l'ascension est loguée.
GRIMPE_MODES = ('tete', 'moulinette')
# Message d'erreur renvoyé (400) quand le mode de grimpe manque.
GRIMPE_REQUIRED_MSG = "Indique si c'est grimpé en tête ou en moulinette."

# Nombre d'essais (style) : ordre du plus facile au plus travaillé.
STYLE_ORDER = ['a_vue', 'flash', 'essais_1', 'essais_2', 'essais_3', 'essais_4', 'essais_5', 'plus_5']
# Libellés affichés pour chaque style (les clés sont celles stockées en base dans `ascension.style`).
STYLE_LABELS = {
    'a_vue': 'À vue', 'flash': 'Flash',
    'essais_1': '1 essai', 'essais_2': '2 essais', 'essais_3': '3 essais',
    'essais_4': '4 essais', 'essais_5': '5 essais', 'plus_5': '+5 essais',
}
# Regroupement des styles détaillés en 3 catégories (graphiques de la page Stats)
STYLE_GROUPS = {
    'a_vue': 'a_vue',
    'flash': 'flash',
    'essais_1': 'travaille', 'essais_2': 'travaille', 'essais_3': 'travaille',
    'essais_4': 'travaille', 'essais_5': 'travaille', 'plus_5': 'travaille',
}

# Libellé unique de chaque type d'ascension, utilisé sur toutes les pages et dans le PDF.
TYPE_LABELS = {
    'bloc': 'Bloc', 'voie': 'Voie', 'grande_voie': 'Grande Voie',
    'trad_voie': 'Trad', 'trad_gv': 'Trad GV', 'psychobloc': 'Psychobloc',
}

# Type de départ d'un bloc (colonne `type_depart`) : assis (DA), jeté, run & jump.
DEPART_LABELS = {'assis': 'DA', 'jete': 'Jeté', 'run_jump': 'R&J'}

# Tick list : pourquoi on veut grimper cette voie (une seule catégorie par envie, facultative)
ENVIE_CATS = {'performance': 'Performance', 'beaute': 'Beauté', 'majeure': 'Majeure'}

# Ressenti indicatif de cotation d'un secteur ou sous-secteur (informatif, non utilisé
# dans les calculs de stats : juste un repère laissé par l'utilisateur)
RESSENTI_LABELS = {
    'tres_dur':    'Coté très difficilement',
    'dur':         'Coté difficilement',
    'juste':       'Bien coté',
    'facile':      'Coté facilement',
    'tres_facile': 'Coté très facilement',
}

# ─── Lieux ───────────────────────────────────────────────────────────────────

# Niveaux de la hiérarchie géographique (de haut en bas). Sert aussi de liste blanche dans routes/api_geo.py :
# le nom de table vient de l'URL et n'est accepté que s'il figure ici (protection contre l'injection SQL).
GEO_TABLES = ('pays', 'departement', 'localisation', 'site', 'secteur', 'sous_secteur')

# ─── « Plus d'informations » ─────────────────────────────────────────────────

# Catégories de choix de la fenêtre « Plus d'informations » (services/tags.py et services/infos.py) :
# libellé affiché, types d'ascension concernés (None = tous), propositions de départ créées pour chaque nouvel utilisateur.
TAG_CATS = {
    'fixation': {'label': 'Fixations', 'types': ('voie', 'grande_voie'),
                 'defaults': ['Broches', 'Goujons', 'Pitons', 'Spits']},
    'coinceur': {'label': 'Coinceurs', 'types': ('trad_voie', 'trad_gv'),
                 'defaults': ['Câblés', 'Hexagonaux', 'Friends']},
    'roche':    {'label': 'Type de roche', 'types': None,
                 'defaults': ['Calcaire', 'Granite', 'Grès', 'Gneiss', 'Conglomérat', 'Basalte', 'Quartzite', 'Rhyolite']},
    'grimpe':   {'label': 'Type de grimpe', 'types': None,
                 'defaults': ['Mur vertical', 'Dalle', 'Léger dévers', 'Dévers', 'Toit', 'Fissure', 'Traversée',
                              'Dièdre', 'Arête', 'Cheminée']},
}
TAG_ORDER = ['grimpe', 'roche', 'fixation', 'coinceur']   # ordre d'affichage dans la fenêtre
TAG_MAX_LEN = 40            # longueur maximale du nom d'une proposition
MAX_TAGS_PER_LIST = 60      # nombre maximal de propositions par catégorie et par utilisateur

# Type de topo consulté (colonne `ascension.topo_type`).
TOPO_TYPES = ('papier', 'pdf')
# Colonnes de `ascension` éditées par la fenêtre « Plus d'informations » (topo + ouverture de la voie).
TOPO_FIELDS = ('topo_type', 'topo_nom', 'topo_edition', 'topo_annee', 'topo_page', 'topo_lien', 'topo_id',
               'annee_ouverture', 'ouvreur')
MAX_REEQUIPEMENTS = 20      # nombre maximal de rééquipements enregistrés pour une voie

# Topos PDF enregistrés dans le site (bibliothèque : table `topo`) : taille maximale d'un fichier, en octets (20 Mo).
TOPO_PDF_MAX_BYTES = 20 * 1024 * 1024
# Niveaux de lieux qui ont un bouton « Topo » (pas le pays ni le département : un topo couvre un site, pas un pays).
TOPO_NIVEAUX = ('localisation', 'site', 'secteur', 'sous_secteur')
TOPO_TITRE_MAX = 150        # longueur maximale du titre d'un topo de la bibliothèque


# ─── Sécurité : limites de tentatives (compteurs en base, voir services/ratelimit.py) ───
PASSWORD_MIN, PASSWORD_MAX = 8, 128
NAME_MAX_LEN, EMAIL_MAX_LEN = 100, 254
LOGIN_PAIR_MAX, LOGIN_IP_MAX, LOGIN_EMAIL_MAX, LOGIN_WINDOW = 5, 50, 100, 15 * 60   # échecs par fenêtre de 15 min
REGISTER_IP_MAX, REGISTER_WINDOW = 50, 60 * 60        # inscriptions par heure et par adresse IP
REGISTER_MIN_SECONDS, REGISTER_MAX_SECONDS = 2, 6 * 3600   # formulaire d'inscription : ni trop rapide ni trop vieux
TOO_MANY_MSG = "Trop de tentatives. Réessayez dans quelques minutes."
