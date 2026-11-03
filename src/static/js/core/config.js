// Configuration de page lue par les autres scripts.
//
// Les templates projets.html et ticklist.html définissent une variable globale `PAGE_STATUT` (« projet » ou
// « ticklist ») avant de charger ce fichier ; sur les autres pages elle n'existe pas.

// Statut d'ascension à créer par défaut depuis la page courante (null = log, c'est-à-dire une ascension réalisée).
const PAGE_STATUT_DEFAULT = typeof PAGE_STATUT !== 'undefined' ? PAGE_STATUT : null;
