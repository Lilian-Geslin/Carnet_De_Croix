# Carnet de Croix

Carnet d'escalade personnel en ligne. On y consigne ses ascensions (blocs, voies, grandes voies, trad, psychoblocs), ses projets et sa tick list, rangés par lieu, avec statistiques, recherche, export et sauvegarde.

Application web **Flask + SQLite**, interface en français, sans framework JavaScript (JS « vanilla » et Chart.js pour les graphiques).

## Sommaire

1. [Installation et lancement](#installation-et-lancement)
2. [Fonctionnalités](#fonctionnalités)
3. [Structure du projet](#structure-du-projet)
4. [Architecture](#architecture)
5. [Configuration](#configuration)
6. [Sécurité](#sécurité)
7. [Sauvegarde et restauration](#sauvegarde-et-restauration)
8. [Déploiement](#déploiement)
9. [Tests](#tests)
10. [Documentation](#documentation)

## Installation et lancement

Prérequis : **Python 3.11+** (imposé par Pillow 13, épinglé dans requirements.txt).

```bash
python -m venv venv
source venv/bin/activate          # Windows : venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # Windows : copy .env.example .env  (puis remplir CARNET_SECRET_KEY, voir Configuration)
python run.py
```

L'application est disponible sur <http://127.0.0.1:5000>. La base `carnet.db` est créée au premier démarrage ; il suffit ensuite de créer un compte sur la page d'inscription. Pour repartir de zéro, arrêter l'application et supprimer `carnet.db`.

**Un fichier `.env` est obligatoire** : il contient la clé secrète (`CARNET_SECRET_KEY`) et, sur ton PC, `CARNET_ENV=development` (sans lui, l'application se comporte comme en production : cookie sécurisé, HTTPS forcé, donc pas de connexion en http). Voir [Configuration](#configuration).

Les polices (Bebas Neue, DM Sans) et Chart.js sont **hébergés dans le projet** : aucune ressource externe, l'application fonctionne hors connexion.

## Fonctionnalités

| Page | Contenu |
|---|---|
| **Carnet** | Arbre déroulant Pays › Département › Localisation › Site › Secteur › Sous-secteur › Ascension. Ajout, édition, renommage et suppression à chaque niveau. Les lieux sans ascension réalisée n'apparaissent pas. |
| **Projets** | Suivi séance par séance (date, essais, mini-journal), regroupement par site ou secteur, tris et filtres, passage au carnet quand le projet est réussi. |
| **Tick List** | Liste à cocher avec catégories (Performance, Beauté, Majeure), vues *Liste* et *Paliers*, filtres ; « ⚡ Projet » ouvre le formulaire de séance complet, et un projet ajouté propose de détailler la séance. |
| **Recherche** | Barre de recherche et filtres en pastilles, mise à jour en direct, fourchette de cotation, calendrier, périmètre Carnet / Projets / Tick list / Tout, regroupement par site ou à plat, synthèse des résultats. |
| **Stats** | Exploration géographique, meilleures performances, détail par discipline (à vue / flash / travaillé), graphe d'évolution. Pour la **voie** et le **trad (voie)**, seules les ascensions grimpées **en tête** sont comptabilisées (une phrase l'indique au-dessus du diagramme ; les ascensions en moulinette ou « les deux » restent enregistrables mais n'apparaissent pas dans les stats, ni dans le résumé du PDF). Les grandes voies (normale et trad) comptent toutes les ascensions. |

Fonctions transversales :

- **Types d'ascension** : bloc, voie, grande voie, trad (libellé « Trad »), trad grande voie (« Trad GV »), psychobloc. Un seul dictionnaire de libellés (`TYPE_LABELS`, `src/constants.py`) sert à toutes les pages.
- **Règle des stats** : `TETE_ONLY_TYPES` (`voie`, `trad_voie`) ne compte que le mode « en tête ». Les anciennes ascensions de ces types sans mode renseigné ne sont pas comptées ; la page Stats l'indique (« N sans précision, non comptée(s) »).
- **Code commenté** : chaque fichier Python, JavaScript, CSS et template commence par un commentaire d'en-tête, et les fonctions et blocs sont expliqués en français.
- **Cotations « entre deux »** (7a/+, 7a+/b) et cotation alpine déduite pour les grandes voies.
- **Tick list** : catégories *Performance*, *Beauté* et *Majeure* (ex-« Classique » ; les anciennes envies sont converties automatiquement).
- **Fiche « Plus d'informations »** : ouverture, rééquipements, topo (papier, lien en ligne ou **PDF enregistré dans le site**), type de grimpe, roche, fixations ou coinceurs, séances.
- **Bibliothèque de topos PDF** : un PDF est enregistré **une seule fois** (20 Mo max) et choisi par toutes les ascensions concernées ; une nouvelle édition est un nouveau topo, les anciennes ascensions gardent l'ancien. Un bouton **Topo** sur chaque localisation, site, secteur et sous-secteur du Carnet liste les topos (PDF, papier, liens) utilisés dessous, et permet d'en ajouter, renommer, supprimer.
- **Répétitions** d'une ascension et **détection des doublons** à l'ajout.
- **Ressenti de cotation** d'un secteur, pré-rempli automatiquement.
- **Suggestions de noms** sur tous les champs de lieu, d'ascension, de topo et d'ouvreur.
- **Export** CSV et PDF, **sauvegarde / restauration** de la base.

## Structure du projet

```
carnet-de-croix/
├── run.py                      # point d'entrée (python run.py)
├── requirements.txt            # dépendances, versions épinglées
├── requirements-dev.txt        # + pytest et pytest-cov (tests)
├── pytest.ini
├── README.md  LICENSE  SECURITY.md
├── .env.example                # modèle du fichier .env (le vrai .env n'est jamais publié)
├── .github/                    # intégration continue (tests + pip-audit) et Dependabot
├── scripts/                    # check_env.py (vérifie le .env), check_updates.py (mises à jour et failles)
├── docs/                       # documentation détaillée (architecture, fonctionnalités, données, API, sécurité)
├── carnet.db                   # base SQLite (créée au démarrage, ignorée par git)
├── src/
│   ├── __init__.py             # fabrique d'application : create_app()
│   ├── config.py               # .env, mode production / développement, clé de session, cookies, comptes
│   ├── security.py             # CSRF, CSP à nonce, en-têtes, HTTPS, droits d'administrateur
│   ├── constants.py            # listes de référence (types, cotations, statuts…)
│   ├── errors.py               # exceptions métier traduites en réponses JSON
│   ├── db.py                   # connexion SQLite par requête
│   ├── schema.py               # création des tables et migrations
│   ├── auth.py                 # session et décorateur login_required
│   ├── routes/                 # couche HTTP : lit la requête, appelle un service, répond
│   │   ├── auth.py             #   connexion, inscription, déconnexion
│   │   ├── pages.py            #   pages HTML
│   │   ├── api_geo.py          #   lieux (pays → sous-secteur)
│   │   ├── api_ascensions.py   #   ascensions, répétitions, passage de statut
│   │   ├── api_seances.py      #   séances d'un projet
│   │   ├── api_infos.py        #   fiche d'informations, listes d'options, noms
│   │   ├── api_topos.py        #   bibliothèque de topos PDF, bouton « Topo » d'un lieu
│   │   └── exports.py          #   CSV, PDF, sauvegarde, restauration
│   ├── services/               # logique métier, sans dépendance à la requête HTTP
│   │   ├── grades.py  formatting.py  geo.py  ascensions.py  seances.py  tags.py  topo_pdf.py
│   │   ├── infos.py  carnet.py  projets.py  ticklist.py  recherche.py  stats.py  ratelimit.py  antibot.py
│   │   └── export_csv.py  export_pdf.py  backup.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── auth/               # connexion, inscription
│   │   ├── pages/              # une page = un fichier
│   │   └── partials/           # fenêtres modales et cartes réutilisées
│   └── static/
│       ├── fonts/              # Bebas Neue et DM Sans hébergées (licence SIL OFL)
│       ├── css/                # feuilles de style par thème (base, header, carnet, stats, recherche…)
│       └── js/
│           ├── core/           # utilitaires partagés : csrf (jeton), cotations, modales, géo, noms
│           ├── vendor/         # Chart.js hébergé (licence MIT)
│           ├── features/       # fonctionnalités : arbre, topos, ascensions, séances, fiche d'infos
│           ├── pages/          # code propre à une page
│           └── main.js         # initialise chaque fonctionnalité au chargement
└── tests/                      # suite pytest (voir « Tests »)
    ├── conftest.py  helpers.py #   fixtures (base temporaire, clients connectés) et fabriques de données
    ├── unit/                   #   fonctions pures : cotations, formatage, validations, constantes, config
    ├── services/               #   logique métier sur une vraie base SQLite temporaire
    └── routes/                 #   API et pages via le client de test Flask
```

## Architecture

- **Trois couches** : *routes* (HTTP) → *services* (règles métier, requêtes SQL) → *base SQLite*. Une route ne contient pas de logique métier ; un service ne connaît pas Flask.
- **Fabrique d'application** : `create_app()` assemble la configuration, la base, les gestionnaires d'erreurs, les blueprints et les filtres Jinja.
- **Erreurs** : les services lèvent `ValidationError`, `NotFoundError` ou `ConflictError` ; un gestionnaire unique les convertit en `{"error": "..."}` avec le bon code HTTP.
- **Base de données** : une connexion par requête (`flask.g`), fermée automatiquement. Le schéma et ses migrations sont appliqués au démarrage (`schema.init_db`).
- **Front** : pages rendues côté serveur (Jinja2), JavaScript sans framework ni étape de compilation. Les scripts sont des fichiers classiques chargés dans l'ordre indiqué dans `base.html` ; les feuilles de style sont chargées dans l'ordre indiqué dans `base.html` (l'ordre compte en CSS).

## Configuration

Les réglages viennent du fichier **`.env`** (à la racine, à côté de `run.py`) ; `.env.example` en est le modèle commenté. `python scripts/check_env.py` vérifie ton `.env` sans jamais afficher les valeurs.

| Variable | Rôle | Défaut |
|---|---|---|
| `CARNET_SECRET_KEY` | **Obligatoire.** Clé qui signe les sessions (16 caractères minimum). Génération : `python -c "import secrets; print(secrets.token_urlsafe(48))"` | — (l'application refuse de démarrer) |
| `CARNET_ENV` | `development` sur ton PC : cookie non sécurisé, HTTPS non forcé, rechargement automatique. **Jamais sur un serveur** | production |
| `CARNET_DATABASE` | Chemin du fichier SQLite | `carnet.db` à la racine |
| `ALLOW_REGISTRATION` | `0` ferme les inscriptions (instance personnelle : crée ton compte d'abord) | `1` |
| `CARNET_ADMIN_EMAIL` | Seul compte à pouvoir sauvegarder / restaurer la base | le premier compte créé |
| `TRUST_PROXY` | `1` derrière un proxy d'hébergement : lit la vraie adresse IP (limitation des essais) | absent |
| `FORCE_HTTPS` | `0` désactive la redirection http → https en production | `1` |
| `CARNET_MAX_UPLOAD_MB` | Taille maximale d'un envoi (PDF de topo, restauration), en Mo | `256` |
| `CARNET_PORT` | Port de `python run.py` | `5000` |

L'ancien fichier `.secret_key` n'est plus utilisé : copie son contenu dans `CARNET_SECRET_KEY` (ou génère une nouvelle clé : tout le monde devra simplement se reconnecter) puis supprime-le.

## Sécurité

Carnet de Croix est prévu pour être mis en ligne : jeton **CSRF** sur toute écriture, **CSP à nonce** (un script injecté ne s'exécute pas), en-têtes de sécurité et HSTS, cookie `HttpOnly` / `SameSite` / `Secure`, mots de passe hachés (8 à 128 caractères), message de connexion identique pour un compte inconnu ou un mauvais mot de passe, **limitation des essais** (compteurs en base), anti-robots à l'inscription, sauvegarde / restauration **réservées à l'administrateur**, polices et scripts hébergés (aucun appel externe), `.env` et base jamais versionnés, dépendances épinglées et surveillées (Dependabot, `pip-audit`). Le détail, la liste des réglages GitHub à activer et la marche à suivre en cas de fuite sont dans [`docs/SECURITE.md`](docs/SECURITE.md) ; pour signaler une faille, voir [`SECURITY.md`](SECURITY.md).

## Sauvegarde et restauration

Depuis la page **Stats** (boutons visibles de l'**administrateur** seulement, car la base contient tous les comptes) : *Sauvegarder* télécharge une copie de la base, *Restaurer une sauvegarde* la remplace (l'ancienne est conservée sous `carnet.db.before_restore`). Les exports CSV et PDF sont disponibles sur la même page. Les **topos PDF** enregistrés dans le site sont stockés dans la base : ils sont inclus dans la sauvegarde (qui peut donc être volumineuse) ; l'export CSV n'en contient que le titre (colonne `topo_pdf`).

## Déploiement

`python run.py` lance le serveur local (en mode production par défaut, sans debug ; le rechargement automatique n'existe qu'avec `CARNET_ENV=development`, sans le débogueur interactif). Pour un hébergement, utiliser un serveur WSGI :

```bash
pip install gunicorn
gunicorn "src:create_app()"
```

Sur le serveur : un `.env` avec `CARNET_SECRET_KEY` (et **sans** `CARNET_ENV=development`), `TRUST_PROXY=1` derrière un proxy, éventuellement `ALLOW_REGISTRATION=0` ; servir en HTTPS ; placer `carnet.db` sur un stockage persistant ; puis `python scripts/check_env.py`. Environ une fois par mois : `python scripts/check_updates.py` (mises à jour et failles connues).

## Tests

```bash
pip install -r requirements-dev.txt
pytest                                   # toute la suite
pytest tests/unit                        # uniquement les fonctions pures (très rapide)
pytest -k recherche                      # tests dont le nom contient « recherche »
pytest --cov=src --cov-report=term-missing   # couverture, avec les lignes non testées
```

La suite (896 tests, une trentaine de secondes) couvre l'ensemble du code Python : **99 % des lignes** (les deux seules lignes non couvertes sont une protection défensive de la page Carnet). Chaque test travaille sur une base SQLite temporaire neuve : aucune donnée réelle n'est touchée. Les tests ne s'exécutent **pas** sur ta base `carnet.db` : `tests/conftest.py` redirige `CARNET_DATABASE` vers un dossier temporaire, donc ni `carnet.db` ni `.secret_key` ne sont ouverts ni modifiés (des tests de `test_config.py` le vérifient).

| Dossier | Ce qui est vérifié |
|---|---|
| `tests/unit/` | scripts de vérification, cotations « entre deux » et conversion alpine, formatage et comparaison de noms, validation des séances, des choix et de la fiche d'infos, calendrier des saisons, constantes, configuration, erreurs |
| `tests/services/` | schéma et migrations d'anciennes bases, lieux (création, renommage, suppression en cascade), ascensions (doublons, séances, longueurs), carnet, projets, tick list, stats (règle « en tête uniquement », mètres, évolution), recherche (chaque filtre, tris, calendrier), bibliothèque de topos PDF (validation, doublons, bouton « Topo » par lieu, migration de l'ancienne table), exports CSV et PDF, restauration |
| `tests/routes/` | **sécurité** (CSRF, CSP et nonce, en-têtes, HTTPS, limitation des essais, anti-robots, droits d'administrateur), connexion / inscription, protection des pages, toutes les routes d'API, le parcours « passage en projet » (Tick List et ajout d'un projet), dont la bibliothèque de topos PDF (envoi, affichage, renommage, suppression, bouton « Topo ») (cas valides, erreurs 400 / 404 / 409, isolation entre deux comptes), exports, sauvegarde et restauration |

## Documentation

La documentation détaillée est dans le dossier [`docs/`](docs/) :

| Fichier | Contenu |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | organisation du code (routes → services → base), cycle d'une requête, démarrage, erreurs, sécurité, front-end (JS et CSS), comment ajouter une fonctionnalité |
| [`docs/FONCTIONNALITES.md`](docs/FONCTIONNALITES.md) | chaque page et toutes les règles métier : cotations « entre deux », statuts, doublons, séances, règle « en tête uniquement » des stats, exports |
| [`docs/MODELE_DONNEES.md`](docs/MODELE_DONNEES.md) | les 18 tables, leurs colonnes, valeurs autorisées, intégrité et migrations |
| [`docs/API.md`](docs/API.md) | toutes les routes avec corps de requête, réponses et codes d'erreur |
| [`docs/SECURITE.md`](docs/SECURITE.md) | sessions, CSRF, CSP, limitation des abus, administrateur, publication sur GitHub, que faire en cas de fuite |

Quand une règle change, mettre à jour le README et le fichier de `docs/` concerné.
