# -*- coding: utf-8 -*-
"""
Lanceur de l'Architecture Web Sémantique (Classe Personne)
Exécute : Front-end + Module IA + Fuseki API + Back-end RDFLib + Protégé OWL
"""

import os
import sys
import webbrowser
import time
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Patch pyparsing / Python 3.14 AVANT tout import rdflib
import pyparsing_patch

from app import app

def open_browser(url):
    time.sleep(1.2)
    print(f"\n[Navigateur] Ouverture de l'interface : {url}")
    try:
        webbrowser.open(url)
    except Exception:
        pass

if __name__ == "__main__":
    PORT = 5000
    URL = f"http://127.0.0.1:{PORT}"

    print("=" * 65)
    print("  ARCHITECTURE PROJET WEB SÉMANTIQUE — CLASSE PERSONNE")
    print("=" * 65)
    print(f"  • Front-end : Interface utilisateur moderne (HTML/CSS/JS)")
    print(f"  • IA API    : Traduction Question Utilisateur -> Requête SPARQL")
    print(f"  • Fuseki    : Endpoint SPARQL compatible Apache Jena")
    print(f"  • Back-end  : Python + RDFLib (ontologie_personne.owl)")
    print(f"  • Modules   : Maladie (ontologie_maladie.owl) + Médicament (ontologie_medicament.owl)")
    print(f"  • URL       : {URL}")
    print("=" * 65)

    threading.Thread(target=open_browser, args=(URL,), daemon=True).start()

    app.run(host="127.0.0.1", port=PORT, debug=False)
