# API et routes

Référence de toutes les routes de Carnet de Croix. Le code correspondant est dans `src/routes/` (un fichier par groupe) ; la logique est dans `src/services/`. Pour le fonctionnement général, voir [ARCHITECTURE.md](ARCHITECTURE.md).

## Sommaire

1. [Conventions](#conventions)
2. [Pages HTML](#pages-html)
3. [Comptes](#comptes)
4. [Lieux](#lieux)
5. [Ascensions](#ascensions)
6. [Répétitions](#répétitions)
7. [Séances](#séances)
8. [Informations, listes de choix et noms](#informations-listes-de-choix-et-noms)
9. [Exports, sauvegarde, restauration](#exports-sauvegarde-restauration)
10. [Paramètres de la Recherche](#paramètres-de-la-recherche)
11. [Exemples](#exemples)

---

## Conventions

- **Jeton CSRF** : toute requête `POST`, `PUT`, `PATCH` ou `DELETE` doit porter le jeton de la session (champ de formulaire `csrf_token` ou en-tête `X-CSRF-Token`) ; le navigateur le lit dans `<meta name="csrf-token">` et `static/js/core/csrf.js` l'ajoute à tous les `fetch`. Sans jeton : **400** (JSON `{"error": "Session expirée…"}` pour `/api/…` et `/restore`, page « Session expirée » pour un formulaire).
- **Authentification** : toutes les routes, sauf `/login`, `/register` et `/logout`, exigent une session ouverte. Sans session, la réponse est une **redirection 302 vers `/login`** (y compris pour les routes d'API : ce n'est pas un 401 JSON).
- **Isolation** : chaque route ne voit que les données de l'utilisateur connecté. Une ressource d'un autre compte est traitée comme **inexistante (404)**.
- **Format** : les routes `/api/...` reçoivent et renvoient du **JSON** (`Content-Type: application/json`). Les pages renvoient du HTML ; les exports, des fichiers.
- **Succès** : généralement `{"success": true}` (avec des champs en plus selon la route).
- **Erreurs** : toujours `{"error": "message lisible"}` avec le code HTTP adapté :

| Code | Exception | Signification |
|---|---|---|
| 400 | `ValidationError` | donnée invalide ou manquante (ou jeton CSRF absent) |
| 403 | `ForbiddenError` | action réservée à l'administrateur (`/backup`, `/restore`) |
| 404 | `NotFoundError` | élément inexistant ou appartenant à un autre compte |
| 409 | `ConflictError` | l'élément existe déjà (ex. renommage vers un nom pris) |
| 413 | (Flask) | requête plus grosse que `MAX_CONTENT_LENGTH` (256 Mo) : `{"error": "Fichier trop volumineux."}` |

- **Écritures** : validées par un `commit` ; une requête qui échoue avant le commit n'écrit rien.
- **Dates** : `AAAA-MM-JJ` dans le JSON ; le serveur ajoute des champs `*_fmt` (JJ/MM/AAAA) pour l'affichage quand c'est utile.

## Pages HTML

| Méthode | URL | Description | Paramètres |
|---|---|---|---|
| GET | `/` | redirige vers `/carnet` | — |
| GET | `/carnet` | arbre des ascensions loguées | `open_secteur` : id d'un secteur à déplier d'office |
| GET | `/projets` | projets et séances | — |
| GET | `/ticklist` | envies | — |
| GET | `/stats` | statistiques | — |
| GET | `/recherche` | recherche | voir [Paramètres de la Recherche](#paramètres-de-la-recherche) |

La Recherche est aussi appelée en `fetch` par le navigateur (en-tête `X-Requested-With: fetch`) : la page complète est renvoyée et le JavaScript n'en extrait que `#rcResults`, `#rcSummary` et `#calBox`.

## Comptes

Routes publiques, ce sont des **formulaires HTML classiques** (pas du JSON). En cas d'erreur, la page est ré-affichée avec un message.

| Méthode | URL | Corps (formulaire) | Résultat |
|---|---|---|---|
| GET | `/login` | — | formulaire de connexion |
| POST | `/login` | `email`, `password`, `csrf_token` | succès : session ouverte (nouvelle session), redirection vers `/` ; sinon **un seul** message « Email ou mot de passe incorrect. » (compte inconnu ou mauvais mot de passe) ; **429** « Trop de tentatives… » après 5 échecs en 15 min (par email + IP), 50 par IP ou 100 par email |
| GET | `/register` | — | formulaire d'inscription |
| POST | `/register` | `name`, `email`, `password` (8 à 128 caractères), `csrf_token`, `form_ts` (jeton daté anti-robot), `company_url` (champ piège : doit rester vide) | succès : compte créé, connecté, redirection vers `/` ; sinon 400 avec le message (« Un compte existe déjà avec cet email. », mot de passe trop court, formulaire expiré ou envoyé trop vite…) ; **429** au-delà de 50 inscriptions par heure et par IP ; **403** si les inscriptions sont fermées (`ALLOW_REGISTRATION=0`) |
| POST | `/logout` | `csrf_token` | vide la session, redirige vers `/` (en POST : un lien piégé ne peut pas déconnecter) |

Le mot de passe est stocké haché. La session contient `user_id`, `user_name` et `csrf_token`. Voir [SECURITE.md](SECURITE.md).

## Lieux

Les niveaux sont désignés par un nom de table de la liste blanche `GEO_TABLES` : `pays`, `departement`, `localisation`, `site`, `secteur`, `sous_secteur`. Tout autre nom est refusé (400 « Table non autorisée »).

### Listes en cascade

Servent aux champs avec suggestions du formulaire d'ascension.

| Méthode | URL | Réponse |
|---|---|---|
| GET | `/api/geo/pays` | pays de l'utilisateur, triés par nom |
| GET | `/api/geo/departements/<pays_id>` | départements de ce pays |
| GET | `/api/geo/localisations/<departement_id>` | localisations |
| GET | `/api/geo/sites/<localisation_id>` | sites |
| GET | `/api/geo/secteurs/<site_id>` | secteurs (avec `ressenti`) |
| GET | `/api/geo/sous_secteurs/<secteur_id>` | sous-secteurs (avec `ressenti`) |

Réponse : tableau d'objets (une ligne de la table : `id`, `name`, + colonne parente, + `ressenti` pour secteur/sous-secteur). Si le parent n'existe pas ou n'est pas à l'utilisateur : **tableau vide** (pas d'erreur).

### Renommer

`PUT /api/geo/<table>/<id>`

```json
{"name": "Nouveau nom", "ressenti": "dur"}
```

`ressenti` est facultatif et n'a d'effet que pour `secteur` et `sous_secteur` (valeurs : `tres_dur`, `dur`, `juste`, `facile`, `tres_facile`).

| Code | Cas |
|---|---|
| 200 | `{"success": true}` |
| 400 | table non autorisée, ou nom vide (un nom d'espaces compte comme vide) |
| 404 | élément inconnu ou à un autre utilisateur |
| 409 | `« <nom> » existe déjà à cet endroit.` |

### Supprimer

`DELETE /api/geo/<table>/<id>` : supprime l'élément, **tous ses niveaux enfants et toutes leurs ascensions** (avec répétitions, longueurs, séances, choix, rééquipements). Définitif.

| Code | Cas |
|---|---|
| 200 | `{"success": true}` |
| 400 | table non autorisée |
| 404 | élément inconnu ou à un autre utilisateur |

## Ascensions

### Créer

`POST /api/ascension`

Champs du JSON :

| Champ | Obligatoire | Détail |
|---|---|---|
| `pays`, `departement`, `site` | oui | noms de lieux (créés s'ils n'existent pas) |
| `localisation`, `secteur` | non | défauts « Principale » et « Principal » |
| `sous_secteur` | non | rien n'est créé s'il est vide |
| `ressenti` | non | ressenti indicatif du secteur (ou du sous-secteur s'il y en a un) |
| `type` | oui | `bloc`, `voie`, `grande_voie`, `trad_voie`, `trad_gv`, `psychobloc` |
| `statut` | non | `log` (défaut), `projet`, `ticklist` |
| `nom` | oui | nom de l'ascension |
| `cotation`, `cotation_haute`, `cotation_perso` | non | `cotation_haute` pour les grandes voies |
| `style` | non | `a_vue`, `flash`, `essais_1`…`essais_5`, `plus_5` |
| `grimpe` | **oui si `statut = log` et type sur corde** | `tete` ou `moulinette` |
| `date` | non | `AAAA-MM-JJ` |
| `pieds_nus` | non | booléen |
| `hauteur` | non | mètres |
| `note_beaute` | non | 1 à 5 |
| `commentaire` | non | texte libre |
| `type_depart`, `type_arrivee` | non | blocs : `normal`/`assis`/`jete`/`run_jump` ; `normal`/`reta` |
| `nb_longueurs` | non | grandes voies |
| `longueurs` | non | grandes voies : tableau d'objets `{cotation, cotation_perso, style, pieds_nus, hauteur, note_beaute, grimpe}` (numérotés dans l'ordre reçu) |
| `nb_essais_projet`, `date_seance` | non | statut `projet` : essais déjà faits (0 à 999) et date → **séance n°1** |
| `envie_categorie` | non | statut `ticklist` : `performance`, `beaute`, `majeure` |

Réponses :

| Code | Corps |
|---|---|
| 200 | `{"success": true, "id": 42, "secteur_id": 7}` |
| 200 | **doublon** : `{"success": false, "duplicate": true, "existing": {"id", "statut", "nom", "type", "nb_essais_projet"}}`, rien n'est écrit |
| 400 | `Pays requis.` / `Département requis.` / `Site requis.` / `Type d'ascension invalide.` / `Statut invalide.` / `Indique si c'est grimpé en tête ou en moulinette.` |

### Lire

`GET /api/ascension/<id>` : données complètes pour pré-remplir le formulaire de modification.

```json
{
  "ascension": { "id": 42, "type": "voie", "statut": "log", "nom": "…", "cotation": "6c", "…": "…",
                 "pays_name": "France", "departement_name": "…", "localisation_name": "…",
                 "site_name": "…", "secteur_name": "…", "sous_secteur_name": null, "ressenti": "juste" },
  "longueurs": [ { "numero": 1, "cotation": "6a", "…": "…" } ]
}
```

404 si l'ascension n'existe pas ou n'est pas à l'utilisateur.

### Modifier

`PUT /api/ascension/<id>` : mêmes champs que la création (le **type** et le **statut** ne changent pas). Les longueurs sont supprimées puis recréées. Le mode de grimpe n'est exigé que si l'ascension est un `log` d'un type sur corde.

| Code | Cas |
|---|---|
| 200 | `{"success": true}` |
| 400 | lieu invalide, mode de grimpe manquant |
| 404 | ascension inconnue ou à un autre utilisateur |

### Supprimer

`DELETE /api/ascension/<id>` : supprime l'ascension, ses longueurs, répétitions, séances, choix et rééquipements. 200 `{"success": true}` ; 404 si inconnue.

### Changements de statut

| Méthode et URL | Rôle | Corps JSON |
|---|---|---|
| `POST /api/ascension/<id>/log` | projet ou envie → **log** | `style`, `date`, `note_beaute`, `cotation_perso`, `pieds_nus`, `grimpe` (**obligatoire** sur corde) |
| `POST /api/ascension/<id>/projet` | envie → **projet** (le bouton « ⚡ Projet » l'appelle avec 0 essai, puis enregistre la séance n°1 par `POST /api/ascension/<id>/seances`) | facultatif : `nb_essais_projet` (entier ≥ 0, plafonné à 999) et `date_seance` → séance n°1 |
| `POST /api/ascension/<id>/categorie` | change la catégorie d'une envie | `{"categorie": "performance" \| "beaute" \| "majeure" \| null}` |

Erreurs : `/log` → 400 si le mode de grimpe manque, 404 si inconnue ; `/projet` → 400 si `nb_essais_projet` n'est pas un entier, 404 si l'ascension n'est pas **dans la tick list** de l'utilisateur ; `/categorie` → 400 si la catégorie n'existe pas, 404 si l'envie est inconnue ou n'est plus en statut `ticklist`.

## Répétitions

| Méthode | URL | Corps | Réponses |
|---|---|---|---|
| POST | `/api/repetition` | `ascension_id` et `date` (obligatoires) ; `nb_essais`, `cotation_perso`, `pieds_nus`, `note_beaute`, `commentaire`, `grimpe` (**obligatoire** sur corde) | 200 `{"success": true}` ; 400 « Ascension introuvable ou date manquante. » ou mode de grimpe manquant |
| DELETE | `/api/repetition/<id>` | — | 200 `{"success": true}` ; la suppression ne concerne que les répétitions d'une ascension de l'utilisateur (sinon rien n'est supprimé, et la réponse reste un succès) |

## Séances

Séances d'un projet : numéro, date, nombre d'essais, commentaire. Après chaque écriture, le total d'essais de l'ascension est recalculé.

### Lister

`GET /api/ascension/<id>/seances`

```json
{
  "nom": "La Marie-Rose", "type": "voie", "statut": "projet",
  "lieu": "Le Cengle › Origine",
  "seances": [ { "id": 1, "numero": 1, "date": "2026-09-12", "date_fmt": "12/09/2026", "nb_essais": 3, "commentaire": "…" } ],
  "nb_seances": 1, "total_essais": 3
}
```

404 si l'ascension est inconnue.

### Ajouter

`POST /api/ascension/<id>/seances`

```json
{"date": "2026-10-05", "nb_essais": 4, "commentaire": "Crux mieux compris"}
```

Règles : `date` obligatoire au format `AAAA-MM-JJ` ; `nb_essais` entier de **1 à 999** ; `commentaire` facultatif, **5 000 caractères** maximum. Le numéro est attribué automatiquement.

Réponses : 200 `{"success": true, "id": 12, "numero": 2}` ; 400 (`Date invalide.`, `La date de la séance est requise.`, `Nombre d'essais invalide.`, `Le nombre d'essais doit être compris entre 1 et 999.`, `Le commentaire est trop long (5000 caractères maximum).`) ; 404.

### Modifier

`PUT /api/seance/<id>` : seuls les champs envoyés (`date`, `nb_essais`, `commentaire`) sont modifiés ; la date peut être effacée. 200 `{"success": true}` ; 400 ; 404.

### Supprimer

`DELETE /api/seance/<id>` : supprime et **renumérote** les suivantes. 200 `{"success": true}` ; 404.

## Informations, listes de choix et noms

### Fiche « Plus d'informations »

`GET /api/ascension/<id>/infos`

```json
{
  "nom": "…", "type": "trad_voie", "statut": "log",
  "seances": [ … ], "nb_seances": 2, "total_essais": 7,
  "topo": { "topo_type": "papier", "topo_nom": "…", "topo_edition": "…", "topo_annee": 2019, "topo_page": "42", "topo_lien": null },
  "topo_pdf": { "id": 3, "nom": "Verdon 2023", "fichier": "Verdon.pdf", "taille": 1234567, "nb": 12 },
  "topos": [ { "id": 3, "nom": "Verdon 2023", "fichier": "Verdon.pdf", "taille": 1234567, "nb": 12, "local": true } ],
  "ouverture": { "annee": 1998, "ouvreur": "…" },
  "reequipements": [ { "nom": "…", "annee": 2021 } ],
  "cats": [ { "key": "grimpe", "label": "Type de grimpe" }, { "key": "roche", "label": "Type de roche" }, { "key": "coinceur", "label": "Coinceurs" } ],
  "tags": { "grimpe": ["Dalle"], "roche": ["Calcaire"], "coinceur": [] },
  "options": { "grimpe": ["Mur vertical", "Dalle", "…"], "roche": ["…"], "coinceur": ["…"] }
}
```

Les catégories (`cats`) dépendent du type : fixations pour `voie` et `grande_voie`, coinceurs pour `trad_voie` et `trad_gv`, roche et type de grimpe pour tous. 404 si inconnue.

`PUT /api/ascension/<id>/infos`

```json
{
  "topo_type": "pdf", "topo_nom": "Topo du Verdon", "topo_edition": "", "topo_annee": "", "topo_page": "",
  "topo_lien": "exemple.fr/topo.pdf", "topo_id": 3,
  "annee_ouverture": 1998, "ouvreur": "J. Dupont",
  "reequipements": [ { "nom": "Club local", "annee": 2021 } ],
  "tags": { "grimpe": ["Dalle"], "roche": ["Calcaire"] }
}
```

Règles de validation (tout est validé **avant** la moindre écriture) :
- `topo_type` : `papier`, `pdf` ou vide ; selon le type, seuls les champs correspondants sont conservés ;
- `topo_id` : topo de la bibliothèque (voir ci-dessous), conservé seulement si `topo_type` vaut `pdf` ; entier ou vide ; 400 « Topo inconnu. » s'il n'existe pas **dans la bibliothèque du compte** ;
- `topo_lien` : uniquement `http(s)` ; sans schéma, `https://` est ajouté ; tout autre schéma est refusé ;
- `annee_ouverture`, `topo_annee`, année d'un rééquipement : entre **1800** et l'an prochain ;
- `reequipements` : au plus **20** lignes ; une ligne vide est ignorée ; une ligne doit avoir un nom ou une année. Si le champ est **absent**, la liste existante n'est pas touchée ; sinon elle est **remplacée** ;
- `tags` : limité aux catégories autorisées pour le type, sans doublon (casse ignorée).

Réponses : 200 `{"success": true}` ; 400 ; 404.

`topo_pdf` vaut `null` si aucun topo PDF n'est choisi. `topos` est toute la bibliothèque du compte ; `local` vaut `true` pour les topos déjà utilisés ou rattachés au **site** de l'ascension (la fiche les propose en premier). Le contenu des fichiers n'est jamais inclus.

### Topos PDF (bibliothèque) et bouton « Topo » des lieux

Chaque PDF n'est enregistré qu'une fois ; les ascensions le choisissent avec `topo_id` (voir ci-dessus). Toutes les routes exigent d'être connecté et ne voient que les topos et lieux **du compte** (404 sinon).

| Méthode | URL | Corps | Réponse |
|---|---|---|---|
| GET | `/api/topos` | — | `[{"id", "nom", "fichier", "taille", "nb"}]` triée par titre (`nb` = ascensions qui l'utilisent) |
| POST | `/api/topos` | `multipart/form-data` : `fichier` (obligatoire), `titre` (facultatif), puis `ascension_id` **ou** `niveau` + `lieu_id` pour rattacher le topo à un lieu | `{"success": true, "topo": {…}, "existait": false}` ; un fichier déjà enregistré n'est pas dupliqué : `existait` vaut `true` et le topo existant (titre conservé) est renvoyé |
| GET | `/api/topos/<id>/pdf` | — | le PDF (`application/pdf`, affiché dans le navigateur, `X-Content-Type-Options: nosniff`) |
| PUT | `/api/topos/<id>` | `{"nom": "Verdon 2023"}` | `{"success": true, "nom": "Verdon 2023"}` |
| DELETE | `/api/topos/<id>` | — | `{"success": true, "ascensions": 3}` (nombre d'ascensions détachées) |
| GET | `/api/topos/lieu/<niveau>/<id>` | — | contenu du bouton « Topo » du lieu : `{"pdf": [{id, nom, fichier, taille, nb}], "papier": [{nom, edition, annee, nb}], "en_ligne": [{nom, lien, nb}]}` |

- `niveau` : `localisation`, `site`, `secteur` ou `sous_secteur` ; `pays` et `departement` n'ont pas de bouton Topo : **400**.
- Le lieu est le lieu demandé **et tout ce qui est en dessous** : un site ne renvoie que ses topos, une localisation ceux de tous ses sites. Les ascensions de tous statuts comptent. `nb` est le nombre d'ascensions **dans ce lieu**.
- Fichier : signature `%PDF-` dans les 1024 premiers octets quelle que soit l'extension, 20 Mo maximum, nom nettoyé (chemin et caractères de contrôle retirés, 150 caractères, `.pdf` ajouté si absent). Titre : 150 caractères maximum, vide refusé en renommage ; par défaut le nom du fichier sans « .pdf ».
- Erreurs : 400 (« Aucun fichier reçu. », « Le PDF dépasse 20 Mo. », « Ce fichier n'est pas un PDF. », titre invalide, niveau sans topo), 404 (topo, ascension ou lieu inconnu ou d'un autre compte), 413 si la requête dépasse 256 Mo.

### Listes de propositions

| Méthode | URL | Corps | Réponse |
|---|---|---|---|
| GET | `/api/options` | — | `{"options": {"grimpe": [...], "roche": [...], "fixation": [...], "coinceur": [...]}, "labels": {"grimpe": "Type de grimpe", ...}}` |
| POST | `/api/options` | `{"categorie": "coinceur", "nom": "Tricams"}` | `{"success": true, "nom": "Tricams", "existait": false}` ; 400 si catégorie ou nom invalide (40 caractères maximum) ou liste pleine (60) |
| DELETE | `/api/options` | `{"categorie": "coinceur", "nom": "Tricams"}` | `{"success": true}` ; les ascensions qui avaient choisi cette proposition la gardent |

La première lecture d'une liste la remplit avec les propositions de départ (voir [MODELE_DONNEES.md](MODELE_DONNEES.md#listes-de-choix-tags)).

### Suggestions de noms

`GET /api/noms`

```json
{ "ascensions": ["…"], "lieux": ["…"], "ouvreurs": ["…"], "topos": ["…"] }
```

Noms déjà saisis par l'utilisateur, triés sans tenir compte de la casse. `ouvreurs` inclut les personnes ayant rééquipé. Sert aux listes de suggestions (`datalist`).

## Exports, sauvegarde, restauration

| Méthode | URL | Résultat |
|---|---|---|
| GET | `/export/csv` | téléchargement `carnet_de_croix_export_AAAA-MM-JJ.zip` : `ascensions.csv`, `longueurs.csv`, `repetitions.csv`, `seances.csv` (liés par `ascension_id`) ; **données de l'utilisateur uniquement** |
| GET | `/export/pdf` | téléchargement `carnet_de_croix_AAAAMMJJ.pdf` : résumé + tableau chronologique |
| GET | `/backup` | téléchargement `carnet_backup_AAAAMMJJ_HHMM.db` : copie brute de la base ⚠️ **tous les comptes** ; **réservé à l'administrateur** (403 sinon) |
| POST | `/restore` | restaure une sauvegarde ; **réservé à l'administrateur** (403 sinon) |

`POST /restore` : envoi en `multipart/form-data`, fichier dans le champ **`dbfile`**.
- 200 `{"success": true}` ;
- 400 `{"error": …}` si le fichier est absent ou n'est pas une base valide (SQLite contenant au moins les tables `user` et `ascension`) ;
- l'ancienne base est conservée sous `<base>.before_restore` ; une sauvegarde ancienne est migrée automatiquement ;
- ⚠️ remplace les données de **tous** les comptes.

## Paramètres de la Recherche

`GET /recherche?…` : tous les paramètres sont facultatifs ; une valeur inconnue est ignorée.

| Paramètre | Valeurs | Défaut |
|---|---|---|
| `statut` | `log`, `projet`, `ticklist`, `tout` | `log` |
| `q` | texte (nom, site, localisation, secteur, sous-secteur, commentaire) | — |
| `type` | un type d'ascension (répétable) | tous |
| `style` | un style (répétable) | tous |
| `beaute` | 1 à 5 (répétable) | tous |
| `date` | `AAAA-MM-JJ` (répétable) | toutes |
| `roche`, `tgrimpe` | nom d'un choix (répétable) | tous |
| `mode` | `tete`, `moulinette` (répétable) | tous |
| `cot_min`, `cot_max` | une cotation de `GRADE_ORDER` | aucune |
| `hauteur_min`, `hauteur_max` | nombre (m) | aucune |
| `annee_min`, `annee_max` | année d'ouverture | aucune |
| `pieds_nus` | `1` | — |
| `ouvreur`, `topo` | texte | — |
| `tri` | `date_desc`, `date_asc`, `cotation_desc`, `cotation_asc`, `style_asc`, `style_desc`, `beaute_desc`, `beaute_asc`, `hauteur_desc`, `hauteur_asc`, `nom` | `date_desc` |
| `groupe` | `site`, `plat` | `site` |
| `mois` | mois du calendrier, ex. `2026-09` | mois du log le plus récent |

Les paramètres répétables s'écrivent `?type=voie&type=bloc`.

## Exemples

### Ajouter un bloc réalisé (JavaScript)

```js
const res = await fetch('/api/ascension', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    type: 'bloc', statut: 'log', nom: 'La Marie-Rose',
    pays: 'France', departement: 'Seine-et-Marne', localisation: 'Fontainebleau',
    site: 'Bas Cuvier', secteur: 'Cuvier Rempart',
    cotation: '7a', style: 'flash', date: '2026-10-04', note_beaute: 4
  })
});
const data = await res.json();
if (data.duplicate) { /* proposer d'ajouter une répétition */ }
else if (data.error) { alert(data.error); }
else { location.href = '/carnet?open_secteur=' + data.secteur_id; }
```

### Enregistrer une séance (curl, session ouverte)

```bash
curl -b cookies.txt -X POST http://127.0.0.1:5000/api/ascension/42/seances \
     -H 'Content-Type: application/json' \
     -d '{"date": "2026-10-05", "nb_essais": 4, "commentaire": "Crux compris"}'
# {"id": 12, "numero": 2, "success": true}
```

### Erreur type

```bash
curl -b cookies.txt -X POST http://127.0.0.1:5000/api/ascension/42/seances \
     -H 'Content-Type: application/json' -d '{"nb_essais": 0}'
# 400  {"error": "La date de la séance est requise."}
```
