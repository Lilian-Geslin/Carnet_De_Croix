// Point d'entrée du JavaScript : une fois la page chargée, démarre chaque fonctionnalité.
//
// Chaque init* est définie dans un fichier de features/ ou pages/ (chargés avant celui-ci, cf. base.html). Elles
// vérifient elles-mêmes que les éléments dont elles ont besoin existent sur la page courante : on peut donc
// toutes les appeler partout.

document.addEventListener('DOMContentLoaded', () => {
    initGeoTree();
    initAscensionModal();
    initGeoEdit();
    initTopos();
    initRepetitions();
    initQuickModals();
    initSeances();
    initPageProjets();
    initInfosModal();
    initPageTicklist();
    initRestoreDb();
});
