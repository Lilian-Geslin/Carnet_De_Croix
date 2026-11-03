"""Logique métier, indépendante de Flask : chaque module reçoit une connexion SQLite et des données simples.

Place dans l'application : les routes (dossier `routes/`) ne font que lire la requête HTTP, puis
appellent les fonctions de ce paquet, qui parlent à la base SQLite et renvoient des dictionnaires /
listes simples (ou lèvent une erreur de `errors.py`). Rien ici ne dépend de Flask, ce qui permet de
tester chaque module avec une simple connexion SQLite (voir `tests/services/`).

Vocabulaire commun à tous les modules :
- une « ascension » est une ligne de la table `ascension`, avec un `statut` :
  « log » (voie réalisée), « projet » (en cours de travail) ou « ticklist » (envie, à faire un jour) ;
- les lieux forment une hiérarchie pays › département › localisation › site › secteur › sous-secteur ;
- `uid` est toujours l'identifiant de l'utilisateur connecté : chaque requête filtre dessus.
"""
