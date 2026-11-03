"""src/services/topo_pdf.py : bibliothèque de topos PDF (un fichier enregistré une seule fois) et contenu du bouton « Topo » des lieux."""
import pytest

from src.constants import TOPO_PDF_MAX_BYTES
from src.errors import NotFoundError, ValidationError
from src.services import ascensions as asc_service
from src.services import geo, infos, topo_pdf
from tests.helpers import add_ascension, scalar

PDF = b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n'
PDF2 = PDF + b'% nouvelle edition\n'
PDF3 = PDF + b'% autre topo\n'


def ids_of(conn, a):
    """Identifiants des lieux d'une ascension : (secteur, site, localisation)."""
    sec = scalar(conn, 'SELECT secteur_id FROM ascension WHERE id=?', a)
    site = scalar(conn, 'SELECT site_id FROM secteur WHERE id=?', sec)
    loc = scalar(conn, 'SELECT localisation_id FROM site WHERE id=?', site)
    return sec, site, loc


def use(conn, a, topo_id):
    """Fait choisir ce topo par l'ascension."""
    conn.execute('UPDATE ascension SET topo_id=? WHERE id=?', (topo_id, a))
    conn.commit()


# ─── Nom de fichier et titre ─────────────────────────────────────────────────

@pytest.mark.parametrize('raw, expected', [
    ('topo.pdf', 'topo.pdf'),
    ('Topo Verdon.PDF', 'Topo Verdon.PDF'),
    ('sans_extension', 'sans_extension.pdf'),
    ('', 'topo.pdf'),
    (None, 'topo.pdf'),
    ('C:\\Users\\moi\\topo.pdf', 'topo.pdf'),
    ('../../etc/passwd', 'passwd.pdf'),
    ('a\x00b\nc.pdf', 'abc.pdf'),
    ('  topo.pdf  ', 'topo.pdf'),
])
def test_clean_filename(raw, expected):
    assert topo_pdf.clean_filename(raw) == expected


def test_clean_filename_is_truncated_and_keeps_extension():
    name = topo_pdf.clean_filename('x' * 500 + '.pdf')
    assert len(name) <= 150 and name.endswith('.pdf')


def test_titre_defaults_to_file_name_without_extension():
    assert topo_pdf.clean_titre(None, 'Verdon 2019.pdf') == 'Verdon 2019'
    assert topo_pdf.clean_titre('   ', 'Verdon.PDF') == 'Verdon'
    assert topo_pdf.clean_titre('  Mon topo ', 'x.pdf') == 'Mon topo'


@pytest.mark.parametrize('titre', [123, 'x' * 151])
def test_titre_rejects_bad_values(titre):
    with pytest.raises(ValidationError):
        topo_pdf.clean_titre(titre, 'x.pdf')


# ─── Validation du contenu ───────────────────────────────────────────────────

def test_validate_accepts_a_pdf_and_leading_garbage():
    topo_pdf.validate_pdf(PDF)
    topo_pdf.validate_pdf(b'\n\r  junk ' + PDF)


@pytest.mark.parametrize('data, message', [
    (b'', 'Aucun fichier reçu.'),
    (None, 'Aucun fichier reçu.'),
    (b'GIF89a not a pdf', "Ce fichier n'est pas un PDF."),
    (b'x' * 2000 + b'%PDF-1.4', "Ce fichier n'est pas un PDF."),
])
def test_validate_rejects_bad_content(data, message):
    with pytest.raises(ValidationError, match=message):
        topo_pdf.validate_pdf(data)


def test_validate_size_limit():
    with pytest.raises(ValidationError, match='dépasse 20 Mo'):
        topo_pdf.validate_pdf(b'%PDF-' + b'0' * TOPO_PDF_MAX_BYTES)
    topo_pdf.validate_pdf(b'%PDF-' + b'0' * (TOPO_PDF_MAX_BYTES - 5))


# ─── Bibliothèque : ajout, doublons, lecture ─────────────────────────────────

def test_add_and_read_roundtrip(conn, uid):
    topo, existait = topo_pdf.add_topo(conn, uid, 'Verdon.pdf', PDF)
    assert existait is False
    assert topo == {'id': topo['id'], 'nom': 'Verdon', 'fichier': 'Verdon.pdf', 'taille': len(PDF), 'nb': 0}
    assert topo_pdf.read_pdf(conn, uid, topo['id']) == ('Verdon.pdf', PDF)


def test_binary_content_is_stored_unchanged(conn, uid):
    data = b'%PDF-1.7\n' + bytes(range(256)) * 10
    topo, _ = topo_pdf.add_topo(conn, uid, 'b.pdf', data)
    assert topo_pdf.read_pdf(conn, uid, topo['id'])[1] == data


def test_custom_title(conn, uid):
    topo, _ = topo_pdf.add_topo(conn, uid, 'x.pdf', PDF, titre='Topo Calanques 2023')
    assert topo['nom'] == 'Topo Calanques 2023'


def test_same_file_is_stored_only_once(conn, uid):
    t1, e1 = topo_pdf.add_topo(conn, uid, 'premier.pdf', PDF)
    t2, e2 = topo_pdf.add_topo(conn, uid, 'autre-nom.pdf', PDF, titre='Autre titre')
    assert (e1, e2) == (False, True)
    assert t1['id'] == t2['id'] and t2['nom'] == 'premier'          # le titre existant est conservé
    assert scalar(conn, 'SELECT COUNT(*) FROM topo') == 1


def test_new_edition_is_a_separate_topo(conn, uid):
    old, _ = topo_pdf.add_topo(conn, uid, 'topo-2019.pdf', PDF)
    new, _ = topo_pdf.add_topo(conn, uid, 'topo-2023.pdf', PDF2)
    assert old['id'] != new['id']
    assert [t['nom'] for t in topo_pdf.list_topos(conn, uid)] == ['topo-2019', 'topo-2023']


def test_same_file_for_two_accounts_is_stored_twice(conn, uid, uid2):
    a, _ = topo_pdf.add_topo(conn, uid, 'topo.pdf', PDF)
    b, existait = topo_pdf.add_topo(conn, uid2, 'topo.pdf', PDF)
    assert a['id'] != b['id'] and existait is False


def test_failed_add_writes_nothing(conn, uid):
    with pytest.raises(ValidationError):
        topo_pdf.add_topo(conn, uid, 'faux.pdf', b'pas un pdf')
    with pytest.raises(ValidationError):
        topo_pdf.add_topo(conn, uid, 'ok.pdf', PDF, titre='x' * 200)
    assert scalar(conn, 'SELECT COUNT(*) FROM topo') == 0


def test_read_unknown_is_not_found(conn, uid):
    with pytest.raises(NotFoundError):
        topo_pdf.read_pdf(conn, uid, 999)


def test_list_counts_ascensions_using_each_topo(conn, uid):
    a, b = add_ascension(conn, uid, 'A'), add_ascension(conn, uid, 'B')
    t, _ = topo_pdf.add_topo(conn, uid, 'topo.pdf', PDF)
    use(conn, a, t['id']); use(conn, b, t['id'])
    assert topo_pdf.list_topos(conn, uid)[0]['nb'] == 2
    assert topo_pdf.get_meta(conn, uid, t['id'])['nb'] == 2


# ─── Renommer, supprimer, isolation ──────────────────────────────────────────

def test_rename(conn, uid):
    t, _ = topo_pdf.add_topo(conn, uid, 'topo.pdf', PDF)
    assert topo_pdf.rename_topo(conn, uid, t['id'], '  Verdon 2023 ') == 'Verdon 2023'
    assert topo_pdf.get_meta(conn, uid, t['id'])['nom'] == 'Verdon 2023'


@pytest.mark.parametrize('titre', ['', '   ', None, 5, 'x' * 151])
def test_rename_rejects_bad_titles(conn, uid, titre):
    t, _ = topo_pdf.add_topo(conn, uid, 'topo.pdf', PDF)
    with pytest.raises(ValidationError):
        topo_pdf.rename_topo(conn, uid, t['id'], titre)
    assert topo_pdf.get_meta(conn, uid, t['id'])['nom'] == 'topo'


def test_delete_detaches_ascensions_but_keeps_them(conn, uid):
    a, b = add_ascension(conn, uid, 'A'), add_ascension(conn, uid, 'B')
    t, _ = topo_pdf.add_topo(conn, uid, 'topo.pdf', PDF)
    other, _ = topo_pdf.add_topo(conn, uid, 'autre.pdf', PDF2)
    use(conn, a, t['id']); use(conn, b, other['id'])
    sec, site, _ = ids_of(conn, a)
    topo_pdf.add_topo(conn, uid, 'topo.pdf', PDF, lieu=('site', site))      # + rattachement à un lieu
    assert topo_pdf.delete_topo(conn, uid, t['id']) == 1
    assert scalar(conn, 'SELECT topo_id FROM ascension WHERE id=?', a) is None
    assert scalar(conn, 'SELECT topo_id FROM ascension WHERE id=?', b) == other['id']
    assert scalar(conn, 'SELECT COUNT(*) FROM topo_lieu') == 0
    assert [x['id'] for x in topo_pdf.list_topos(conn, uid)] == [other['id']]


def test_other_account_cannot_touch_a_topo(conn, uid, uid2):
    t, _ = topo_pdf.add_topo(conn, uid, 'topo.pdf', PDF)
    for call in (lambda: topo_pdf.read_pdf(conn, uid2, t['id']),
                 lambda: topo_pdf.rename_topo(conn, uid2, t['id'], 'x'),
                 lambda: topo_pdf.delete_topo(conn, uid2, t['id'])):
        with pytest.raises(NotFoundError):
            call()
    assert topo_pdf.get_meta(conn, uid2, t['id']) is None
    assert topo_pdf.list_topos(conn, uid2) == []
    assert topo_pdf.get_meta(conn, uid, t['id']) is not None


# ─── Rattachement à un lieu ──────────────────────────────────────────────────

def test_lieu_of_ascension(conn, uid, uid2):
    a = add_ascension(conn, uid, 'A')
    b = add_ascension(conn, uid, 'B', place={'secteur': 'Autre', 'sous_secteur': 'Dalle'})
    sec = scalar(conn, 'SELECT secteur_id FROM ascension WHERE id=?', a)
    assert topo_pdf.lieu_of_ascension(conn, uid, a) == ('secteur', sec)
    assert topo_pdf.lieu_of_ascension(conn, uid, b)[0] == 'sous_secteur'
    with pytest.raises(NotFoundError):
        topo_pdf.lieu_of_ascension(conn, uid2, a)


@pytest.mark.parametrize('niveau', ['pays', 'departement', 'inconnu'])
def test_levels_without_topo_are_refused(conn, uid, niveau):
    a = add_ascension(conn, uid)
    with pytest.raises(ValidationError):
        topo_pdf.add_topo(conn, uid, 't.pdf', PDF, lieu=(niveau, 1))
    with pytest.raises(ValidationError):
        topo_pdf.topos_du_lieu(conn, uid, niveau, 1)
    assert scalar(conn, 'SELECT COUNT(*) FROM topo') == 0


def test_foreign_or_unknown_place_is_not_found(conn, uid, uid2):
    a = add_ascension(conn, uid)
    site = ids_of(conn, a)[1]
    with pytest.raises(NotFoundError):
        topo_pdf.add_topo(conn, uid2, 't.pdf', PDF, lieu=('site', site))
    with pytest.raises(NotFoundError):
        topo_pdf.topos_du_lieu(conn, uid2, 'site', site)
    with pytest.raises(NotFoundError):
        topo_pdf.topos_du_lieu(conn, uid, 'site', 9999)
    assert scalar(conn, 'SELECT COUNT(*) FROM topo') == 0


def test_attaching_twice_does_not_duplicate_the_link(conn, uid):
    a = add_ascension(conn, uid)
    site = ids_of(conn, a)[1]
    topo_pdf.add_topo(conn, uid, 't.pdf', PDF, lieu=('site', site))
    topo_pdf.add_topo(conn, uid, 't.pdf', PDF, lieu=('site', site))
    assert scalar(conn, 'SELECT COUNT(*) FROM topo_lieu') == 1


# ─── Bouton « Topo » d'un lieu ───────────────────────────────────────────────

def build_two_sites(conn, uid):
    """Une localisation avec deux sites ayant chacun son topo, plus un topo sur un 3e site d'une autre localisation."""
    a1 = add_ascension(conn, uid, 'A1', place={'site': 'Site 1', 'secteur': 'S1'})
    a2 = add_ascension(conn, uid, 'A2', place={'site': 'Site 2', 'secteur': 'S2'})
    a3 = add_ascension(conn, uid, 'A3', place={'localisation': 'Ailleurs', 'site': 'Site 3', 'secteur': 'S3'})
    t1, _ = topo_pdf.add_topo(conn, uid, 'topo1.pdf', PDF)
    t2, _ = topo_pdf.add_topo(conn, uid, 'topo2.pdf', PDF2)
    t3, _ = topo_pdf.add_topo(conn, uid, 'topo3.pdf', PDF3)
    use(conn, a1, t1['id']); use(conn, a2, t2['id']); use(conn, a3, t3['id'])
    return (a1, a2, a3), (t1, t2, t3)


def names(res):
    return [t['nom'] for t in res['pdf']]


def test_site_shows_only_its_own_topo_and_localisation_shows_both(conn, uid):
    (a1, a2, a3), _ = build_two_sites(conn, uid)
    sec1, site1, loc = ids_of(conn, a1)
    _, site2, loc2 = ids_of(conn, a2)
    assert loc == loc2
    assert names(topo_pdf.topos_du_lieu(conn, uid, 'site', site1)) == ['topo1']
    assert names(topo_pdf.topos_du_lieu(conn, uid, 'site', site2)) == ['topo2']
    assert names(topo_pdf.topos_du_lieu(conn, uid, 'localisation', loc)) == ['topo1', 'topo2']
    assert names(topo_pdf.topos_du_lieu(conn, uid, 'secteur', sec1)) == ['topo1']


def test_count_is_per_place(conn, uid):
    a1 = add_ascension(conn, uid, 'A1')
    a2 = add_ascension(conn, uid, 'A2')
    a3 = add_ascension(conn, uid, 'A3', place={'secteur': 'Autre'})
    t, _ = topo_pdf.add_topo(conn, uid, 'topo.pdf', PDF)
    for a in (a1, a2, a3):
        use(conn, a, t['id'])
    sec1, site, _ = ids_of(conn, a1)
    assert topo_pdf.topos_du_lieu(conn, uid, 'secteur', sec1)['pdf'][0]['nb'] == 2
    assert topo_pdf.topos_du_lieu(conn, uid, 'site', site)['pdf'][0]['nb'] == 3


def test_one_topo_used_by_many_ascensions_appears_once(conn, uid):
    ids = [add_ascension(conn, uid, f'Bloc {i}') for i in range(5)]
    t, _ = topo_pdf.add_topo(conn, uid, 'topo.pdf', PDF)
    for a in ids:
        use(conn, a, t['id'])
    assert scalar(conn, 'SELECT COUNT(*) FROM topo') == 1
    assert len(topo_pdf.topos_du_lieu(conn, uid, 'secteur', ids_of(conn, ids[0])[0])['pdf']) == 1


def test_old_and_new_edition_both_listed_for_the_place(conn, uid):
    old_a = add_ascension(conn, uid, 'Ancienne', place={'secteur': 'S1'})
    new_a = add_ascension(conn, uid, 'Récente', place={'secteur': 'S2'})
    old, _ = topo_pdf.add_topo(conn, uid, 'topo-2019.pdf', PDF)
    new, _ = topo_pdf.add_topo(conn, uid, 'topo-2023.pdf', PDF2)
    use(conn, old_a, old['id']); use(conn, new_a, new['id'])
    site = ids_of(conn, old_a)[1]
    assert names(topo_pdf.topos_du_lieu(conn, uid, 'site', site)) == ['topo-2019', 'topo-2023']
    # chaque ascension garde son édition
    assert scalar(conn, 'SELECT topo_id FROM ascension WHERE id=?', old_a) == old['id']


def test_sous_secteur_and_secteur_levels(conn, uid):
    a = add_ascension(conn, uid, 'A', place={'sous_secteur': 'Dalle'})
    b = add_ascension(conn, uid, 'B', place={'sous_secteur': 'Toit'})
    t, _ = topo_pdf.add_topo(conn, uid, 'topo.pdf', PDF)
    use(conn, a, t['id'])
    sec = ids_of(conn, a)[0]
    ss_a = scalar(conn, 'SELECT sous_secteur_id FROM ascension WHERE id=?', a)
    ss_b = scalar(conn, 'SELECT sous_secteur_id FROM ascension WHERE id=?', b)
    assert names(topo_pdf.topos_du_lieu(conn, uid, 'sous_secteur', ss_a)) == ['topo']
    assert names(topo_pdf.topos_du_lieu(conn, uid, 'sous_secteur', ss_b)) == []
    assert names(topo_pdf.topos_du_lieu(conn, uid, 'secteur', sec)) == ['topo']


def test_attached_topo_appears_at_its_place_and_above_not_beside(conn, uid):
    (a1, a2, _), _ = build_two_sites(conn, uid)
    sec1, site1, loc = ids_of(conn, a1)
    site2 = ids_of(conn, a2)[1]
    nouveau, _ = topo_pdf.add_topo(conn, uid, 'rattache.pdf', PDF + b'% rattache\n', lieu=('site', site1))
    assert 'rattache' in names(topo_pdf.topos_du_lieu(conn, uid, 'site', site1))
    assert 'rattache' in names(topo_pdf.topos_du_lieu(conn, uid, 'localisation', loc))
    assert 'rattache' not in names(topo_pdf.topos_du_lieu(conn, uid, 'site', site2))     # le site voisin ne le voit pas
    assert 'rattache' not in names(topo_pdf.topos_du_lieu(conn, uid, 'secteur', sec1))   # ni un niveau en dessous
    assert [t['nb'] for t in topo_pdf.topos_du_lieu(conn, uid, 'site', site1)['pdf'] if t['nom'] == 'rattache'] == [0]


def set_topo(conn, nom, **fields):
    """Crée une ascension puis renseigne ses champs de topo (la création n'en reçoit pas : ils viennent de la fiche d'infos)."""
    a = add_ascension(conn, 1, nom)
    infos.update_infos(conn, 1, a, fields)
    return a


def test_papier_and_online_topos_are_listed_and_grouped(conn, uid):
    for nom in ('A', 'B', 'C'):
        set_topo(conn, nom, topo_type='papier', topo_nom='Guide Calanques', topo_edition='2e éd.', topo_annee=2019)
    set_topo(conn, 'D', topo_type='papier', topo_nom='guide calanques', topo_edition='2E ÉD.', topo_annee=2019)
    set_topo(conn, 'E', topo_type='papier', topo_nom='Autre guide')
    set_topo(conn, 'F', topo_type='pdf', topo_nom='Topo web', topo_lien='https://exemple.fr/t.pdf')
    set_topo(conn, 'G', topo_type='pdf')                                 # rien de renseigné : ignoré
    set_topo(conn, 'H', topo_type='papier')                              # papier sans titre
    site = scalar(conn, 'SELECT id FROM site')
    res = topo_pdf.topos_du_lieu(conn, uid, 'site', site)
    papier = {(p['nom'] or '').lower(): p for p in res['papier']}
    assert papier['guide calanques']['nb'] == 4 and papier['guide calanques']['annee'] == 2019
    assert papier['autre guide']['nb'] == 1 and papier['']['nb'] == 1
    assert res['en_ligne'] == [{'nom': 'Topo web', 'lien': 'https://exemple.fr/t.pdf', 'nb': 1}]


def test_pdf_with_library_file_is_not_listed_as_online_link(conn, uid):
    a = set_topo(conn, 'A', topo_type='pdf', topo_nom='Titre', topo_lien='https://exemple.fr/t.pdf')
    t, _ = topo_pdf.add_topo(conn, uid, 'topo.pdf', PDF)
    use(conn, a, t['id'])
    res = topo_pdf.topos_du_lieu(conn, uid, 'site', ids_of(conn, a)[1])
    assert res['en_ligne'] == [] and names(res) == ['topo']


def test_projects_and_wishes_count_too(conn, uid):
    a = add_ascension(conn, uid, 'Projet', statut='projet')
    b = add_ascension(conn, uid, 'Envie', statut='ticklist')
    t, _ = topo_pdf.add_topo(conn, uid, 'topo.pdf', PDF)
    use(conn, a, t['id']); use(conn, b, t['id'])
    assert topo_pdf.topos_du_lieu(conn, uid, 'site', ids_of(conn, a)[1])['pdf'][0]['nb'] == 2


def test_other_accounts_ascensions_never_leak(conn, uid, uid2):
    mine = add_ascension(conn, uid, 'Mien')
    theirs = add_ascension(conn, uid2, 'Leur')
    t, _ = topo_pdf.add_topo(conn, uid2, 'leur.pdf', PDF)
    use(conn, theirs, t['id'])
    assert topo_pdf.topos_du_lieu(conn, uid, 'site', ids_of(conn, mine)[1]) == {'pdf': [], 'papier': [], 'en_ligne': []}


def test_empty_place(conn, uid):
    a = add_ascension(conn, uid)
    assert topo_pdf.topos_du_lieu(conn, uid, 'site', ids_of(conn, a)[1]) == {'pdf': [], 'papier': [], 'en_ligne': []}


# ─── Fiche d'infos ───────────────────────────────────────────────────────────

def test_get_infos_exposes_chosen_topo_and_library(conn, uid):
    a = add_ascension(conn, uid, 'A', place={'site': 'Site 1'})
    b = add_ascension(conn, uid, 'B', place={'site': 'Site 2'})
    local, _ = topo_pdf.add_topo(conn, uid, 'local.pdf', PDF)
    ailleurs, _ = topo_pdf.add_topo(conn, uid, 'ailleurs.pdf', PDF2)
    use(conn, a, local['id']); use(conn, b, ailleurs['id'])
    data = infos.get_infos(conn, uid, a)
    assert data['topo_pdf']['id'] == local['id'] and 'contenu' not in data['topo_pdf']
    assert {t['nom']: t['local'] for t in data['topos']} == {'local': True, 'ailleurs': False}
    assert infos.get_infos(conn, uid, add_ascension(conn, uid, 'C', place={'site': 'Site 3'}))['topo_pdf'] is None


def test_deleting_the_ascension_keeps_the_shared_topo(conn, uid):
    a, b = add_ascension(conn, uid, 'A'), add_ascension(conn, uid, 'B')
    t, _ = topo_pdf.add_topo(conn, uid, 'topo.pdf', PDF)
    use(conn, a, t['id']); use(conn, b, t['id'])
    asc_service.delete_ascensions(conn, [a])
    conn.commit()
    assert scalar(conn, 'SELECT COUNT(*) FROM topo') == 1
    assert scalar(conn, 'SELECT topo_id FROM ascension WHERE id=?', b) == t['id']


def test_deleting_a_place_removes_its_links_but_keeps_the_topo(conn, uid):
    a = add_ascension(conn, uid, 'A', place={'site': 'Site 1'})
    add_ascension(conn, uid, 'B', place={'site': 'Site 2'})
    _, site1, loc = ids_of(conn, a)
    t, _ = topo_pdf.add_topo(conn, uid, 'topo.pdf', PDF, lieu=('site', site1))
    geo.delete_item(conn, uid, 'site', site1)
    assert scalar(conn, 'SELECT COUNT(*) FROM topo_lieu') == 0
    assert scalar(conn, 'SELECT COUNT(*) FROM topo') == 1


def test_deleting_a_whole_localisation_removes_links_of_every_level_below(conn, uid):
    a = add_ascension(conn, uid, 'A', place={'sous_secteur': 'Dalle'})
    sec, site, loc = ids_of(conn, a)
    ss = scalar(conn, 'SELECT sous_secteur_id FROM ascension WHERE id=?', a)
    for i, lieu in enumerate((('sous_secteur', ss), ('secteur', sec), ('site', site), ('localisation', loc))):
        topo_pdf.add_topo(conn, uid, f't{i}.pdf', PDF + bytes([i]), lieu=lieu)
    assert scalar(conn, 'SELECT COUNT(*) FROM topo_lieu') == 4
    geo.delete_item(conn, uid, 'localisation', loc)
    assert scalar(conn, 'SELECT COUNT(*) FROM topo_lieu') == 0


# ─── Cas limites ─────────────────────────────────────────────────────────────

def test_place_without_anything_below_it(conn, uid):
    """Un site sans secteur et une localisation sans site ne plantent pas : listes vides."""
    a = add_ascension(conn, uid)
    loc = ids_of(conn, a)[2]
    vide_loc = conn.execute("INSERT INTO localisation(departement_id, name) VALUES((SELECT departement_id FROM localisation WHERE id=?), 'Vide')", (loc,)).lastrowid
    vide_site = conn.execute("INSERT INTO site(localisation_id, name) VALUES(?, 'Site vide')", (loc,)).lastrowid
    conn.commit()
    empty = {'pdf': [], 'papier': [], 'en_ligne': []}
    assert topo_pdf.topos_du_lieu(conn, uid, 'site', vide_site) == empty
    assert topo_pdf.topos_du_lieu(conn, uid, 'localisation', vide_loc) == empty


def test_same_online_link_is_grouped(conn, uid):
    for nom in ('A', 'B'):
        set_topo(conn, nom, topo_type='pdf', topo_nom='Topo web', topo_lien='https://exemple.fr/t.pdf')
    res = topo_pdf.topos_du_lieu(conn, uid, 'site', scalar(conn, 'SELECT id FROM site'))
    assert res['en_ligne'] == [{'nom': 'Topo web', 'lien': 'https://exemple.fr/t.pdf', 'nb': 2}]


def test_infos_of_an_ascension_in_a_sous_secteur_flags_local_topos(conn, uid):
    a = add_ascension(conn, uid, 'A', place={'sous_secteur': 'Dalle'})
    t, _ = topo_pdf.add_topo(conn, uid, 'topo.pdf', PDF)
    use(conn, a, t['id'])
    assert [x['local'] for x in infos.get_infos(conn, uid, a)['topos']] == [True]


def test_infos_of_an_ascension_without_place(conn, uid):
    a = add_ascension(conn, uid, 'A')
    conn.execute('UPDATE ascension SET secteur_id=NULL WHERE id=?', (a,))
    conn.commit()
    topo_pdf.add_topo(conn, uid, 'topo.pdf', PDF)
    assert [x['local'] for x in infos.get_infos(conn, uid, a)['topos']] == [False]
