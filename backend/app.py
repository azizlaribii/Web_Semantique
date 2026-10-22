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

from rdflib_service import RDFLibService, MaladieService
from fuseki_api import FusekiAPIService
from ia_service import IAService
from ia_maladie_service import IAMaladieService
from medicament_service import MedicamentService
from ia_medicament_service import IAMedicamentService

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)

# Force UTF-8 sur toutes les réponses
@app.after_request
def set_utf8(response):
    if response.content_type and 'text' in response.content_type and 'charset' not in response.content_type:
        response.headers['Content-Type'] = response.content_type + '; charset=utf-8'
    return response


# Initialisation des services
print("[Architecture] Initialisation du Back-end Python + RDFLib...")
rdflib_service = RDFLibService()

print("[Architecture] Initialisation de l'API Fuseki...")
fuseki_service = FusekiAPIService(rdflib_service)

print("[Architecture] Initialisation du module IA...")
ia_service = IAService(rdflib_service)

print("[Architecture] Initialisation du module Maladie...")
maladie_service = MaladieService()

print("[Architecture] Initialisation du module IA Maladie...")
ia_maladie_service = IAMaladieService(maladie_service)

print("[Architecture] Initialisation du module Médicament...")
medicament_service = MedicamentService()

print("[Architecture] Initialisation du module IA Médicament...")
ia_medicament_service = IAMedicamentService(medicament_service)

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

@app.route("/api/maladies", methods=["GET"])
def get_all_maladies():
    try:
        data = maladie_service.get_all_maladies()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/graph-maladie", methods=["GET"])
def get_graph_maladie():
    try:
        data = maladie_service.get_graph_maladie()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/ia-maladie/ask", methods=["POST"])
def ia_maladie_ask():
    """Traduit une question NL en SPARQL Maladie et retourne les données."""
    body = request.get_json(force=True, silent=True) or {}
    question = body.get("question", "").strip()
    if not question:
        return jsonify({"error": "Question vide"}), 400
    try:
        result = ia_maladie_service.answer_question(question)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------------------------------------------------------------
# Routes Module Médicament (ontologie_medicament.owl)
# ----------------------------------------------------------------------
@app.route("/api/medicaments", methods=["GET"])
def get_all_medicaments():
    try:
        return jsonify(medicament_service.get_all_medicaments())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/graph-medicament", methods=["GET"])
def get_graph_medicament():
    try:
        return jsonify(medicament_service.get_graph_medicament())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/summary-medicament", methods=["GET"])
def get_summary_medicament():
    try:
        return jsonify(medicament_service.get_summary())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/ia-medicament/ask", methods=["POST"])
def ia_medicament_ask():
    """Traduit une question NL en SPARQL Médicament et retourne les données."""
    body = request.get_json(force=True, silent=True) or {}
    question = body.get("question", "").strip()
    if not question:
        return jsonify({"error": "Question vide"}), 400
    try:
        return jsonify(ia_medicament_service.answer_question(question))
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
        "medicament_owl": (f"Chargé ({len(medicament_service.graph)} triplets depuis ontologie_medicament.owl)"
                           if medicament_service.loaded else "Non chargé (lancez medicament_owlready2.py)"),
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
