# Sécurité et vie privée

Ce document décrit ce qui protège Carnet de Croix et comment le vérifier. Pour signaler une faille, voir [SECURITY.md](../SECURITY.md) à la racine.

## Sommaire

1. [Sessions et comptes](#sessions-et-comptes)
2. [Protection contre les attaques web](#protection-contre-les-attaques-web)
3. [Limitation des abus](#limitation-des-abus)
4. [Sauvegarde et restauration réservées à l'administrateur](#sauvegarde-et-restauration-réservées-à-ladministrateur)
5. [Fichiers envoyés](#fichiers-envoyés)
6. [Journaux et secrets](#journaux-et-secrets)
7. [Dépendances](#dépendances)
8. [Publier le code sur GitHub](#publier-le-code-sur-github)
9. [En cas de fuite](#en-cas-de-fuite)
10. [Vérifié par les tests](#vérifié-par-les-tests)

## Sessions et comptes

- Mots de passe stockés **hachés** (Werkzeug), 8 à 128 caractères. À la connexion, un calcul de hachage est toujours fait (même sans compte) et le message d'erreur est identique : impossible de deviner quels emails existent.
- Cookie de session `HttpOnly`, `SameSite=Lax`, `Secure` en production, durée **30 jours**. La session est vidée et recréée à chaque connexion (pas de fixation de session).
- Clé `CARNET_SECRET_KEY` **obligatoire** (16 caractères minimum) : l'application refuse de démarrer sans elle. Plus aucune clé n'est écrite dans un fichier.
- À **chaque requête**, le compte est relu en base : compte supprimé → déconnecté tout de suite.
- **Production par défaut** : sans `CARNET_ENV=development`, le cookie est sécurisé, HTTPS est forcé et HSTS est envoyé.
- Déconnexion en **POST** avec jeton (un lien piégé ne peut pas déconnecter).
- `ALLOW_REGISTRATION=0` ferme les inscriptions (instance personnelle).

## Protection contre les attaques web

| Mesure | Détail |
|---|---|
| **CSRF** | jeton de session obligatoire sur tout `POST/PUT/PATCH/DELETE` (champ `csrf_token` ou en-tête `X-CSRF-Token`). Le JavaScript l'ajoute tout seul à tous ses `fetch` (`static/js/core/csrf.js`). Sans jeton : 400 |
| **CSP** | `default-src 'self'` ; scripts : `'self'` + **nonce** par requête (aucun script en ligne non signé) ; styles `'self' 'unsafe-inline'` ; polices `'self'` ; images `'self' data:` ; `connect-src 'self'` ; `object-src 'none'` ; `frame-ancestors 'none'` ; `form-action 'self'` ; `base-uri 'self'` |
| **Aucune ressource externe** | les polices (Bebas Neue, DM Sans, licence SIL OFL) et Chart.js (licence MIT) sont **hébergés dans le projet** : aucun appel à Google ni à un CDN, donc ni suivi des visiteurs ni script tiers |
| **En-têtes** | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` (géolocalisation, micro, caméra, paiement désactivés), `Cache-Control: no-store` sur les pages, **HSTS** 180 jours en production |
| **HTTPS** | redirection 301 si `X-Forwarded-Proto: http` (production, `FORCE_HTTPS` ≠ 0) |
| **XSS** | Jinja2 échappe tout ; les noms de lieux saisis par l'utilisateur sont échappés (`escHtml`) avant d'entrer dans le HTML construit en JavaScript ; liens de topo limités à http/https |
| **Injection SQL** | requêtes paramétrées ; les noms de tables et de colonnes viennent toujours du code (liste blanche `GEO_TABLES`, champs validés), jamais de l'utilisateur |
| **Clickjacking** | `X-Frame-Options: DENY` et `frame-ancestors 'none'` |
| **Isolation des comptes** | chaque requête filtre sur l'utilisateur connecté ; la ressource d'un autre compte donne 404 |

## Limitation des abus

Les compteurs sont **en base** (table `auth_attempt`) et non en mémoire : un hébergeur lance souvent plusieurs processus, et une limite gardée en mémoire serait contournable. Avec `TRUST_PROXY=1`, l'adresse IP est lue dans `X-Real-IP` puis `X-Forwarded-For` (dernière adresse, celle ajoutée par le proxy de confiance) ; sans ce réglage ces en-têtes, falsifiables, sont ignorés.

| Action | Limite |
|---|---|
| Connexion | 5 échecs / 15 min par couple (email + IP) ; 50 par IP ; 100 par email |
| Inscription | 50 par heure et par IP + champ piège anti-robots + jeton daté (refusé si envoyé en moins de 2 s ou après 6 h) |

Dépasser une limite donne `429` (« Trop de tentatives. Réessayez dans quelques minutes. »). Un succès remet à zéro le compteur du couple email + IP. Les lignes de plus de 24 h sont effacées.

## Sauvegarde et restauration réservées à l'administrateur

Le fichier de base contient **tous les comptes** (dont les mots de passe hachés). `/backup` et `/restore` sont donc réservés à l'administrateur (403 sinon), et les boutons n'apparaissent pas pour les autres. L'administrateur est le compte dont l'email est `CARNET_ADMIN_EMAIL` ; à défaut, le **premier compte créé**. Les exports CSV et PDF, eux, ne contiennent que les données de l'utilisateur connecté.

## Fichiers envoyés

- **Topos PDF** : 20 Mo maximum, signature `%PDF` vérifiée, doublons détectés par empreinte, servis avec `nosniff`.
- **Restauration** : le fichier doit être une base SQLite contenant au moins les tables `user` et `ascension` ; l'ancienne base est conservée en `.before_restore`.
- Taille maximale d'une requête : `CARNET_MAX_UPLOAD_MB` (256 Mo par défaut).

## Journaux et secrets

- `RedactSecretsFilter` remplace par `***` les valeurs de `api_key=`, `token=`, `secret=`, `password=` dans les messages de journal.
- Le `.env` contient les secrets : **jamais versionné** (`.gitignore`), droits `600` conseillés sous Linux ; `python scripts/check_env.py` le vérifie **sans afficher les valeurs** (et signale si `.env`, la base ou `.secret_key` sont suivis par Git).
- Le débogueur interactif de Werkzeug (qui permet d'exécuter du code depuis le navigateur) est désactivé, même en développement (`use_debugger=False`).

## Dépendances

Versions **épinglées** dans `requirements.txt`. `python scripts/check_updates.py` (environ une fois par mois) liste les mises à jour disponibles et, si `pip-audit` est installé, les failles connues ; il ne modifie rien. Sur GitHub : Dependabot propose les mises à jour (`.github/dependabot.yml`) et l'intégration continue (`.github/workflows/ci.yml`) lance les tests et `pip-audit` à chaque modification, puis chaque lundi.

## Publier le code sur GitHub

Un dépôt public se **lit** et se **copie sur GitHub** (fork) ; seuls les collaborateurs invités peuvent y **écrire**. La licence (tous droits réservés) interdit toute réutilisation sans accord. À vérifier avant et après publication :

- `.env`, `carnet.db` (et ses copies) et `.secret_key` ne sont pas dans le dépôt : `git status` ne doit pas les lister, et `python scripts/check_env.py` doit afficher « Ni .env, ni la base… ».
- Réglages GitHub : authentification à deux facteurs sur le compte ; protection de la branche `main` (pull request obligatoire, pas de force-push) ; **Secret scanning** et **Push protection** ; **Dependabot alerts** ; **Private vulnerability reporting** ; droits du jeton Actions en lecture seule.

## En cas de fuite

Si `.env`, la base ou une clé a été publié par erreur : (1) changer `CARNET_SECRET_KEY` (toutes les sessions deviennent invalides) ; (2) considérer les mots de passe comme exposés et demander aux utilisateurs d'en changer ; (3) retirer le fichier de l'**historique** Git (supprimer le fichier ne suffit pas : il reste dans les anciens commits) avec `git filter-repo`, ou recréer le dépôt ; (4) forcer la mise à jour du dépôt distant.

## Vérifié par les tests

`tests/routes/test_security.py` (CSRF, CSP et nonce, en-têtes, HTTPS, honeypot, limitation, compte supprimé, droits d'administrateur, journaux), `tests/routes/test_auth_pages.py`, `tests/unit/test_config.py` (clé obligatoire, production par défaut), `tests/unit/test_scripts.py`, `tests/services/test_schema.py`.
