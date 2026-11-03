# Fonctionnalités et règles métier

Ce document décrit ce que fait Carnet de Croix, page par page, et surtout **les règles qui gouvernent les données** (qui compte pour quoi, comment on compare deux cotations, ce qui est supprimé avec quoi…). Pour l'organisation du code, voir [ARCHITECTURE.md](ARCHITECTURE.md) ; pour les tables, [MODELE_DONNEES.md](MODELE_DONNEES.md) ; pour les routes, [API.md](API.md).

## Sommaire

1. [Concepts de base](#concepts-de-base)
2. [Cotations](#cotations)
3. [Ajouter une ascension](#ajouter-une-ascension)
4. [Page Carnet](#page-carnet)
5. [Page Projets et séances](#page-projets-et-séances)
6. [Page Tick List](#page-tick-list)
7. [Page Recherche](#page-recherche)
8. [Page Stats](#page-stats)
9. [Fenêtre « Plus d'informations »](#fenêtre--plus-dinformations-)
10. [Topos](#topos)
11. [Répétitions](#répétitions)
12. [Lieux](#lieux)
13. [Exports, sauvegarde et restauration](#exports-sauvegarde-et-restauration)
14. [Comptes et confidentialité](#comptes-et-confidentialité)
15. [Tableau récapitulatif des règles](#tableau-récapitulatif-des-règles)

---

## Concepts de base

**Ascension.** Une voie ou un bloc, quel que soit son état. C'est l'objet central.

**Statut.** Dit où en est l'ascension et sur quelle page elle apparaît :

| Statut | Signification | Page |
|---|---|---|
| `log` | réalisée | Carnet (et Stats) |
| `projet` | essayée, pas encore réussie | Projets |
| `ticklist` | simple envie, à faire un jour | Tick List |

Une ascension change de statut au fil du temps : une envie devient un projet (« ⚡ Projet » de la Tick List, qui ouvre le formulaire de séance), un projet devient un log (« Marquer comme grimpé » ou « Projet réussi »). Elle ne repart jamais en arrière.

**Types d'ascension.**

| Type | Libellé affiché | Remarques |
|---|---|---|
| `bloc` | Bloc | départ et arrivée spécifiques |
| `voie` | Voie | sur corde : mode de grimpe |
| `grande_voie` | Grande Voie | plusieurs longueurs, cotation basse → haute |
| `trad_voie` | Trad | voie en équipement mobile (coinceurs) |
| `trad_gv` | Trad GV | grande voie en trad |
| `psychobloc` | Psychobloc | bloc au-dessus de l'eau |

Les types « grandes voies » sont `grande_voie` et `trad_gv`. Les types « sur corde » sont `voie`, `grande_voie`, `trad_voie`, `trad_gv`.

**Mode de grimpe.** *En tête* ou *moulinette*. **Obligatoire** pour une ascension réalisée (log) ou une répétition d'un type sur corde ; sans objet pour les blocs, les projets et les envies.

**Style (nombre d'essais).** À vue, Flash, 1 à 5 essais, plus de 5 essais. Pour les graphiques, les styles sont regroupés en trois catégories : *À vue*, *Flash*, *Travaillé* (tous les nombres d'essais).

## Cotations

**Échelle.** De `3a` à `9c`, avec les « + » (`3a`, `3a+`, `3b`… `9b+`, `9c`). L'ordre de cette liste (`GRADE_ORDER`) définit la difficulté : on compare toujours des **positions**, jamais des textes (`"6c+"` et `"7a"` ne se comparent pas alphabétiquement).

**Cotation « entre deux ».** Un bouton « / » à côté des sélecteurs de cotation bascule sur la version intermédiaire : `7a/+` signifie « entre 7a et 7a+ », `7a+/b` « entre 7a+ et 7b ». La valeur est stockée telle quelle, avec le slash.

| Usage | Comment `7a/+` est traitée |
|---|---|
| Stats (répartition par cotation), filtres min/max de la Recherche | comme `7a` (le niveau **avant** le slash) |
| Tri et « cotation max » | **entre** `7a` et `7a+` (juste au-dessus de 7a, sous 7a+) |

Pas de version « entre deux » pour `9c` (rien au-dessus). Le bouton « / » est alors désactivé.

**Grandes voies.** Une grande voie a une cotation **basse** et une cotation **haute** (le passage le plus dur). Pour tout calcul de difficulté (stats, tri, max, tick list), la **cotation effective** est la cotation **haute**.

**Cotation alpine.** Pour une grande voie, la cotation alpine est déduite de la cotation haute (ex. `5c+` → `D+`). Chaque repère est le seuil bas de son palier :

| Alpine | À partir de | Alpine | À partir de |
|---|---|---|---|
| F | 2 (hors échelle) | TD− | 6a |
| PD | 3a | TD | 6b |
| AD− | 4a | TD+ | 6c |
| AD | 4b | ED− | 7a |
| AD+ | 4c | ED | 7b |
| D− | 5a | ED+ | 7c |
| D | 5b | ABO− | 8a |
| D+ | 5c | ABO | 8b |
| | | ABO+ | 8c |

**Ma cotation (`cotation_perso`).** La cotation ressentie par l'utilisateur, distincte de la cotation officielle. Elle est enregistrée mais n'entre dans aucun calcul de stats.

**Ordre d'affichage des ascensions d'un secteur.** 1) cotation la plus dure d'abord, 2) à cotation égale, date la plus récente d'abord, 3) à date égale, ordre alphabétique (sans casse ni accents).

## Ajouter une ascension

Le bouton « + Ajouter une ascension » ouvre une fenêtre en deux étapes (la même fenêtre sert à modifier).

**Étape 1 : où et quoi.** Pays, département, localisation, site, secteur, sous-secteur (champs avec suggestions des lieux déjà saisis, remplis en cascade), le *ressenti* indicatif du secteur, le **type d'escalade** puis le **statut** (Carnet, Projet ou Tick List ; masqué en modification, et imposé sur les pages Projets et Tick List).

Règles de saisie des lieux :
- **pays, département et site sont obligatoires** ;
- une localisation laissée vide devient « Principale », un secteur vide « Principal » ;
- les noms sont nettoyés (espaces) ; le sous-secteur est facultatif ;
- si un lieu n'existe pas encore, il est **créé automatiquement** ; sinon il est réutilisé.

**Étape 2 : formulaire détaillé**, qui s'adapte au type et au statut :

| Champ | Où |
|---|---|
| Nom | toujours |
| Type de départ (normal, assis, jeté, run & jump) et type d'arrivée (normal, reta) | blocs et psychoblocs |
| Cotation unique | tout sauf grandes voies |
| Plage de cotation basse → haute, nombre de longueurs, détail de chaque longueur | grandes voies |
| En tête / moulinette | types sur corde ; **obligatoire pour un log** |
| Ma cotation | toujours |
| Style (à vue, flash, essais), date, pieds nus, note de beauté (1 à 5 étoiles) | log |
| Nombre d'essais déjà faits et date de la séance | projet (devient la **séance n°1**) ; une fois le projet ajouté, l'application **propose de détailler la séance** (voir ci-dessous) |
| Catégorie d'envie (Performance, Beauté, Majeure) | tick list |
| Hauteur (m), commentaire | toujours |

**Détection des doublons.** Avant d'écrire, l'application cherche dans le même secteur / sous-secteur une ascension identique, **tous statuts confondus**. Critères comparés : type, nom, cotation basse, cotation haute, nombre de longueurs, type de départ, type d'arrivée. La comparaison ignore la casse, les accents et les espaces (« Voie  Éole » = « voie eole ») et un départ/arrivée vide équivaut à « normal ». Sont **ignorés** : ma cotation, essais, date, pieds nus, note, hauteur, commentaire, mode de grimpe. S'il y a plusieurs correspondances, on retient le log, puis le projet, puis l'envie. Quand un doublon est trouvé, rien n'est écrit : le navigateur propose d'ajouter une **répétition** à la place.

## Page Carnet

Arbre déroulant **Pays › Département › Localisation › Site › Secteur › Sous-secteur › Ascension**, un `<details>` par niveau.

- Seules les ascensions **loguées** apparaissent ; un niveau qui ne contient que des projets ou des envies n'est pas affiché.
- Chaque niveau affiche un compteur ; les secteurs et sous-secteurs affichent leur *ressenti* (« Coté difficilement »…) quand il est renseigné.
- Des boutons apparaissent au survol d'un niveau : **ajouter** (ouvre la fenêtre d'ajout pré-remplie avec ce lieu), **renommer** (et modifier le ressenti pour un secteur/sous-secteur) et **supprimer**.
- Un bouton **📖 Topo**, qui apparaît au survol comme renommer et supprimer, existe pour les **localisations, sites, secteurs et sous-secteurs** (pas pour les pays ni les départements). Il ouvre la liste des topos de ce lieu (voir [Topos](#topos)).
- Après un ajout, la page se recharge avec `?open_secteur=<id>` : les niveaux menant à ce secteur sont dépliés d'office.
- Chaque **carte d'ascension** montre : type, nom, cotation (pour une grande voie « basse → haute (alpine) »), date, note, badges (style, pieds nus, hauteur, mode de grimpe, type de départ), commentaire, les **longueurs** d'une grande voie et les **répétitions**. Actions : modifier, supprimer, ajouter une répétition, « Plus d'informations ».

## Page Projets et séances

Un **projet** est une voie ou un bloc travaillé sans l'avoir encore réussi.

**Détailler la séance après un ajout.** Quand on ajoute un **projet** (depuis le Carnet ou n'importe quelle page), une question propose de détailler la séance maintenant. *OK* : on arrive sur la page Projets avec la fenêtre des séances déjà ouverte (sur la séance n°1 en modification s'il y avait des essais, sinon sur une nouvelle séance n°1) pour ajouter date, nombre d'essais et mini-journal. *Annuler* : on arrive simplement sur la page Projets. L'adresse `/projets?seance=<id>` ouvre ainsi la fenêtre d'un projet.

**Cartes de projet.** Nom, type, cotation, lieu, nombre de séances, total d'essais, mini-histogramme des **14 dernières séances** (la dernière en or), dernier commentaire.

**Barre d'outils** (appliquée côté navigateur, choix mémorisés) : recherche texte, discipline, site, cotation minimale, tri (cotation, dernière séance, nombre d'essais, nombre de séances, nom), regroupement (par site, par secteur ou aucun). Les groupes sont repliables.

**Séances.** Une séance = un jour d'essais : numéro (1, 2, 3…), date, nombre d'essais, mini-journal.

| Règle | Détail |
|---|---|
| Numérotation | automatique : précédente + 1 ; supprimer une séance **renumérote** les suivantes |
| Date | obligatoire à la création (format `AAAA-MM-JJ`), peut être effacée en modification |
| Nombre d'essais | entre **1 et 999** |
| Commentaire | facultatif, 5 000 caractères maximum |
| Total d'essais du projet | **toujours recalculé** (somme des séances), jamais saisi à la main |
| Compteur du formulaire | boutons − / + ; si le compteur n'est pas à 0 en cliquant sur « Projet réussi », ces essais sont d'abord enregistrés comme une séance |

**Projet réussi.** Le bouton « ✓ Projet réussi : l'ajouter au carnet » ouvre « Marquer comme grimpé » : style, date, note, ma cotation, pieds nus, mode de grimpe (obligatoire sur corde). Le projet devient un `log` ; son **journal de séances est conservé** et reste consultable dans la fiche « Plus d'informations ».

## Page Tick List

Les **envies** : voies et blocs à faire un jour.

- **Catégorie** facultative, une seule par envie : *Performance*, *Beauté*, *Majeure* (anciennement « Classique » : les envies déjà classées ainsi sont converties automatiquement) (modifiable depuis la liste).
- **Vues** : *Liste* et *Paliers*. La vue Paliers range les envies en colonnes par cotation : un palier regroupe tout ce qui est ≤ 5c+, puis un palier par niveau (6a = 6a et 6a+, 6b = 6b et 6b+, etc.) ; les envies sans cotation sont à part.
- **Filtres, tri et regroupement** : recherche, discipline, catégories ; tri par cotation (dure ou facile) ou nom ; regroupement par site ou par catégorie.
- **Repère « plus dur que ce que j'ai fait »** : chaque envie est comparée à la meilleure cotation **déjà réalisée dans sa discipline** (logs uniquement). Si elle est plus dure, un signe l'indique ; si rien n'a encore été réalisé dans cette discipline, il n'y a pas de repère.
- **Cocher** une envie ouvre « Marquer comme grimpé » (elle devient un log) ; **⚡ Projet** ouvre directement le **formulaire de séance complet** (date, nombre d'essais avec + / −, mini-journal) : *Enregistrer la séance* passe l'envie en projet avec cette séance n°1 ; *Passer en projet sans séance* la passe en projet sans rien enregistrer ; fermer la fenêtre ne change rien ; **✕** supprime.

## Page Recherche

Barre de recherche + filtres combinables. La page se met à jour **en direct** à chaque changement (les saisies de texte sont retardées de 280 ms), et l'URL reflète les filtres (la page peut être partagée ou mise en favori).

**Périmètre** : Carnet (défaut), Projets, Tick list ou Tout.

**Filtres** (chacun ouvre une fenêtre flottante ; les filtres actifs deviennent des pastilles qu'on retire d'un clic) :

| Filtre | Détail |
|---|---|
| Texte (`q`) | nom de l'ascension, site, localisation, secteur, sous-secteur, commentaire |
| Type | un ou plusieurs types d'ascension |
| Cotation | minimum et maximum (« entre deux » compte comme son niveau avant le slash) |
| Style | à vue, flash, nombre d'essais |
| Beauté | 1 à 5 étoiles |
| Dates | sélection de jours dans un **calendrier** ; les jours ayant au moins un log sont cliquables ; navigation de mois en mois sans recharger |
| Plus de filtres | hauteur min/max, année d'ouverture min/max, ouvreur, topo, type de roche, type de grimpe, mode (en tête / moulinette), pieds nus |

**Tri** : date (récente / ancienne), cotation, style, beauté, hauteur, nom. **Regroupement** : par site (un bandeau par site, avec son lieu et son nombre de résultats) ou à plat.

**Synthèse** au-dessus des résultats : nombre de résultats, nombre de sites, cotation max, mètres. Pour une grande voie sans hauteur saisie, on prend la somme de ses longueurs.

Détails de fonctionnement : les cotations étant du texte, la fourchette de cotation est appliquée **en Python** après la requête SQL ; les valeurs inconnues dans l'URL sont ignorées ; les valeurs saisies passent toujours en paramètres SQL.

## Page Stats

Cinq blocs.

### 1. Exploration

Nombre de pays, départements, localisations, sites, secteurs et sous-secteurs qui contiennent **au moins une ascension loguée**. Un niveau qui ne contient que des projets ou des envies n'est pas compté, et l'exclusion remonte la hiérarchie. **Cette partie compte toutes les ascensions loguées, y compris les voies en moulinette.**

### 2. Meilleure performance

Cotation max toutes disciplines, nombre total d'ascensions comptées, total de mètres.

### 3. Détail par discipline

Un bloc par type qui a au moins une ascension comptée : nombre, mètres, cotation max, graphe de **répartition par cotation** (avec un interrupteur « empiler par style »), graphe de **répartition à vue / flash / travaillé**, et cotation max par style.

### Règle « en tête uniquement » ★

> **Pour la voie et le trad (voie), seules les ascensions grimpées en tête sont comptabilisées.** Pour les grandes voies (normale et trad) et les autres disciplines, toutes les ascensions comptent.

| Type | Compté dans les stats si… |
|---|---|
| Voie, Trad (voie) | `grimpe = 'tete'` |
| Grande voie, Trad GV | toujours |
| Bloc, Psychobloc | toujours |

Conséquences :
- une ascension en **moulinette** reste enregistrée (visible dans le Carnet, la Recherche, les exports) mais **n'apparaît pas** dans les stats : ni dans les chiffres, ni dans les graphes, ni dans l'évolution, ni dans le résumé du PDF ;
- la règle s'applique aussi aux **répétitions** (une répétition en moulinette n'ajoute pas de mètres) ;
- le total d'ascensions et la cotation max globale ne tiennent compte que des ascensions comptées ;
- une phrase au-dessus du diagramme le rappelle : *« Seules les ascensions grimpées en tête sont comptabilisées. »* ;
- **les anciennes voies sans mode renseigné** (créées avant l'existence du champ) ne comptent pas non plus ; la phrase ajoute alors « N sans précision, non comptée(s) » pour que l'écart ne passe pas inaperçu. Pour les compter, il suffit de modifier l'ascension et d'indiquer « en tête ».

Autres règles de calcul :
- **Une ascension compte une seule fois**, même refaite plusieurs fois : les répétitions n'ajoutent que des **mètres** (`mètres = hauteur × (1 + nombre de répétitions comptées)`).
- **Hauteur** : celle saisie ; pour une grande voie sans hauteur, la somme de ses longueurs.
- La répartition utilise la **cotation effective** (haute pour une grande voie) et le niveau de base d'une cotation « entre deux ».

### 4. Évolution

Courbe de la **cotation max atteinte par saison**, un trait par discipline (légende colorée).

| Saison | Début | Fin |
|---|---|---|
| Printemps | 20/03 | 20/06 |
| Été | 21/06 | 21/09 |
| Automne | 22/09 | 20/12 |
| Hiver | 21/12 | 19/03 |

Calendrier fixe ; l'hiver, à cheval sur deux années, est rattaché à l'année où il commence (« Hiver 2024-25 »). Une saison sans ascension fait retomber la courbe au plus bas ; la courbe d'une discipline ne démarre qu'à sa première saison. Seules les ascensions **datées et comptées** entrent dans l'évolution.

### 5. Export et sauvegarde

Voir [Exports, sauvegarde et restauration](#exports-sauvegarde-et-restauration).

## Fenêtre « Plus d'informations »

Accessible depuis chaque ascension du Carnet et de la Recherche. Deux modes :

- **Fiche en lecture** (par défaut) : texte mis en forme, avec « Non renseigné » pour les champs vides ;
- **Formulaire** (bouton « Ajouter / modifier des informations ») : modifications abandonnées après confirmation si l'on quitte sans enregistrer.

Contenu :

| Section | Détail |
|---|---|
| **Ouverture** | année d'ouverture (entre 1800 et l'an prochain), ouvreur, **rééquipements** (« rééquipé par … en … », jusqu'à 20) |
| **Séances** | séances de projet liées (lecture seule) avec leur mini-journal, nombre de séances et total d'essais |
| **Topo consulté** | support *Papier* (titre, édition, année de publication, page) ou *PDF / en ligne* (titre facultatif, lien, et **PDF choisi dans la bibliothèque de topos du site**) |
| **Type de grimpe** | pastilles : mur vertical, dalle, dévers, toit, fissure, traversée, dièdre, arête, cheminée… |
| **Type de roche** | calcaire, granite, grès, gneiss, conglomérat, basalte, quartzite, rhyolite… |
| **Fixations** | voie et grande voie : broches, goujons, pitons, spits… |
| **Coinceurs** | trad et trad GV : câblés, hexagonaux, friends… |

Règles :
- Les listes de propositions sont **personnelles** : on peut en **ajouter** (barre « choisir ou ajouter ») et en **supprimer** (✕ dans la liste). Supprimer une proposition **ne touche pas** aux ascensions qui l'avaient déjà choisie. Nom : 40 caractères maximum ; 60 propositions maximum par liste ; doublons détectés sans tenir compte de la casse.
- Un **lien de topo** n'est accepté que s'il est en `http(s)` ; sans schéma (`exemple.fr/topo.pdf`), `https://` est ajouté ; les autres schémas (`javascript:`, `file:`…) sont refusés. Il s'ouvre dans un nouvel onglet.
- **Topo PDF** (support *PDF / en ligne*) : la fiche propose une liste « PDF enregistré dans le site » (les topos du **même site** d'abord, puis les autres) ; on choisit un topo, ou on en ajoute un avec « Ajouter un PDF… ». **Le choix est enregistré avec la fiche** (bouton Enregistrer). Voir [Topos](#topos).
- Tout est **validé avant la moindre écriture** : une erreur n'enregistre rien.
- Les noms saisis (ouvreurs, topos) deviennent des **suggestions** pour les saisies suivantes.

## Topos

Les topos PDF forment une **bibliothèque** personnelle : chaque fichier n'est enregistré qu'**une seule fois** dans la base, même s'il sert à 20 blocs d'un même secteur.

**Enregistrer un topo.** Deux endroits :
- dans la fiche « Plus d'informations » d'une ascension (« Ajouter un PDF… ») : le topo est rattaché au secteur (ou sous-secteur) de l'ascension et sélectionné dans la liste ; il est associé à l'ascension quand on clique sur *Enregistrer* ;
- dans la fenêtre du bouton **Topo** d'un lieu (« + Ajouter un topo PDF… ») : il est rattaché à ce lieu.

**Règles du fichier.** PDF uniquement (le contenu est vérifié, pas seulement l'extension), 20 Mo maximum. Le titre par défaut est le nom du fichier sans « .pdf » ; on peut le **renommer** depuis la fenêtre Topo.
- **Pas de doublon** : si le même fichier (même contenu) est déjà enregistré, il est réutilisé au lieu d'être copié, et son titre est conservé.
- **Nouvelle édition** : un fichier différent est un **nouveau topo**. Les anciennes ascensions gardent l'ancien topo ; les nouvelles peuvent choisir le nouveau ; les deux apparaissent dans le bouton Topo du lieu.

**Bouton Topo d'un lieu.** Liste, en trois sections, ce qui est utilisé **dans ce lieu et en dessous** (projets et envies compris) :
- *Topos PDF* : ceux choisis par une ascension du lieu ou rattachés au lieu (ou à un lieu en dessous), avec leur taille et le nombre d'ascensions concernées. Boutons : **Ouvrir** (lecteur PDF du navigateur, nouvel onglet), **renommer** (✏), **supprimer** (✕) ;
- *Topos papier* : titre, édition et année renseignés sur les ascensions, regroupés quand ils sont identiques (casse ignorée) ;
- *Liens en ligne* : liens de topo renseignés sans fichier enregistré.

Un **site** n'affiche que ses propres topos ; une **localisation** affiche ceux de tous ses sites. Un topo ajouté depuis un site apparaît dans ce site et dans sa localisation, pas dans un site voisin.

**Suppression.** Supprimer un topo (✕) le retire de la bibliothèque ; les ascensions qui l'utilisaient perdent seulement ce lien (rien d'autre n'est touché), après confirmation indiquant leur nombre. Supprimer une ascension ne supprime **jamais** un topo (d'autres peuvent l'utiliser) ; supprimer un lieu supprime seulement le rattachement. Un topo n'est visible que par son propriétaire.

**Mise à jour depuis la version précédente.** Les PDF enregistrés ascension par ascension sont convertis automatiquement : les contenus identiques d'un même compte sont fusionnés en un seul topo.

## Répétitions

Une **répétition** est une voie déjà loguée que l'on refait à une autre date. Elle ne crée pas de nouvelle ascension : elle s'ajoute à celle existante (donc elle ne change pas le nombre d'ascensions, seulement les mètres).

Champs : date (obligatoire), nombre d'essais, mode de grimpe (obligatoire sur corde), ma cotation, pieds nus, note, commentaire. Elles apparaissent sur la carte de l'ascension et dans le PDF, et peuvent être supprimées une à une.

## Lieux

- **Hiérarchie** : pays › département › localisation › site › secteur › sous-secteur (facultatif). Chaque utilisateur a ses propres lieux.
- **Renommer** : possible à chaque niveau. Un nom déjà utilisé au même endroit est refusé (« existe déjà à cet endroit »). Pour un secteur ou sous-secteur, on peut aussi changer le *ressenti*.
- **Ressenti** : repère indicatif de cotation d'un secteur (*Coté très difficilement*, *difficilement*, *Bien coté*, *facilement*, *très facilement*), pré-rempli quand on retrouve un secteur connu. N'entre dans aucun calcul.
- **Supprimer** : supprime le lieu, **tous ses niveaux enfants et toutes leurs ascensions** (avec répétitions, longueurs, séances…). Action **définitive** : la page demande une confirmation.

## Exports, sauvegarde et restauration

Depuis la page **Stats**.

| Action | Résultat |
|---|---|
| **Export CSV** | un ZIP de 4 fichiers liés par `ascension_id` : `ascensions.csv` (tous statuts, avec lieux, topo, choix, rééquipements en une cellule « a \| b »), `longueurs.csv`, `repetitions.csv`, `seances.csv`. Ne contient que **tes** données (un topo PDF n'y figure que par son titre, colonne `topo_pdf`, jamais le fichier). |
| **Export PDF** | une page de résumé (compteurs de lieux, chiffres par discipline : nombre, mètres, cotation max) puis un tableau **chronologique** de toutes les ascensions loguées et de leurs répétitions (la plus récente d'abord). Le **résumé** suit la règle « en tête uniquement » comme la page Stats ; la **liste**, elle, contient toutes les ascensions loguées. |
| **Sauvegarder la base** | télécharge une copie brute de `carnet.db` (⚠️ tous les comptes de la base ; les topos PDF enregistrés y sont inclus, la sauvegarde peut donc être volumineuse). |
| **Restaurer une sauvegarde** | remplace la base par le fichier `.db` envoyé. |

Règles de la restauration : le fichier doit être une base SQLite contenant au moins les tables `user` et `ascension` ; l'ancienne base est conservée sous `carnet.db.before_restore` ; une sauvegarde d'une ancienne version est **migrée automatiquement** ; la restauration remplace les données de **tous** les comptes.

## Comptes et confidentialité

- Inscription (prénom, email, mot de passe de 8 à 128 caractères) puis connexion ; l'email est unique (sans tenir compte des majuscules). Les mots de passe sont stockés **hachés**. L'instance peut fermer les inscriptions (`ALLOW_REGISTRATION=0`).
- Connexion : un seul message d'erreur (« Email ou mot de passe incorrect. ») ; après trop d'échecs, un blocage de quelques minutes ; déconnexion par un bouton (POST).
- **Sauvegarde et restauration** de la base : réservées à l'administrateur (premier compte créé, ou `CARNET_ADMIN_EMAIL`), car elles concernent tous les comptes. Détail : [SECURITE.md](SECURITE.md).
- Toutes les pages et routes d'API (sauf connexion/inscription/déconnexion) exigent d'être connecté.
- Chaque utilisateur ne voit que ses propres données ; une ressource d'un autre compte est traitée comme inexistante (404).
- Les exports CSV et PDF ne contiennent que les données de l'utilisateur connecté.

## Tableau récapitulatif des règles

| Sujet | Règle |
|---|---|
| Statuts | `log` → Carnet et Stats ; `projet` → Projets ; `ticklist` → Tick List |
| Mode de grimpe | obligatoire pour un log ou une répétition de type sur corde ; sans objet pour bloc, projet, envie |
| Stats voie / trad (voie) | seulement `grimpe = 'tete'` ; moulinette et mode manquant exclus |
| Stats grandes voies et blocs | toujours comptés |
| Exploration (lieux) | toutes les ascensions loguées, y compris moulinette |
| Une ascension refaite | compte une fois ; les répétitions ajoutent des mètres |
| Cotation d'une grande voie | cotation **haute** pour tout calcul |
| Cotation « entre deux » | niveau de base pour stats/filtres ; entre deux niveaux pour tri et max |
| Total d'essais d'un projet | somme des séances, recalculée automatiquement |
| Séance | date requise à la création, 1 à 999 essais, commentaire ≤ 5 000 caractères |
| Doublon | même secteur + type, nom, cotations, longueurs, départ, arrivée ; casse/accents/espaces ignorés |
| Suppression d'une ascension | supprime répétitions, longueurs, séances, choix, rééquipements |
| Suppression d'un lieu | supprime ses sous-niveaux et toutes leurs ascensions |
| Propositions (roche, grimpe…) | personnelles ; supprimer une proposition ne touche pas aux ascensions |
| Lien de topo | `http(s)` uniquement |
| Isolation | chaque requête filtre sur l'utilisateur ; ressource d'autrui = 404 |
