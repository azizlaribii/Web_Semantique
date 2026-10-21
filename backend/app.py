# -*- coding: utf-8 -*-
"""
Serveur Back-end Flask principal
Intègre les 4 composants de l'architecture du projet :
1. Front-end (fichiers statiques)
2. IA API (Question Utilisateur -> Requête SPARQL)
3. Fuseki API (SPARQL Endpoint JSON)
4. Back-end Python + RDFLib (Ontologie Personne OWL issue de Protégé)
"""

import os
import sys
import pyparsing_patch

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from rdflib_service import RDFLibService
from fuseki_api import FusekiAPIService
from ia_service import IAService

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)

# Initialisation des services
print("[Architecture] Initialisation du Back-end Python + RDFLib...")
rdflib_service = RDFLibService()

print("[Architecture] Initialisation de l'API Fuseki...")
fuseki_service = FusekiAPIService(rdflib_service)

print("[Architecture] Initialisation du module IA...")
ia_service = IAService(rdflib_service)

# ----------------------------------------------------------------------
# Routes Frontend
# ----------------------------------------------------------------------
@app.route("/")
def serve_frontend():
    return send_from_directory(FRONTEND_DIR, "index.html")

# ----------------------------------------------------------------------
# 1. Route IA : Question Utilisateur -> Requête SPARQL -> Données
# ----------------------------------------------------------------------
@app.route("/api/ia/ask", methods=["POST"])
def ia_ask():
    data = request.get_json() or {}
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "Veuillez poser une question."}), 400

    try:
        response = ia_service.answer_question(question)
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------------------------------------------------------------
# 2. Route Fuseki API : SPARQL Endpoint direct
# ----------------------------------------------------------------------
@app.route("/api/sparql", methods=["GET", "POST"])
@app.route("/api/fuseki/query", methods=["GET", "POST"])
def sparql_endpoint():
    if request.method == "POST":
        if request.is_json:
            query = request.json.get("query", "")
        else:
            query = request.form.get("query", "") or request.data.decode("utf-8")
    else:
        query = request.args.get("query", "")

    if not query:
        return jsonify({"error": "Aucune requête SPARQL spécifiée."}), 400

    try:
        results = fuseki_service.query(query)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ----------------------------------------------------------------------
# 3. Routes Données Métier de la Classe Personne
# ----------------------------------------------------------------------
@app.route("/api/personnes", methods=["GET"])
def get_all_personnes():
    try:
        data = rdflib_service.get_all_personnes()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/graph", methods=["GET"])
def get_graph():
    try:
        data = rdflib_service.get_relations_graph()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/summary", methods=["GET"])
def get_summary():
    try:
        data = rdflib_service.get_summary()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/status", methods=["GET"])
def get_status():
    """Retourne l'état de chaque brique de l'architecture."""
    fuseki_alive = fuseki_service.is_fuseki_alive()
    return jsonify({
        "frontend": "Actif (HTML/CSS/JS)",
        "ia_api": "Actif (Traducteur NL -> SPARQL)",
        "fuseki_api": "Actif" + (" (Connecté à Fuseki distant)" if fuseki_alive else " (Mode Émulation RDFLib local)"),
        "backend": f"Actif (Python {sys.version.split()[0]} + RDFLib {rdflib_service.graph.__module__})",
        "protege_owl": f"Chargé ({len(rdflib_service.graph)} triplets depuis ontologie_personne.owl)",
        "target_class": "Personne (Médecins, Patients, Stagiaires, Stuff Médical)"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n==================================================")
    print(f" Serveur Web Sémantique lancé sur http://127.0.0.1:{port}")
    print(f" Architecture : Front-end -> IA -> Fuseki -> RDFLib -> OWL")
    print(f" Classe ciblée: Personne")
    print(f"==================================================\n")
    app.run(host="0.0.0.0", port=port, debug=True)
