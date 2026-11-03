"""Pages de l'application : Carnet, Projets, Tick List, Recherche, Stats.

Ces routes renvoient du HTML (templates Jinja dans templates/pages). Elles préparent les données avec les
services puis les passent au template ; les listes de référence (cotations, libellés) viennent de constants.py.
Les modifications de données passent ensuite par les API JSON (fichiers api_*.py), appelées par le JavaScript.
"""
from flask import Blueprint, redirect, render_template, request

from ..auth import current_user_id, login_required
from ..constants import (ASCENSION_TYPES, GRADE_ORDER, ENVIE_CATS, RESSENTI_LABELS, STYLE_LABELS,
                         TYPE_LABELS)
from ..db import get_db
from ..services import carnet as carnet_service
from ..services import geo as geo_service
from ..services import projets as projets_service
from ..services import recherche as recherche_service
from ..services import stats as stats_service
from ..services import ticklist as ticklist_service

bp = Blueprint('pages', __name__)


@bp.route('/')
@login_required
def home():
    """Accueil : renvoie vers le Carnet."""
    return redirect('/carnet')


@bp.route('/carnet')
@login_required
def carnet():
    """Page Carnet : arbre des lieux (pays > … > secteur) avec leurs ascensions loguées.
    Paramètre d'URL facultatif `open_secteur` : id d'un secteur à déplier d'office (après un ajout)."""
    conn, uid = get_db(), current_user_id()
    tree = carnet_service.build_carnet_tree(conn, uid)

    # Chemin à ouvrir automatiquement après un ajout
    open_path = {}
    open_secteur = request.args.get('open_secteur')
    if open_secteur:
        try:
            open_path = geo_service.location_path(conn, open_secteur, uid) or {}
        except Exception:   # id invalide ou introuvable : on n'ouvre simplement rien
            open_path = {}
    return render_template('pages/carnet.html', tree=tree, grades=GRADE_ORDER, open_path=open_path,
                           ressenti_labels=RESSENTI_LABELS)


@bp.route('/projets')
@login_required
def projets():
    """Page Projets : voies essayées mais pas encore réussies (statut 'projet'), avec leurs séances."""
    ascensions = projets_service.list_projets(get_db(), current_user_id())
    return render_template('pages/projets.html', ascensions=ascensions, grades=GRADE_ORDER,
                           ressenti_labels=RESSENTI_LABELS)


@bp.route('/ticklist')
@login_required
def ticklist():
    """Page Tick List : voies que l'on veut grimper (statut 'ticklist'), classées par catégorie d'envie."""
    envies = ticklist_service.list_envies(get_db(), current_user_id())
    return render_template('pages/ticklist.html', envies=envies, categories=ENVIE_CATS, grades=GRADE_ORDER,
                           ressenti_labels=RESSENTI_LABELS, type_labels=TYPE_LABELS)


@bp.route('/stats')
@login_required
def stats():
    """Page Stats : graphiques et chiffres calculés sur les ascensions loguées (`**data` = tous les résultats du service)."""
    data = stats_service.compute_stats(get_db(), current_user_id())
    return render_template('pages/stats.html', **data, grades=GRADE_ORDER,
                           types=list(ASCENSION_TYPES), type_labels=TYPE_LABELS)


@bp.route('/recherche')
@login_required
def recherche():
    """Recherche : filtres combinables (barre + pastilles), résultats groupés par site ou à plat.
    La page se met à jour en direct côté navigateur (le même HTML est simplement re-demandé).

    Tous les filtres viennent de l'URL (?q=…&types=…&cot_min=…, `mois` pour le calendrier) et sont lus par
    `parse_filters`. Les variables du template se terminent par `_f` quand elles reprennent la valeur d'un
    filtre, pour pré-remplir les champs de la page.
    """
    conn, uid = get_db(), current_user_id()
    # ─── Filtres, résultats et listes de choix ───
    filters = recherche_service.parse_filters(request.args)
    results = recherche_service.search(conn, uid, filters)
    options = recherche_service.filter_options(conn, uid)
    calendar = recherche_service.build_calendar(conn, uid, request.args.get('mois', ''), filters['dates'])

    # ─── Passage au template ───
    return render_template('pages/recherche.html',
        ascensions=results,
        groupes=recherche_service.group_by_site(results) if filters['groupe'] == 'site' else [],
        summary=recherche_service.summarize(results),
        tri=filters['tri'], groupe=filters['groupe'], statut_f=filters['statut'],
        types_f=filters['types'], styles_f=filters['styles'], beautes_f=filters['beautes'], dates_f=filters['dates'],
        roches_f=filters['roches'], tgrimpes_f=filters['tgrimpes'], modes_f=filters['modes'],
        cot_min_f=filters['cot_min'], cot_max_f=filters['cot_max'],
        hauteur_min_f=filters['hauteur_min'], hauteur_max_f=filters['hauteur_max'],
        pieds_nus_f=filters['pieds_nus'], ouvreur_f=filters['ouvreur'],
        annee_min_f=filters['annee_min'], annee_max_f=filters['annee_max'], topo_f=filters['topo'], q=filters['q'],
        types=list(ASCENSION_TYPES), type_labels=TYPE_LABELS,
        styles=list(STYLE_LABELS), style_labels=STYLE_LABELS,
        roche_options=options['roche'], tgrimpe_options=options['tgrimpe'],
        ouvreur_options=options['ouvreurs'], topo_options=options['topos'],
        calendar_weeks=calendar['weeks'], month_name=calendar['month_name'],
        cal_year=calendar['year'], cal_month=calendar['month'],
        prev_month=calendar['prev_month'], next_month=calendar['next_month'],
        grades=GRADE_ORDER)
