# Politique de sécurité

## Signaler une vulnérabilité

Si tu penses avoir trouvé une faille de sécurité dans Carnet de Croix, **merci de ne pas
ouvrir une issue publique** : cela exposerait la faille avant qu'elle soit corrigée.

Utilise plutôt le signalement privé de GitHub :

1. Va dans l'onglet **Security** du dépôt.
2. Clique sur **Report a vulnerability**.
3. Décris le problème : où il se trouve, comment le reproduire, et son impact possible.

Je répondrai dès que possible et te tiendrai au courant de la correction.

## Ce qui est utile dans un signalement

- la page ou la route concernée ;
- les étapes pour reproduire le problème ;
- ce qu'un attaquant pourrait faire (lire le carnet d'un autre compte, voler une session, etc.).

## Merci de ne pas

- tester la faille sur une instance en ligne avec les données d'autres personnes ;
- accéder, modifier ou supprimer des données qui ne t'appartiennent pas ;
- effectuer des attaques par saturation (déni de service).

## Ce qui est déjà en place

Protection CSRF, en-têtes CSP (scripts signés par un nonce) et HSTS, limitation des tentatives de
connexion, sauvegarde réservée à l'administrateur, aucune ressource externe. Le détail est dans
[docs/SECURITE.md](docs/SECURITE.md).

## Ce qui ne doit jamais être publié

La base `carnet.db`, un fichier `.env`, l'ancien fichier `.secret_key`. Ils sont exclus par
`.gitignore` ; `python scripts/check_env.py` vérifie qu'ils ne sont pas suivis par Git.
