"""Point d'entrée : lance le serveur (`python run.py`).

Pour un hébergement, utiliser un serveur WSGI, par exemple : `gunicorn "src:create_app()"`
(avec CARNET_SECRET_KEY défini ; voir README, section Configuration).
"""
import os

from src import create_app
from src.config import IS_DEV

# Instance de l'application : c'est aussi l'objet que Flask (`flask run`) et un serveur WSGI vont chercher.
app = create_app()

# Ne se lance que si on exécute `python run.py` directement (pas à l'import par un serveur WSGI).
if __name__ == '__main__':
    port = int(os.environ.get('CARNET_PORT', '5000'))
    if IS_DEV:
        # Rechargement automatique, MAIS pas le débogueur interactif de Werkzeug (use_debugger=False) : il permet
        # d'exécuter du code Python depuis le navigateur, dangereux dès que le réseau est partagé.
        app.run(host='127.0.0.1', port=port, debug=True, use_debugger=False)
    else:
        print("Mode production (CARNET_ENV non défini) : écoute locale uniquement, sans debug.")
        print("Pour travailler sur ton PC en http, ajoute CARNET_ENV=development dans le fichier .env.")
        app.run(host='127.0.0.1', port=port, debug=False)
