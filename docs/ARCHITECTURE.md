# Architecture

Ce document explique comment le code de **Carnet de Croix** est organisé, comment une requête le traverse et quelles conventions il suit. Pour les règles métier, voir [FONCTIONNALITES.md](FONCTIONNALITES.md) ; pour les tables, [MODELE_DONNEES.md](MODELE_DONNEES.md) ; pour les routes, [API.md](API.md).

## Sommaire

1. [Vue d'ensemble](#vue-densemble)
2. [Arborescence](#arborescence)
3. [Les trois couches](#les-trois-couches)
4. [Cycle de vie d'une requête](#cycle-de-vie-dune-requête)
5. [Démarrage de l'application](#démarrage-de-lapplication)
6. [Gestion des erreurs](#gestion-des-erreurs)
7. [Base de données](#base-de-données)
8. [Authentification et isolation des données](#authentification-et-isolation-des-données)
9. [Le front-end](#le-front-end)
10. [Les services, module par module](#les-services-module-par-module)
11. [Sécurité](#sécurité)
12. [Tests](#tests)
13. [Ajouter une fonctionnalité](#ajouter-une-fonctionnalité)

---

## Vue d'ensemble

| Élément | Choix |
|---|---|
| Langage serveur | Python 3.9+ |
| Framework web | Flask (fabrique d'application + blueprints) |
| Base de données | SQLite (un seul fichier, `carnet.db`), accès direct avec le module `sqlite3` (pas d'ORM) |
| Templates | Jinja2, pages rendues côté serveur |
| Front | JavaScript « vanilla » (aucun framework, aucune compilation), CSS écrit à la main |
| Graphiques | Chart.js (chargé depuis cdnjs) |
| PDF | reportlab |
| Tests | pytest (709 tests, 99 % de couverture des lignes Python) |

L'interface est entièrement en français. Les valeurs stockées en base (`'bloc'`, `'a_vue'`, `'tete'`…) sont des clés techniques ; les libellés français ne servent qu'à l'affichage (voir `src/constants.py`).

## Arborescence

```
carnet-de-croix/
├── run.py                  point d'entrée : crée l'application et lance le serveur de développement
├── requirements.txt        dépendances d'exécution (Flask, reportlab…)
├── requirements-dev.txt    + pytest et pytest-cov
├── pytest.ini              configuration des tests
├── README.md               présentation et installation
├── docs/                   cette documentation
├── src/
│   ├── __init__.py         fabrique d'application create_app()
│   ├── config.py           chemin de la base, clé secrète de session
│   ├── constants.py        données de référence (cotations, types, statuts, libellés…)
│   ├── errors.py           exceptions métier → réponses JSON (et erreur 413)
│   ├── db.py               connexion SQLite par requête
│   ├── schema.py           création des tables + migrations
│   ├── auth.py             décorateur login_required, current_user_id
│   ├── routes/             couche HTTP (8 blueprints)
│   ├── services/           logique métier (16 modules)
│   ├── templates/          pages Jinja2
│   └── static/             CSS et JavaScript
└── tests/                  suite pytest (unit / services / routes)
```

## Les trois couches

```
 Navigateur
     │  HTTP (HTML ou JSON)
     ▼
 routes/     lit la requête, vérifie le minimum, appelle un service, fabrique la réponse
     │
     ▼
 services/   règles métier + requêtes SQL ; ne connaît pas Flask
     │
     ▼
 SQLite      fichier carnet.db
```

- **Routes** (`src/routes/`) : « minces ». Elles lisent `request`, appellent un service, renvoient `jsonify(...)` ou `render_template(...)`. Elles ne contiennent pas de règles métier compliquées.
- **Services** (`src/services/`) : reçoivent une connexion SQLite (`conn`), l'identifiant de l'utilisateur (`uid`) et des données simples ; renvoient des dictionnaires, des listes, ou lèvent une erreur de `errors.py`. Rien n'y dépend de Flask, ce qui permet de les tester avec une simple connexion SQLite.
- **Base** : SQLite, accédée via `db.get_db()`.

Cette séparation a une conséquence pratique : **les règles de l'application se trouvent dans `services/` et `constants.py`**, jamais dans une route ni dans un template.

## Cycle de vie d'une requête

Exemple : l'utilisateur ajoute une ascension depuis le Carnet (`POST /api/ascension`).

1. Le JavaScript (`features/ascension-form.js`, fonction `collectPayload`) rassemble les champs du formulaire en un objet JSON et l'envoie avec `fetch`.
2. Flask appelle `routes/api_ascensions.py › add_ascension`. Le décorateur `@login_required` vérifie la session (sinon redirection vers `/login`).
3. La route valide le lieu et le type (`geo_service.validate_geo_payload`, `ASCENSION_TYPES`, `STATUTS`) et, pour une voie loguée, le mode de grimpe (`_check_grimpe`).
4. `geo_service.resolve_location` retrouve ou crée la chaîne pays › … › secteur (get-or-create) et renvoie les identifiants.
5. `asc_service.find_duplicate` cherche un doublon. S'il y en a un, la route répond `{"success": false, "duplicate": true, "existing": {...}}` sans rien écrire.
6. Sinon `asc_service.insert_ascension` insère la ligne (et les longueurs d'une grande voie, ou la séance n°1 d'un projet), puis la route fait `conn.commit()`.
7. La route répond `{"success": true, "id": ..., "secteur_id": ...}` ; le JavaScript recharge `/carnet?open_secteur=<id>` pour déplier le bon secteur.
8. À la fin de la requête, `db.close_db` ferme la connexion (`teardown_appcontext`).

**Le commit n'est pas automatique** : chaque route qui écrit doit appeler `conn.commit()`. Une requête qui lève une exception avant le commit est donc annulée.

## Démarrage de l'application

`create_app(config=None)` (dans `src/__init__.py`) assemble tout, dans cet ordre :

1. Crée l'objet `Flask` et charge `Config` (chemin de la base) ; la clé secrète vient de `Config.secret_key()`.
2. Applique le dictionnaire `config` éventuel en dernier (les tests s'en servent pour fournir une base temporaire).
3. `db.init_app` branche la fermeture de la connexion en fin de requête.
4. `register_error_handlers` branche le traitement des `ApiError`.
5. `register_blueprints` enregistre les 8 blueprints : `auth`, `pages`, `api_geo`, `api_ascensions`, `api_seances`, `api_infos`, `api_topos`, `exports`.
6. Ajoute les filtres Jinja `alpine_grade` et `fmt_date`.
7. `schema.init_db` crée ou met à jour les tables (idempotent : sans danger à chaque lancement).

`run.py` appelle `create_app()` ; en développement, `python run.py` démarre le serveur avec `debug=True` (rechargement automatique, **jamais en production**). Pour un hébergement : `gunicorn "src:create_app()"`.

### Configuration

| Variable d'environnement | Rôle | Défaut |
|---|---|---|
| `CARNET_DATABASE` | chemin du fichier SQLite | `carnet.db` à la racine du projet |
| `CARNET_SECRET_KEY` | clé qui signe le cookie de session | fichier `.secret_key` généré au premier lancement |

Si ni la variable ni le fichier ne sont utilisables, une clé aléatoire est générée pour la session du processus (les utilisateurs devront alors se reconnecter à chaque redémarrage).

## Gestion des erreurs

`src/errors.py` définit une petite hiérarchie :

| Exception | Code HTTP | Quand |
|---|---|---|
| `ApiError` | 400 (défaut) | base commune |
| `ValidationError` | 400 | donnée invalide |
| `NotFoundError` | 404 | élément inexistant **ou qui appartient à un autre utilisateur** |
| `ConflictError` | 409 | l'élément existe déjà (ex. renommage vers un nom pris) |

Les services et les routes font simplement `raise ValidationError("message")`. Un gestionnaire unique transforme l'exception en réponse JSON :

```json
{"error": "message affiché à l'utilisateur"}
```

Le JavaScript affiche ce message tel quel. Il n'y a donc pas de tuples `(réponse, code)` éparpillés dans le code.

## Base de données

- **Une connexion par requête**, stockée dans `flask.g` : `get_db()` la crée à la première demande, `close_db()` la ferme à la fin. Les lignes se lisent par nom de colonne (`row['nom']`, `dict(row)`).
- **Schéma et migrations** dans `schema.py` : `init_db(path)` crée les tables manquantes puis applique des migrations qui testent d'abord si elles sont nécessaires (colonne absente, ancien nom de table…). On peut donc ouvrir une base créée par une très ancienne version, ou restaurer une vieille sauvegarde : elle est mise à niveau automatiquement.
- **Requêtes paramétrées** : les valeurs saisies passent toujours par des `?`. Les seuls noms de tables ou de colonnes insérés dans du SQL viennent de listes blanches du code (`GEO_TABLES`, colonnes fixes).

Voir [MODELE_DONNEES.md](MODELE_DONNEES.md) pour le détail des tables.

## Authentification et isolation des données

- Le compte (`user`) stocke le mot de passe **haché** (`werkzeug.security`) ; la session Flask contient `user_id` et `user_name` dans un cookie signé.
- `@login_required` redirige vers `/login` (302) si personne n'est connecté. Pour une route d'API, un utilisateur non connecté reçoit donc une redirection, pas du JSON.
- **Chaque requête filtre sur `uid`** (identifiant de l'utilisateur connecté). Les lieux descendent de `user` via `pays.user_id`. Une ressource qui appartient à un autre compte est traitée comme inexistante (404), jamais comme interdite : on ne révèle pas son existence. Des tests vérifient cette isolation entre deux comptes pour toutes les routes d'API.
- Seules `/login`, `/register` et `/logout` sont publiques.
- ⚠️ La **sauvegarde** (`/backup`) et la **restauration** (`/restore`) travaillent sur le fichier entier : elles concernent *tous* les comptes de la base. C'est cohérent pour un usage personnel ou familial ; à garder en tête si l'application était hébergée pour plusieurs personnes.

## Le front-end

### Pages et templates

Toutes les pages héritent de `templates/base.html` (en-tête, menu, chargement des CSS et des scripts). Une page = un fichier de `templates/pages/` ; les fenêtres modales et cartes réutilisées sont dans `templates/partials/`.

| Page | Route | Template | Service | Script principal |
|---|---|---|---|---|
| Carnet | `/carnet` | `pages/carnet.html` | `carnet.py`, `topo_pdf.py` | `features/geo-tree.js`, `features/topos.js` |
| Projets | `/projets` | `pages/projets.html` | `projets.py` | `pages/projets.js`, `features/seances.js` |
| Tick List | `/ticklist` | `pages/ticklist.html` | `ticklist.py` | `pages/ticklist.js` |
| Recherche | `/recherche` | `pages/recherche.html` | `recherche.py` | script inline de la page |
| Stats | `/stats` | `pages/stats.html` | `stats.py` | script inline (Chart.js), `pages/stats-restore.js` |
| Connexion / inscription | `/login`, `/register` | `auth/*.html` | — | — |

Les données Python utiles au JavaScript sont transmises dans une balise `<script>` avec le filtre `|tojson` (ex. `const GRADES = {{ grades | tojson }};`), qui garantit un JSON sûr.

### JavaScript

Aucun framework ni module : ce sont des fichiers classiques chargés dans l'ordre indiqué par `base.html` (l'ordre compte, car les fichiers partagent des fonctions globales).

| Dossier | Rôle |
|---|---|
| `js/core/` | utilitaires partagés : `config.js` (constantes JS), `grades.js` (cotations), `stars.js` (notes), `modal.js` (ouverture/fermeture des fenêtres), `cotation-select.js` (bouton « / » des cotations « entre deux »), `geo-autocomplete.js` (listes de lieux en cascade), `noms.js` (suggestions de noms) |
| `js/features/` | fonctionnalités : `ascension-form.js` (formulaire), `ascension-modal.js` (fenêtre d'ajout/édition), `geo-tree.js` (arbre du carnet), `geo-edit.js` (renommer/supprimer un lieu), `repetition.js`, `quick-modals.js` (« Marquer comme grimpé », bouton « ⚡ Projet »), `seances.js` (fenêtre des séances, aussi utilisée pour « Passer en projet »), `infos-modal.js`, `topos.js` (bouton « Topo » des lieux) |
| `js/pages/` | code propre à une page : `projets.js`, `ticklist.js`, `stats-restore.js` |
| `js/main.js` | appelle l'initialisation de chaque fonctionnalité au chargement |

Chaque script s'active seulement si les éléments HTML qu'il attend existent sur la page (ex. `if (document.getElementById('tlBody'))`), ce qui permet de tous les charger partout.

Conventions du JavaScript :
- le texte saisi est inséré avec `textContent` (jamais comme HTML) pour éviter les injections ;
- les appels à l'API utilisent `fetch` avec du JSON, et affichent `data.error` en cas d'erreur ;
- la Recherche met à jour la page « en direct » : le formulaire est renvoyé en `fetch`, le serveur renvoie la page entière, et seules les zones `#rcResults`, `#rcSummary` et `#calBox` sont remplacées ;
- les pages Projets et Tick List filtrent, trient et regroupent **côté navigateur** ; sur la page Projets, les choix (tri, regroupement, discipline) sont mémorisés dans `localStorage` du navigateur.

### CSS

Onze feuilles, chargées dans cet ordre par `base.html` (l'ordre compte, une règle plus tardive l'emporte à spécificité égale) :

`base` (variables de couleur, remise à zéro) → `header` → `buttons` → `layout` → `carnet` → `modals-forms` → `auth-misc` → `stats` → `projets-infos` → `ticklist` → `recherche`.

`base.css` définit la palette (`--bg`, `--accent`, `--roche`, `--or`…) sous forme de variables CSS réutilisées partout : changer une couleur à cet endroit la change dans toute l'application.

## Les services, module par module

| Module | Responsabilité |
|---|---|
| `grades.py` | comparer les cotations (`grade_index`, `grade_rank`, `max_grade`), cotations « entre deux », cotation effective d'une grande voie, conversion alpine, tri des ascensions, paliers de la tick list |
| `formatting.py` | normaliser des noms (sans casse, accents ni espaces), convertir en entier, formater une date en JJ/MM/AAAA |
| `geo.py` | lieux : propriété, get-or-create, renommage, suppression en cascade, compteurs d'exploration, chemin d'un secteur |
| `ascensions.py` | doublons, création, mise à jour, suppression, détail d'une ascension, fragments SQL de jointure des lieux |
| `seances.py` | numérotation et validation des séances, recalcul du total d'essais |
| `tags.py` | listes de propositions personnalisables (roche, type de grimpe, fixations, coinceurs) et choix par ascension |
| `infos.py` | fenêtre « Plus d'informations » : topo, ouverture, rééquipements, choix, suggestions de noms |
| `topo_pdf.py` | bibliothèque de topos PDF dans la base : validation (`%PDF-`, 20 Mo), pas de doublon (empreinte SHA-256), rattachement à un lieu, renommage, suppression, et contenu du bouton « Topo » d'un lieu |
| `carnet.py` | arbre de la page Carnet (logs uniquement) |
| `projets.py` | liste des projets avec leurs séances |
| `ticklist.py` | liste des envies, catégories, repère « plus dur que ce que j'ai fait » |
| `recherche.py` | lecture des filtres, requête, tri, synthèse, regroupement par site, calendrier |
| `stats.py` | chiffres par discipline, évolution par saison, règle « en tête uniquement » |
| `export_csv.py` | ZIP de 4 CSV liés |
| `export_pdf.py` | PDF (résumé + liste chronologique) avec reportlab |
| `backup.py` | vérification et restauration d'une sauvegarde |

### Choix de conception notables

- **Un seul endroit pour la règle des stats.** `stats.counts_in_stats(type, grimpe)` décide si une ascension (ou répétition) compte ; la page Stats, le graphe d'évolution et le résumé du PDF l'utilisent tous, donc ils ne peuvent pas diverger.
- **Un seul dictionnaire de libellés de types** : `constants.TYPE_LABELS` (« Bloc », « Voie », « Grande Voie », « Trad », « Trad GV », « Psychobloc »), utilisé par toutes les pages et le PDF.
- **Le total d'essais d'un projet n'est jamais saisi à la main** : `seances.sync_essais_projet` le recalcule depuis les séances après chaque changement.
- **Cotations comparées par position**, jamais par texte : `GRADE_ORDER` donne l'ordre, et les comparaisons se font en Python (SQLite ne saurait pas comparer `'6c+'` et `'7a'`).
- **Cotation effective** : pour une grande voie, tous les calculs de difficulté utilisent la cotation *haute* (le passage le plus dur).
- **Pas de ressource « orpheline »** : supprimer une ascension supprime ses longueurs, répétitions, séances, choix et rééquipements (`ascensions.delete_ascensions`) ; supprimer un lieu supprime tout ce qu'il contient (`geo.delete_item`).

## Sécurité

Le détail (limites, en-têtes, réglages GitHub, que faire en cas de fuite) est dans [SECURITE.md](SECURITE.md). En résumé, tout est branché une fois pour toutes dans `src/security.py` (`init_app`), les routes n'ont rien à faire :

| Risque | Mesure |
|---|---|
| Requête forgée depuis un autre site (CSRF) | jeton de session obligatoire sur `POST/PUT/PATCH/DELETE` (`before_request`) ; `csrf.js` l'ajoute aux `fetch`, les formulaires ont un champ caché |
| Injection de script (XSS) | auto-échappement de Jinja ; `escHtml` pour le HTML construit en JS ; **CSP à nonce** (`script-src 'self' 'nonce-…'`) : un script injecté ne s'exécute pas ; aucune ressource externe (polices et Chart.js hébergés) |
| Injection SQL | requêtes paramétrées ; noms de tables / colonnes issus du code uniquement (liste blanche `GEO_TABLES`) |
| Accès aux données d'autrui | filtre `uid` partout ; ressource d'un autre compte = 404 ; compte relu en base à chaque requête |
| Mots de passe, devinette | hachés ; message d'erreur unique ; limitation des essais en base (`services/ratelimit.py`) ; anti-robots à l'inscription (`services/antibot.py`) |
| Fuite de la base | sauvegarde / restauration réservées à l'administrateur ; `.env`, base et clés jamais versionnés |
| Mise en production | production par défaut (cookie `Secure`, HTTPS forcé, HSTS), clé secrète obligatoire, débogueur désactivé |
| Liens de topo | seuls `http(s)` acceptés (serveur et navigateur) ; `rel="noopener noreferrer"` |
| PDF et restauration | signature `%PDF` vérifiée, `nosniff` ; restauration : base SQLite avec tables `user` et `ascension`, ancienne base gardée en `.before_restore` |

À faire avant une mise en ligne : `.env` avec `CARNET_SECRET_KEY` (sans `CARNET_ENV=development`), `TRUST_PROXY=1` derrière un proxy, servir en HTTPS, `carnet.db` sur un stockage persistant, puis `python scripts/check_env.py`.

## Tests

Voir la section « Tests » du [README](../README.md). Points d'architecture :

- `tests/conftest.py` redirige `CARNET_DATABASE` vers un dossier temporaire **avant** l'import de l'application : les tests ne peuvent jamais ouvrir ni modifier le vrai `carnet.db` ni `.secret_key`.
- Chaque test reçoit une base SQLite neuve (fixture) ; un hachage de mot de passe rapide accélère l'inscription dans les tests.
- `tests/unit/` teste les fonctions pures, `tests/services/` la logique métier sur une vraie base, `tests/routes/` l'API et les pages via le client de test Flask.

## Ajouter une fonctionnalité

Marche à suivre type, par exemple « ajouter un champ à une ascension » :

1. **Schéma** : ajouter la colonne dans `schema.py` (liste `_ASCENSION_EXTRA_COLUMNS`) : la migration l'ajoutera aux bases existantes.
2. **Constantes** : si le champ a des valeurs fixes, les déclarer dans `constants.py`.
3. **Service** : lire et écrire le champ dans `ascensions.py` (`insert_ascension`, `update_ascension`, `get_ascension_detail`) avec la validation nécessaire.
4. **Route** : ne change normalement pas (les données passent par le dictionnaire JSON) ; ajouter la validation si besoin et le `conn.commit()` pour toute écriture.
5. **Front** : champ dans `buildForm` et `collectPayload` (`ascension-form.js`), affichage dans la carte (`partials/carnet_card.html`).
6. **Exports** : colonne dans `export_csv.py` si pertinent.
7. **Tests** : un test de service, un test de route, un test de migration si une colonne est ajoutée.
8. **Documentation** : mettre à jour le README et les fichiers de `docs/`.
