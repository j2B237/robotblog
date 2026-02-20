# WSGI configuration file pour PythonAnywhere
# Remplacez 'votre_username' par votre nom d'utilisateur PythonAnywhere

import sys
import os

# Chemin vers votre projet
project_home = '/home/votre_username/robotblog'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Variables d'environnement (optionnel)
os.environ['FLASK_ENV'] = 'production'

from app import app as application
