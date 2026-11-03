"""Export PDF : résumé statistique + liste complète des ascensions loguées, aux couleurs du site.

Le PDF est construit en mémoire avec reportlab : une première page de résumé (compteurs de lieux,
chiffres par discipline) puis, après un saut de page, le tableau chronologique de tous les logs et
de leurs répétitions. Les chiffres suivent les mêmes règles que la page Stats (stats.py).
"""
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..constants import ASCENSION_TYPES, GV_TYPES, TYPE_LABELS
from .ascensions import GEO_COLUMNS, GEO_JOINS
from .formatting import fmt_date
from .geo import get_geo_counts
from .stats import _height_getter, counts_in_stats
from .grades import alpine_from_classic, effective_cotation, max_grade

# Palette reprise de la feuille de style du site
VERT_SAPIN = colors.HexColor('#1d3b26')
VERT_FORET = colors.HexColor('#2f5233')
ROCHE = colors.HexColor('#4a4a45')
GRIS_CLAIR = colors.HexColor('#f2f2ee')
GRIS_GRILLE = colors.HexColor('#dddddd')


# ─── Données ─────────────────────────────────────────────────────────────────

def _load_data(conn, uid):
    """Logs de l'utilisateur (récents d'abord) et toutes leurs répétitions, avec les noms de lieux."""
    ascensions = conn.execute(f"""
        SELECT a.*, {GEO_COLUMNS}
        FROM ascension a {GEO_JOINS}
        WHERE a.user_id=? AND a.statut='log'
        ORDER BY a.date DESC
    """, (uid,)).fetchall()

    repetitions = []
    if ascensions:
        marks = ','.join('?' for _ in ascensions)
        # Répétitions de ces logs, avec les infos de l'ascension d'origine (nom, type, cotation, lieux)
        repetitions = conn.execute(f"""
            SELECT r.*, a.nom as asc_nom, a.type as asc_type, a.cotation as asc_cotation,
                   sec.name as secteur_name, si.name as site_name, loc.name as localisation_name,
                   ss.name as sous_secteur_name
            FROM repetition r
            JOIN ascension a ON r.ascension_id = a.id
            LEFT JOIN secteur sec ON a.secteur_id = sec.id
            LEFT JOIN site si     ON sec.site_id   = si.id
            LEFT JOIN localisation loc ON si.localisation_id = loc.id
            LEFT JOIN sous_secteur ss ON a.sous_secteur_id = ss.id
            WHERE r.ascension_id IN ({marks})
        """, [a['id'] for a in ascensions]).fetchall()
    return ascensions, repetitions


def _per_type_summary(conn, ascensions, repetitions):
    """Par discipline : nombre, mètres et cotation max ; plus mètres et cotation max globaux.

    Même règle que la page Stats : voies et trad (voie) ne comptent que s'ils sont grimpés en tête
    (ascensions comme répétitions). La liste chronologique du PDF, elle, montre tout."""
    per_type, all_cotations, total_metres = {}, [], 0
    asc_height = _height_getter(conn)
    for t in ASCENSION_TYPES:
        # Seules les ascensions qui comptent dans les stats (voie / trad en tête uniquement)
        ascs = [a for a in ascensions if a['type'] == t and counts_in_stats(t, a['grimpe'])]

        # Mètres : comme la page Stats, la hauteur de chaque ascension (ou la somme des longueurs d'une
        # grande voie sans hauteur) est comptée une fois, puis à nouveau pour chaque répétition.
        reps_count = {}
        for r in repetitions:
            if not counts_in_stats(t, r['grimpe']):
                continue
            reps_count[r['ascension_id']] = reps_count.get(r['ascension_id'], 0) + 1
        metres = sum(asc_height(a) * (1 + reps_count.get(a['id'], 0)) for a in ascs)

        cotations = [effective_cotation(a) for a in ascs if effective_cotation(a)]
        all_cotations.extend(cotations)
        per_type[t] = {'nb': len(ascs), 'metres': round(metres, 1), 'cot_max': max_grade(cotations)}
        total_metres += metres
    return per_type, max_grade(all_cotations), total_metres


def _chronological_rows(ascensions, repetitions):
    """Ascensions et répétitions fusionnées en une seule liste, de la plus récente à la plus ancienne."""
    def lieu(row):
        # Chemin lisible « localisation › site › secteur › sous-secteur » (niveaux vides ignorés)
        return ' › '.join(filter(None, [row['localisation_name'], row['site_name'],
                                        row['secteur_name'], row['sous_secteur_name']]))

    combined = []
    for a in ascensions:
        # Grande voie : « cotation basse → cotation haute (alpine) » ; sinon la cotation seule
        if a['type'] in GV_TYPES and a['cotation_haute']:
            alpine = alpine_from_classic(a['cotation_haute'])
            cot_display = f"{a['cotation']} → {a['cotation_haute']}" + (f" ({alpine})" if alpine else '')
        else:
            cot_display = a['cotation'] or '—'
        combined.append({'date': a['date'], 'type': a['type'], 'nom': a['nom'],
                         'cotation': cot_display, 'lieu': lieu(a), 'repetition': False})
    # Une répétition affiche la cotation perso de ce jour-là si elle existe, sinon celle de la voie
    for r in repetitions:
        combined.append({'date': r['date'], 'type': r['asc_type'], 'nom': r['asc_nom'],
                         'cotation': r['cotation_perso'] or r['asc_cotation'] or '—',
                         'lieu': lieu(r), 'repetition': True})
    combined.sort(key=lambda x: x['date'] or '', reverse=True)
    return combined


# ─── Mise en page ────────────────────────────────────────────────────────────

def _styles():
    """Styles de texte du PDF (titre, sous-titre, titre de section, texte des cellules de tableau)."""
    base = getSampleStyleSheet()
    return {
        'base': base,
        'title': ParagraphStyle('TitleCustom', parent=base['Title'], textColor=VERT_SAPIN, fontSize=26, spaceAfter=4),
        'subtitle': ParagraphStyle('Subtitle', parent=base['Normal'], textColor=ROCHE, fontSize=11, spaceAfter=20),
        'h2': ParagraphStyle('H2Custom', parent=base['Heading2'], textColor=VERT_FORET, fontSize=15,
                             spaceBefore=18, spaceAfter=8),
        'cell': ParagraphStyle('CellText', parent=base['Normal'], fontSize=8.5, leading=10.5),
    }


def _summary_table(counts):
    """Tableau « Résumé » : nombre de pays, départements, localisations, sites, secteurs, sous-secteurs."""
    data = [
        ['Pays', 'Départements', 'Localisations', 'Sites', 'Secteurs', 'Sous-secteurs'],
        [str(counts['nb_pays']), str(counts['nb_departements']), str(counts['nb_localisations']),
         str(counts['nb_sites']), str(counts['nb_secteurs']), str(counts['nb_sous_secteurs'])],
    ]
    table = Table(data, colWidths=[2.7 * cm] * 6)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), VERT_SAPIN),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, GRIS_GRILLE),
    ]))
    return table


def _discipline_table(per_type):
    """Tableau « Par discipline » : nombre, mètres et cotation max ; les disciplines vides sont omises."""
    data = [['Discipline', 'Ascensions', 'Mètres', 'Max']]
    for t in ASCENSION_TYPES:
        d = per_type[t]
        if d['nb'] > 0:
            data.append([TYPE_LABELS[t], str(d['nb']), f"{d['metres']}m", d['cot_max'] or '—'])
    table = Table(data, colWidths=[5 * cm, 3.5 * cm, 3.5 * cm, 3.5 * cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), VERT_FORET),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, GRIS_GRILLE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRIS_CLAIR]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
    ]))
    return table


def _list_table(rows, cell_style):
    """Tableau chronologique des ascensions et répétitions (la ligne d'en-tête se répète à chaque page)."""
    data = [['Date', 'Type', 'Nom', 'Cotation', 'Lieu']]
    for c in rows:
        nom_html = c['nom'] or ''
        if c['repetition']:
            nom_html += '<br/><font color="#6b4e2a" size="7.5">• répétition</font>'
        data.append([
            fmt_date(c['date']) or '—',
            TYPE_LABELS.get(c['type'], c['type']),
            Paragraph(nom_html, cell_style),
            Paragraph(c['cotation'], cell_style),
            Paragraph(c['lieu'], cell_style),
        ])
    table = Table(data, colWidths=[2.2 * cm, 2.6 * cm, 3.9 * cm, 2.8 * cm, 6.1 * cm], repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), VERT_SAPIN),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.4, GRIS_GRILLE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRIS_CLAIR]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return table


def build_pdf(conn, uid, user_name):
    """PDF du compte en mémoire (BytesIO), prêt à être envoyé à l'utilisateur.

    `user_name` s'affiche sous le titre, avec la date du jour.
    """
    # Données : compteurs de lieux, logs + répétitions, puis chiffres par discipline
    counts = get_geo_counts(conn, uid)
    ascensions, repetitions = _load_data(conn, uid)
    per_type, cot_max_global, total_metres = _per_type_summary(conn, ascensions, repetitions)

    # Page 1 : titre, résumé, totaux et tableau par discipline ; page 2 et suivantes : liste complète
    st = _styles()
    elements = [
        Paragraph("CARNET DE CROIX", st['title']),
        Paragraph(f"Export du {datetime.now().strftime('%d/%m/%Y')} — {user_name}", st['subtitle']),
        Paragraph("Résumé", st['h2']),
        _summary_table(counts),
        Spacer(1, 14),
        Paragraph(
            f"<b>{sum(v['nb'] for v in per_type.values())}</b> ascensions totales &nbsp;•&nbsp; "
            f"<b>{round(total_metres, 1)}m</b> grimpés &nbsp;•&nbsp; "
            f"cotation max : <b>{cot_max_global or '—'}</b>",
            st['base']['Normal']),
        Spacer(1, 14),
        Paragraph("Par discipline", st['h2']),
        _discipline_table(per_type),
        PageBreak(),
        Paragraph("Liste complète des ascensions (répétitions incluses)", st['h2']),
        _list_table(_chronological_rows(ascensions, repetitions), st['cell']),
    ]

    # Écriture dans un tampon mémoire (pas de fichier sur le disque), marges de 1,8 cm
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm)
    doc.build(elements)
    buf.seek(0)
    return buf
