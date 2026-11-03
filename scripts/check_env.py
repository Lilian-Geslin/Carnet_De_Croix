"""
Vérifie le fichier .env, sans jamais afficher de valeur secrète.

    python scripts/check_env.py

À lancer à la racine du projet (environnement virtuel actif), en local comme sur le serveur.
Affiche OK / ATTENTION / ERREUR pour chaque réglage important et dit quoi faire.
"""
import os
import stat
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, '.env')

# Réglages reconnus : tout autre nom est signalé (faute de frappe probable, il serait ignoré)
KNOWN = {
    'CARNET_SECRET_KEY', 'CARNET_ENV', 'CARNET_DATABASE', 'CARNET_ADMIN_EMAIL', 'CARNET_MAX_UPLOAD_MB',
    'ALLOW_REGISTRATION', 'TRUST_PROXY', 'FORCE_HTTPS',
}

results = []   # (niveau, message)


def add(level, message):
    results.append((level, message))


def main():
    if not os.path.exists(ENV_PATH):
        print(f"ERREUR : aucun fichier .env dans {BASE_DIR}")
        print("Copie .env.example en .env (même dossier que run.py) puis remplis-le (voir README, section Configuration).")
        sys.exit(1)

    try:
        from dotenv import dotenv_values
    except ImportError:
        print("ERREUR : python-dotenv n'est pas installé (l'environnement virtuel est-il activé ?).")
        sys.exit(1)
    values = dotenv_values(ENV_PATH)

    # --- syntaxe : lignes sans « = » ---
    with open(ENV_PATH, encoding='utf-8', errors='replace') as f:
        for number, line in enumerate(f, 1):
            text = line.strip()
            if text and not text.startswith('#') and '=' not in text:
                add('ATTENTION', f"ligne {number} : pas de « = » (ligne ignorée ; deux réglages collés sur une même ligne ?)")

    # --- clé secrète ---
    key = values.get('CARNET_SECRET_KEY') or ''
    if len(key) < 16:
        add('ERREUR', "CARNET_SECRET_KEY absente ou trop courte (l'application refuse de démarrer sans elle).")
    elif len(key) < 32 or any(w in key.lower() for w in ('changeme', 'secret', 'motdepasse', 'password', 'exemple')):
        add('ATTENTION', f"CARNET_SECRET_KEY faible ({len(key)} caractères ou valeur d'exemple). Génère-en une : "
                         "python -c \"import secrets; print(secrets.token_urlsafe(48))\" puis remplace-la dans .env "
                         "(tout le monde sera déconnecté, c'est normal).")
    else:
        add('OK', f"CARNET_SECRET_KEY présente ({len(key)} caractères).")

    # --- mode production ---
    if (values.get('CARNET_ENV') or '').strip().lower() == 'development':
        add('INFO', "CARNET_ENV=development : correct sur ton PC, mais à SUPPRIMER sur un serveur "
                    "(cookie non sécurisé, HTTPS non forcé).")
    else:
        add('OK', "Mode production (CARNET_ENV absent ou différent de « development »).")

    # --- proxy / HTTPS ---
    if values.get('TRUST_PROXY') == '1':
        add('OK', "TRUST_PROXY=1 (la vraie adresse IP des visiteurs est utilisée).")
    else:
        add('INFO', "TRUST_PROXY absent : correct en local. Sur un hébergement derrière un proxy, ajoute TRUST_PROXY=1, "
                    "sinon la limitation des essais se fera sur l'adresse du proxy.")
    if values.get('FORCE_HTTPS') == '0':
        add('ATTENTION', "FORCE_HTTPS=0 : la redirection automatique vers HTTPS est désactivée.")

    # --- comptes ---
    if (values.get('ALLOW_REGISTRATION') or '').strip().lower() in ('0', 'false', 'non', 'no', 'off'):
        add('OK', "Inscriptions fermées (ALLOW_REGISTRATION=0).")
    else:
        add('INFO', "Inscriptions ouvertes. Pour une instance personnelle, crée ton compte puis mets ALLOW_REGISTRATION=0.")

    # --- noms inconnus (fautes de frappe) ---
    for name in sorted(k for k in values if k not in KNOWN):
        add('ATTENTION', f"nom de réglage inconnu : « {name} » (faute de frappe ? il sera ignoré).")

    # --- droits du fichier (sous Linux / macOS ; Windows ne gère pas ces droits) ---
    if os.name == 'posix':
        mode = stat.S_IMODE(os.stat(ENV_PATH).st_mode)
        if mode & 0o077:
            add('ATTENTION', f"droits du fichier .env : {oct(mode)[2:]} (lisible par d'autres). Corrige avec : chmod 600 .env")
        else:
            add('OK', "Droits du fichier .env corrects (privé).")

    # --- .env et base suivis par Git ? ---
    for name in ('.env', 'carnet.db', '.secret_key'):
        try:
            tracked = subprocess.run(['git', 'ls-files', '--error-unmatch', name], cwd=BASE_DIR,
                                     capture_output=True, text=True).returncode == 0
        except OSError:
            break
        if tracked:
            add('ERREUR', f"{name} est suivi par Git (son contenu est dans le dépôt). Retire-le : git rm --cached {name}, "
                          "puis change CARNET_SECRET_KEY (et considère les mots de passe comme exposés).")
    if not any(level == 'ERREUR' and 'suivi par Git' in msg for level, msg in results):
        add('OK', "Ni .env, ni la base, ni .secret_key ne sont suivis par Git.")

    order = {'ERREUR': 0, 'ATTENTION': 1, 'INFO': 2, 'OK': 3}
    for level, message in sorted(results, key=lambda r: order[r[0]]):
        print(f"[{level:9}] {message}")
    errors = sum(1 for level, _ in results if level == 'ERREUR')
    warnings = sum(1 for level, _ in results if level == 'ATTENTION')
    print(f"\n{errors} erreur(s), {warnings} attention(s).")
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
