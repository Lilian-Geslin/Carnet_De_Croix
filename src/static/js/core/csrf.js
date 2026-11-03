// ─── SÉCURITÉ : jeton CSRF ─────────────────────────────────────────────────────────────────────────
// Le serveur refuse toute requête qui modifie des données (POST, PUT, PATCH, DELETE) sans le jeton de la session
// (voir src/security.py). Il est lu dans <meta name="csrf-token"> et ajouté ICI, une seule fois, à tous les fetch()
// qui modifient quelque chose : aucun autre fichier JS n'a besoin d'y penser.
// Chargé en premier (voir base.html).

window.csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || '';

(function () {
    const nativeFetch = window.fetch.bind(window);
    const SAFE_METHODS = ['GET', 'HEAD', 'OPTIONS'];
    window.fetch = (input, init = {}) => {
        const method = (init.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
        if (!SAFE_METHODS.includes(method)) {
            const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined));
            if (!headers.has('X-CSRF-Token')) headers.set('X-CSRF-Token', window.csrfToken());
            init = { ...init, headers };
        }
        return nativeFetch(input, init);
    };
})();
