# Modèle de données

La base est un fichier SQLite (`carnet.db`) créé et mis à jour par `src/schema.py`. Ce document décrit les 18 tables, leurs liens, les valeurs autorisées et les migrations. Pour les règles qui s'appliquent à ces données, voir [FONCTIONNALITES.md](FONCTIONNALITES.md).

## Sommaire

1. [Schéma général](#schéma-général)
2. [Les lieux](#les-lieux)
3. [L'ascension](#lascension)
4. [Tables dépendant d'une ascension](#tables-dépendant-dune-ascension)
5. [Listes de choix (tags)](#listes-de-choix-tags)
6. [Valeurs autorisées](#valeurs-autorisées)
7. [Intégrité des données](#intégrité-des-données)
8. [Migrations](#migrations)
9. [Requêtes types](#requêtes-types)

---

## Schéma général

```
user
 └── pays (user_id)
      └── departement (pays_id)
           └── localisation (departement_id)
                └── site (localisation_id)
                     └── secteur (site_id)            ← porte un « ressenti » facultatif
                          └── sous_secteur (secteur_id)   ← facultatif, porte aussi un « ressenti »

user ──< ascension (user_id) >── secteur (secteur_id)
                              >── sous_secteur (sous_secteur_id, facultatif)

ascension ──< longueur          (grandes voies : une ligne par longueur)
          ──< repetition        (voie déjà loguée refaite)
          ──< seance            (séances de travail d'un projet)
          ──< reequipement      (rééquipé par … en …)
          ──< ascension_tag     (choix : roche, type de grimpe, fixations, coinceurs)

user ──< tag_option             (listes de propositions de l'utilisateur)
user ──< tag_seed               (trace du remplissage initial des listes)
```

`──<` se lit « a plusieurs ». Il n'y a **pas** de table de lieux commune à tous les comptes : chaque utilisateur a ses propres pays, départements, etc.

## Les lieux

Six niveaux emboîtés. Chaque niveau pointe vers son parent. Le nom doit être **unique chez un même parent** (contrainte `UNIQUE`), ce qui évite deux « Cengle » dans la même localisation mais autorise un « Cengle » dans une autre.

| Table | Colonnes | Unicité |
|---|---|---|
| `pays` | `id`, `user_id` → `user`, `name` | `(user_id, name)` |
| `departement` | `id`, `pays_id` → `pays`, `name` | `(pays_id, name)` |
| `localisation` | `id`, `departement_id` → `departement`, `name` | `(departement_id, name)` |
| `site` | `id`, `localisation_id` → `localisation`, `name` | `(localisation_id, name)` |
| `secteur` | `id`, `site_id` → `site`, `name`, `ressenti` | `(site_id, name)` |
| `sous_secteur` | `id`, `secteur_id` → `secteur`, `name`, `ressenti` | `(secteur_id, name)` |

Particularités :

- **Seul le pays porte `user_id`.** L'appartenance d'un niveau inférieur à un utilisateur se vérifie en remontant jusqu'au pays (`geo.geo_owned`).
- **Le sous-secteur est facultatif.** Une ascension est toujours rattachée à un secteur, et en plus à un sous-secteur s'il y en a un.
- **Valeurs par défaut à la saisie** : une localisation vide devient « Principale », un secteur vide « Principal » (`geo.normalize_geo_payload`), pour qu'une ascension ait toujours une chaîne complète.
- **`ressenti`** : repère indicatif laissé par l'utilisateur (voir [valeurs autorisées](#valeurs-autorisées)). Il s'applique au sous-secteur s'il y en a un, sinon au secteur. Il n'entre dans aucun calcul.
- **Nommage** : le niveau « localisation » s'appelait « falaise » dans une ancienne version ; la migration `_rename_falaise_to_localisation` renomme la table et la colonne `site.falaise_id`.

## L'ascension

Table centrale : **une ligne = une voie ou un bloc**, quel que soit son statut. Le `statut` détermine la page où elle apparaît.

| Colonne | Type | Rôle |
|---|---|---|
| `id` | INTEGER, clé | identifiant |
| `user_id` | INTEGER, obligatoire | propriétaire |
| `secteur_id` | INTEGER | secteur (obligatoire en pratique, rempli par `resolve_location`) |
| `sous_secteur_id` | INTEGER | sous-secteur, si présent |
| `type` | TEXT, obligatoire | `bloc`, `voie`, `grande_voie`, `trad_voie`, `trad_gv`, `psychobloc` |
| `statut` | TEXT, défaut `log` | `log` (Carnet), `projet` (Projets), `ticklist` (Tick List) |
| `nom` | TEXT, obligatoire | nom de la voie / du bloc |
| `cotation` | TEXT | cotation (pour une grande voie : cotation **basse**) |
| `cotation_haute` | TEXT | grandes voies : cotation haute (passage le plus dur) |
| `cotation_perso` | TEXT | ressenti de l'utilisateur (« ma cotation ») |
| `style` | TEXT | `a_vue`, `flash`, `essais_1`…`essais_5`, `plus_5` |
| `nb_essais_projet` | INTEGER, défaut 0 | total d'essais d'un projet ; **recalculé** depuis les séances |
| `pieds_nus` | INTEGER (0/1) | grimpé pieds nus |
| `hauteur` | REAL | hauteur en mètres |
| `note_beaute` | INTEGER | note de 1 à 5 étoiles |
| `date` | TEXT | date de réalisation, `AAAA-MM-JJ` |
| `commentaire` | TEXT | texte libre |
| `type_depart` | TEXT | blocs : `normal`, `assis`, `jete`, `run_jump` (vide = normal) |
| `type_arrivee` | TEXT | blocs : `normal` (normal top) ou `reta` (vide = normal) |
| `nb_longueurs` | INTEGER | grandes voies |
| `grimpe` | TEXT | mode de grimpe : `tete` ou `moulinette` |
| `topo_type` | TEXT | `papier`, `pdf` ou NULL |
| `topo_id` | INTEGER | topo PDF choisi dans la bibliothèque (table `topo`), ou NULL ; seulement si `topo_type` = `pdf` |
| `topo_nom`, `topo_edition`, `topo_annee`, `topo_page`, `topo_lien` | TEXT / INTEGER | topo consulté |
| `annee_ouverture` | INTEGER | année d'ouverture de la voie |
| `ouvreur` | TEXT | nom de l'ouvreur |
| `envie_categorie` | TEXT | tick list : `performance`, `beaute`, `majeure` ou NULL |

Remarques :

- **Dates** : stockées en texte ISO `AAAA-MM-JJ` (tri alphabétique = tri chronologique). L'affichage JJ/MM/AAAA est fait par le filtre `fmt_date`.
- **Cotation effective** : pour une grande voie (`grande_voie`, `trad_gv`), les calculs de difficulté utilisent `cotation_haute` ; pour les autres types, `cotation` (voir `grades.effective_cotation`).
- **Cotation « entre deux »** : stockée avec un slash dans le même champ (`7a/+` = entre 7a et 7a+, `7a+/b` = entre 7a+ et 7b). Voir [FONCTIONNALITES.md](FONCTIONNALITES.md#cotations).
- **`grimpe` peut être NULL** : obligatoire pour une voie **loguée** sur corde, mais absent pour un bloc, un projet ou une envie, et pour les anciennes ascensions créées avant l'existence du champ.
- **`envie_categorie`** n'est conservée que pour le statut `ticklist`.
- **`pieds_nus`** vaut 0 ou 1 (pas de type booléen en SQLite).

## Tables dépendant d'une ascension

### `longueur` : longueurs d'une grande voie

`id`, `ascension_id`, `numero`, `cotation`, `cotation_perso`, `style`, `pieds_nus`, `hauteur`, `note_beaute`, `grimpe`.

Une ligne par longueur, numérotées dans l'ordre reçu. Quand une grande voie n'a pas de `hauteur` propre, sa hauteur est la **somme des hauteurs de ses longueurs**. À chaque modification de l'ascension, les longueurs sont supprimées puis recréées.

### `repetition` : voie refaite

`id`, `ascension_id`, `date` (obligatoire), `nb_essais` (texte : `1`…`5` ou `plus_5`), `cotation_perso`, `pieds_nus`, `note_beaute`, `commentaire`, `grimpe`.

Une répétition ne crée pas une nouvelle ascension : elle s'ajoute à celle existante. Sa colonne `grimpe` a été ajoutée après coup : les anciennes répétitions ont repris le mode de leur ascension.

### `seance` : séances de travail d'un projet

`id`, `ascension_id`, `numero`, `date` (peut être NULL), `nb_essais` (défaut 0), `commentaire` (« mini-journal »).

Les séances sont numérotées 1, 2, 3… par ascension et **conservées quand le projet est passé au carnet**. Supprimer une séance renumérote les suivantes. `ascension.nb_essais_projet` est toujours égal à la somme des `nb_essais` des séances.

### `reequipement`

`id`, `ascension_id`, `nom`, `annee`, `ordre`.

« Rééquipé par … en … » : plusieurs lignes possibles (maximum 20, `MAX_REEQUIPEMENTS`), l'ordre de saisie est conservé grâce à `ordre`.

## Topos PDF

Deux tables (`_create_topo_tables`).

### `topo` : la bibliothèque de PDF

`id`, `user_id`, `nom` (titre affiché, modifiable), `fichier_nom` (nom d'origine nettoyé), `taille` (octets), `sha256` (empreinte du contenu), `contenu` (BLOB), `date_ajout` ; **unique `(user_id, sha256)`**.

Un même fichier n'existe donc qu'une fois par compte : le renvoyer réutilise la ligne existante. Une nouvelle édition (contenu différent) est une nouvelle ligne. Plusieurs ascensions partagent un topo grâce à `ascension.topo_id`. Le contenu doit commencer par `%PDF-` et faire au plus 20 Mo (`TOPO_PDF_MAX_BYTES`). Les lectures de fiche ne chargent jamais le BLOB, seulement `nom`, `fichier_nom` et `taille`.

### `topo_lieu` : rattachement d'un topo à un lieu

`topo_id`, `niveau` (`localisation`, `site`, `secteur` ou `sous_secteur`, `TOPO_NIVEAUX`), `lieu_id` ; clé primaire sur les trois colonnes.

Créé quand on ajoute un topo depuis le bouton « Topo » d'un lieu ou depuis la fiche d'une ascension (rattaché alors au secteur / sous-secteur de l'ascension). Le bouton « Topo » d'un lieu affiche les topos rattachés à ce lieu **ou en dessous**, plus ceux utilisés par une ascension en dessous (`topo_pdf.topos_du_lieu`).

## Tentatives de connexion

### `auth_attempt` : compteurs anti-abus

| Colonne | Type | Rôle |
|---|---|---|
| `id` | INTEGER | clé |
| `bucket` | TEXT | « seau » compté : `login:pair:<email>\|<ip>`, `login:email:<email>`, `login:ip:<ip>`, `register:ip:<ip>` |
| `ts` | INTEGER | instant de l'événement (secondes Unix) |

Index `idx_auth_attempt(bucket, ts)`. Une ligne = un échec de connexion (ou une inscription). Les lignes de plus de 24 h sont effacées à chaque nouvel enregistrement ; une connexion réussie vide le seau « pair » (`services/ratelimit.py`). Aucune donnée personnelle autre que l'email saisi et l'adresse IP.

## Listes de choix (tags)

Quatre catégories de choix : **type de grimpe**, **type de roche**, **fixations**, **coinceurs**. Trois tables :

| Table | Colonnes | Rôle |
|---|---|---|
| `tag_option` | `id`, `user_id`, `categorie`, `nom` ; unique `(user_id, categorie, nom)` | la **liste de propositions** de l'utilisateur (ce qu'il peut cocher) |
| `tag_seed` | `user_id`, `categorie` ; clé `(user_id, categorie)` | note que la liste de départ a déjà été créée, pour qu'elle ne revienne pas si l'utilisateur supprime tout |
| `ascension_tag` | `id`, `ascension_id`, `categorie`, `nom` ; unique `(ascension_id, categorie, nom)` | les **choix retenus** pour une ascension |

À ne pas confondre : une *proposition* (`tag_option`) est un élément de la liste ; un *choix* (`ascension_tag`) est ce qu'on a coché pour une ascension. Les choix stockent le **texte** : supprimer une proposition de la liste n'efface donc rien sur les ascensions qui l'avaient déjà choisie.

Catégories proposées selon le type d'ascension :

| Catégorie | Types concernés | Propositions de départ |
|---|---|---|
| `grimpe` (type de grimpe) | tous | Mur vertical, Dalle, Léger dévers, Dévers, Toit, Fissure, Traversée, Dièdre, Arête, Cheminée |
| `roche` (type de roche) | tous | Calcaire, Granite, Grès, Gneiss, Conglomérat, Basalte, Quartzite, Rhyolite |
| `fixation` | `voie`, `grande_voie` | Broches, Goujons, Pitons, Spits |
| `coinceur` | `trad_voie`, `trad_gv` | Câblés, Hexagonaux, Friends |

Limites : nom de 40 caractères maximum (`TAG_MAX_LEN`), 60 propositions maximum par catégorie et par utilisateur (`MAX_TAGS_PER_LIST`). Les doublons sont détectés sans tenir compte de la casse.

## Valeurs autorisées

Toutes définies dans `src/constants.py`.

| Colonne | Valeurs | Constante |
|---|---|---|
| `ascension.type` | `bloc`, `voie`, `grande_voie`, `trad_voie`, `trad_gv`, `psychobloc` | `ASCENSION_TYPES` |
| `ascension.statut` | `log`, `projet`, `ticklist` | `STATUTS` |
| `ascension.grimpe`, `repetition.grimpe` | `tete`, `moulinette` | `GRIMPE_MODES` |
| `ascension.style` | `a_vue`, `flash`, `essais_1`, `essais_2`, `essais_3`, `essais_4`, `essais_5`, `plus_5` | `STYLE_ORDER` |
| `ascension.type_depart` | `normal`, `assis` (DA), `jete` (Jeté), `run_jump` (R&J) ; vide = normal | `DEPART_LABELS` (abréviations affichées) |
| `ascension.type_arrivee` | `normal` (normal top), `reta` ; vide = normal | (liste du formulaire) |
| `ascension.envie_categorie` | `performance`, `beaute`, `majeure` | `ENVIE_CATS` |
| `ascension.topo_type` | `papier`, `pdf` | `TOPO_TYPES` |
| `secteur.ressenti`, `sous_secteur.ressenti` | `tres_dur`, `dur`, `juste`, `facile`, `tres_facile` | `RESSENTI_LABELS` |
| `cotation*` | de `3a` à `9c` (avec les `+`), plus l'« entre deux » `7a/+` | `GRADE_ORDER` |

Regroupement des styles pour les graphiques de la page Stats (`STYLE_GROUPS`) : `a_vue` → À vue ; `flash` → Flash ; `essais_1`…`plus_5` → Travaillé.

Types de l'ascension par famille :

| Famille | Types | Utilisée pour |
|---|---|---|
| Grandes voies (`GV_TYPES`) | `grande_voie`, `trad_gv` | cotation basse → haute, longueurs |
| Voies sur corde (`ROPE_TYPES`) | `voie`, `grande_voie`, `trad_voie`, `trad_gv` | mode de grimpe obligatoire pour un log |
| Comptées seulement en tête (`TETE_ONLY_TYPES`) | `voie`, `trad_voie` | règle des stats |

## Intégrité des données

SQLite **n'impose pas** les clés étrangères par défaut, et l'application n'active pas `PRAGMA foreign_keys`. L'intégrité est donc assurée **par le code** :

- supprimer une **ascension** supprime ses répétitions, longueurs, séances, choix et rééquipements (`ascensions.delete_ascensions`) ; elle ne supprime **pas** son topo PDF, que d'autres ascensions peuvent utiliser ;
- supprimer un **lieu** supprime tous ses niveaux enfants, toutes leurs ascensions et les rattachements de topos (`topo_lieu`) de ces lieux ; les topos eux-mêmes restent dans la bibliothèque (`geo.delete_item`) ;
- supprimer un **topo** (`topo_pdf.delete_topo`) met `topo_id` à NULL sur les ascensions qui l'utilisaient et supprime ses rattachements ;
- toute lecture ou écriture filtre sur l'utilisateur (voir [ARCHITECTURE.md](ARCHITECTURE.md#authentification-et-isolation-des-données)) ;
- les écritures sont validées explicitement par `conn.commit()` ; une requête interrompue avant le commit est annulée.

Si tu modifies la base à la main (outil externe), respecte cet ordre de suppression : enfants d'abord, parents ensuite.

## Migrations

`schema.init_db(path)` est **idempotent** : il s'exécute à chaque démarrage et après chaque restauration, sur une base neuve comme sur une base ancienne. Chaque migration vérifie d'abord si elle est nécessaire.

| Migration | Ce qu'elle répare |
|---|---|
| `_rename_falaise_to_localisation` | ancienne table `falaise` → `localisation` ; colonne `site.falaise_id` → `localisation_id` |
| `_migrate_ascension_columns` | ajoute à `ascension` les colonnes apparues après la première version : `cotation_haute`, `sous_secteur_id`, `topo_*`, `annee_ouverture`, `ouvreur`, `envie_categorie` |
| `_migrate_ressenti_columns` | ajoute `ressenti` aux secteurs et sous-secteurs |
| `_migrate_envie_classique_to_majeure` | la catégorie d'envie `classique` devient `majeure` |
| `_create_topo_tables` | crée `topo` et `topo_lieu` si elles manquent |
| `_migrate_topo_fichier` | ancienne table `topo_fichier` (un PDF copié par ascension) → bibliothèque `topo` : un topo par contenu et par compte (les copies identiques sont fusionnées), `ascension.topo_id` renseigné, puis l'ancienne table est supprimée |
| (dans `_create_repetition_table`) | ajoute `repetition.grimpe` et la remplit avec le mode de l'ascension |
| (dans `_create_seance_table`) | un projet qui avait un total d'essais mais aucune séance reçoit une **séance n°1 sans date** portant ce total, pour ne rien perdre de l'ancien compteur |

Pour ajouter une colonne à `ascension` : l'ajouter à la liste `_ASCENSION_EXTRA_COLUMNS` de `schema.py` ; la migration l'ajoutera aux bases existantes.

Les migrations sont testées dans `tests/services/test_schema.py` (création d'anciennes bases, double exécution).

## Requêtes types

Fragments SQL partagés (dans `services/ascensions.py`) : `GEO_JOINS` et `GEO_COLUMNS` joignent d'un coup toute la chaîne de lieux d'une ascension.

Ascensions loguées d'un utilisateur, avec leurs lieux :

```sql
SELECT a.*, p.name AS pays_name, d.name AS departement_name, l.name AS localisation_name,
       si.name AS site_name, s.name AS secteur_name, ss.name AS sous_secteur_name
FROM ascension a
LEFT JOIN secteur s        ON a.secteur_id = s.id
LEFT JOIN site si          ON s.site_id = si.id
LEFT JOIN localisation l   ON si.localisation_id = l.id
LEFT JOIN departement d    ON l.departement_id = d.id
LEFT JOIN pays p           ON d.pays_id = p.id
LEFT JOIN sous_secteur ss  ON a.sous_secteur_id = ss.id
WHERE a.user_id = ? AND a.statut = 'log';
```

Total d'essais d'un projet (ce que fait `sync_essais_projet`) :

```sql
SELECT COALESCE(SUM(nb_essais), 0) FROM seance WHERE ascension_id = ?;
```

Voies loguées sans mode de grimpe (anciennes ascensions, non comptées dans les stats) :

```sql
SELECT nom, type FROM ascension
WHERE user_id = ? AND statut = 'log' AND type IN ('voie', 'trad_voie')
  AND (grimpe IS NULL OR grimpe NOT IN ('tete', 'moulinette'));
```
