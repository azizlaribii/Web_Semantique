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
import time
import threading
import pyparsing_patch

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from rdflib_service import RDFLibService, MaladieService
from fuseki_api import FusekiAPIService
from ia_service import IAService
from ia_maladie_service import IAMaladieService
from medicament_service import MedicamentService
from ia_medicament_service import IAMedicamentService
from auth_service import AuthService
import ontology_crud_service

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANGULAR_DIST = os.path.join(BASE_DIR, "angular-frontend", "dist", "onto-sante-frontend", "browser")
STATIC_FALLBACK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "frontend")
FRONTEND_DIR = ANGULAR_DIST if os.path.exists(ANGULAR_DIST) else STATIC_FALLBACK

# Chemins des ontologies surveillées en temps réel (Hot-Reload)
OWL_FILES = {
    "personne":       os.path.join(BASE_DIR, "ontologie_personne.owl"),
    "medicale_ttl":   os.path.join(BASE_DIR, "ontologie_medicale (1).ttl"),
    "medicale_owl":   os.path.join(BASE_DIR, "ontologie_medicale.owl"),
    "maladie":        os.path.join(BASE_DIR, "ontologie_maladie.owl"),
    "medicament":     os.path.join(BASE_DIR, "ontologie_medicament.owl"),
}

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)

# Force UTF-8 sur toutes les réponses
@app.after_request
def set_utf8(response):
    if response.content_type and 'text' in response.content_type and 'charset' not in response.content_type:
        response.headers['Content-Type'] = response.content_type + '; charset=utf-8'
    return response


# ---------------------------------------------------------------------------
# Initialisation des services
# ---------------------------------------------------------------------------
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

print("[Architecture] Initialisation du module Authentification...")
auth_service = AuthService(rdflib_service)

# ---------------------------------------------------------------------------
# Hot-Reload : rechargement automatique quand un .owl est modifié
# ---------------------------------------------------------------------------
_reload_lock = threading.Lock()
_last_reload_info = {"ts": time.time(), "reason": "Démarrage initial"}

def _get_mtime(path: str) -> float:
    """Retourne le timestamp de dernière modification, 0 si fichier absent."""
    try:
        return os.stat(path).st_mtime
    except OSError:
        return 0.0

def reload_all_services(reason: str = "Manuel"):
    """
    Recharge toutes les ontologies OWL dans les services sans redémarrer le serveur.
    Thread-safe grâce au verrou _reload_lock.
    """
    global rdflib_service, fuseki_service, ia_service
    global maladie_service, ia_maladie_service
    global medicament_service, ia_medicament_service

    with _reload_lock:
        print(f"[HotReload] Rechargement déclenché ({reason})...")
        errors = []
        try:
            import importlib
            import ia_service as _ia_mod
            import rdflib_service as _rdf_mod
            importlib.reload(_rdf_mod)
            importlib.reload(_ia_mod)
            rdflib_service = _rdf_mod.RDFLibService()
            fuseki_service = FusekiAPIService(rdflib_service)
            ia_service = _ia_mod.IAService(rdflib_service)
            print("[HotReload] OK ontologies personne/medicale rechargees")
        except Exception as e:
            errors.append(f"personne: {e}")
            print(f"[HotReload] ERREUR personne : {e}")
        try:
            import importlib
            import ia_maladie_service as _ia_mal_mod
            importlib.reload(_ia_mal_mod)
            maladie_service._load()
            ia_maladie_service = _ia_mal_mod.IAMaladieService(maladie_service)
            print("[HotReload] OK ontologie_maladie.owl rechargee")
        except Exception as e:
            errors.append(f"maladie: {e}")
            print(f"[HotReload] ERREUR maladie : {e}")
        try:
            if hasattr(medicament_service, "lock"):
                with medicament_service.lock:
                    medicament_service._load()
            else:
                medicament_service._load()
            if hasattr(ia_medicament_service, "refresh"):
                ia_medicament_service.refresh()
            else:
                import importlib
                import ia_medicament_service as _ia_med_mod
                importlib.reload(_ia_med_mod)
                ia_medicament_service = _ia_med_mod.IAMedicamentService(medicament_service)
            print("[HotReload] OK ontologie_medicament.owl rechargee")
        except Exception as e:
            errors.append(f"medicament: {e}")
            print(f"[HotReload] ERREUR medicament : {e}")

        _last_reload_info["ts"] = time.time()
        _last_reload_info["reason"] = reason
        print("[HotReload] Rechargement terminé.")
        return errors


def _owl_watcher(interval: int = 3):
    """
    Vérifie toutes les `interval` secondes si un fichier OWL a été modifié.
    Si oui, déclenche un rechargement automatique de tous les services.
    """
    mtimes = {name: _get_mtime(path) for name, path in OWL_FILES.items()}
    while True:
        time.sleep(interval)
        changed = []
        for name, path in OWL_FILES.items():
            current = _get_mtime(path)
            if current != 0.0 and current != mtimes[name]:
                changed.append(name)
                mtimes[name] = current
        if changed:
            reason = f"Fichier(s) modifié(s) : {', '.join(changed)}"
            print(f"[HotReload] Changement detecte -> {reason}")
            reload_all_services(reason)

# Démarrage du watcher (thread daemon = s'arrête avec le serveur)
_watcher_thread = threading.Thread(target=_owl_watcher, args=(3,), daemon=True)
_watcher_thread.start()
print("[HotReload] Watcher OWL actif - rechargement auto toutes les 3 secondes")


# ----------------------------------------------------------------------
# Routes Frontend
# ----------------------------------------------------------------------
@app.route("/")
def serve_frontend():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/login")
@app.route("/register")
@app.route("/dashboard")
def serve_auth_pages():
    """Sert la page d'authentification et de dashboard (SPA — index.html)."""
    return send_from_directory(FRONTEND_DIR, "index.html")


# ----------------------------------------------------------------------
# Routes Authentification
# ----------------------------------------------------------------------
@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    """Inscrit un nouvel utilisateur et l'ajoute à l'ontologie OWL."""
    body = request.get_json(force=True, silent=True) or {}
    try:
        result = auth_service.register(body)
        # Recharger les services après ajout
        reload_all_services("Inscription d'un nouvel utilisateur")
        auth_service.reload()
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Erreur serveur : {str(e)}"}), 500


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    """Authentifie un utilisateur et retourne un token de session."""
    body = request.get_json(force=True, silent=True) or {}
    email = (body.get("email") or body.get("identifier") or body.get("username") or "").strip()
    password = body.get("motDePasse", "").strip()
    try:
        result = auth_service.login(email, password)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        return jsonify({"error": f"Erreur serveur : {str(e)}"}), 500


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    """Invalide le token de session courant."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    auth_service.logout(token)
    return jsonify({"success": True, "message": "Déconnexion réussie."})


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    """Retourne les infos de l'utilisateur connecté via son token."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    user = auth_service.verify_token(token)
    if not user:
        return jsonify({"error": "Non authentifié."}), 401
    return jsonify({"success": True, "user": user})


@app.route("/api/auth/verify", methods=["POST"])
def auth_verify():
    """Vérifie si un token est valide (utilisé par le front-end au démarrage)."""
    body = request.get_json(force=True, silent=True) or {}
    token = body.get("token", "") or request.headers.get("Authorization", "").replace("Bearer ", "")
    user = auth_service.verify_token(token)
    if not user:
        return jsonify({"valid": False}), 401
    return jsonify({"valid": True, "user": user})

def _clean_val(val: str) -> str:
    """Nettoie les URIs ontologiques pour afficher des labels propres."""
    if not isinstance(val, str):
        return str(val) if val is not None else ""
    for ns in [
        "http://example.org/ontologie-medicale#",
        "http://example.org/ontologie-maladie#",
        "http://example.org/ontologie-medicament#",
        "http://www.w3.org/2002/07/owl#",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "http://www.w3.org/2000/01/rdf-schema#",
        "http://www.w3.org/2001/XMLSchema#",
    ]:
        if val.startswith(ns):
            val = val[len(ns):]
    if "://" in val and "#" in val:
        val = val.split("#")[-1]
    elif "://" in val and "/" in val:
        val = val.split("/")[-1]
    # Supprimer les deux points devant le nom d'une classe ou entité
    val = val.lstrip(":")
    return val.strip()

import unicodedata

def _normalize_txt(text: str) -> str:
    """Normalise un texte en retirant accents et espaces superflus."""
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', str(text))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

def _dedup_dicts(items: list) -> list:
    """Supprime les doublons dans une liste de dictionnaires tout en préservant l'ordre."""
    seen = set()
    deduped = []
    for item in items:
        # Clé tuple basée sur les paires triées (clé, valeur normalisée sans accents)
        key = tuple(sorted((str(k), _normalize_txt(v)) for k, v in item.items() if v))
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped

def _dedup_list(items: list) -> list:
    """Supprime les doublons dans une liste de chaînes tout en préservant l'ordre."""
    seen = set()
    deduped = []
    for x in items:
        cleaned = str(x).strip()
        norm_key = _normalize_txt(cleaned)
        if cleaned and norm_key not in seen:
            seen.add(norm_key)
            deduped.append(cleaned)
    return deduped


# ----------------------------------------------------------------------
# 1. Route IA : Question Utilisateur -> Requête SPARQL -> Données
# ----------------------------------------------------------------------
@app.route("/api/ia/ask", methods=["POST"])
def ia_ask():
    """Assistant IA Universel : route intelligemment entre Personnes, Maladies et Médicaments."""
    data = request.get_json(force=True, silent=True) or {}
    question = data.get("question", "").strip()
    target_module = (data.get("module") or "auto").strip().lower()
    if not question:
        return jsonify({"error": "Veuillez poser une question."}), 400

    try:
        q_norm = _normalize_txt(question)
        med_keywords = [
            "medicament", "antibiotique", "molecule", "dosage",
            "clamoxyl", "paracetamol", "doliprane", "posologie", "atc",
            "forme", "anti-inflammatoire", "antalgique", "sirop", "comprime"
        ]
        mal_keywords = [
            "maladie", "symptome", "diabete", "asthme", "hypertension",
            "covid", "grippe", "pathologie", "infection", "bronchite", "cancer", "cardiaque",
            "chronique", "aigue", "cause", "gravite", "transmission", "angine", "pathogene",
            "agent", "virus", "bacterie", "ulcere", "gastrite", "arthrite", "anemie"
        ]

        # 1. Routing vers Médicaments
        if target_module == "medicament" or (target_module == "auto" and any(k in q_norm for k in med_keywords)):
            res = ia_medicament_service.answer_question(question)
            bindings = res.get("data", {}).get("results", {}).get("bindings", [])
            raw_donnees = []
            for b in bindings:
                item = {k: _clean_val(v.get("value", "")) for k, v in b.items()}
                raw_donnees.append(item)

            # Déduplication des lignes
            donnees = _dedup_dicts(raw_donnees)

            # Réponse dynamique sans répétitions
            noms_med = [d.get("medicament") or d.get("nom") or d.get("antibiotique") or d.get("antalgique") or "" for d in donnees if d.get("medicament") or d.get("nom")]
            unique_noms = _dedup_list(noms_med)

            if not donnees:
                reponse_txt = f"Aucun médicament trouvé dans l'ontologie pour : « {question} »."
            elif unique_noms:
                reponse_txt = f"{len(donnees)} résultat(s) — {res.get('intention', '')} : {', '.join(unique_noms[:6])}."
            else:
                reponse_txt = f"{len(donnees)} résultat(s) extrait(s) de l'ontologie des médicaments."

            return jsonify({
                "module": "Médicaments",
                "question": question,
                "intention": res.get("intention", ""),
                "reponse": reponse_txt,
                "sparql": res.get("sparql", ""),
                "donnees": donnees,
                "count": len(donnees),
                "explication": res.get("explication", ""),
                "nlp": res.get("nlp")
            })

        # 2. Routing vers Maladies
        elif target_module == "maladie" or (target_module == "auto" and any(k in q_norm for k in mal_keywords)):
            res = ia_maladie_service.answer_question(question)
            bindings = res.get("data", {}).get("results", {}).get("bindings", [])
            raw_donnees = []
            for b in bindings:
                item = {k: _clean_val(v.get("value", "")) for k, v in b.items()}
                raw_donnees.append(item)

            # Déduplication des lignes
            donnees = _dedup_dicts(raw_donnees)

            # Détection ciblée de l'attribut principal à lister pour une réponse claire sans répétition
            items_to_display = []
            if any(k in q_norm for k in ["symptome", "signe"]):
                items_to_display = [d.get("symptome") or d.get("symptomeGeneral") or d.get("symptomeCommun") or "" for d in donnees]
            elif any(k in q_norm for k in ["medicament", "traite", "traitement"]):
                items_to_display = [d.get("medicament") or d.get("nomMedicament") or "" for d in donnees]
            elif any(k in q_norm for k in ["medecin", "docteur", "soigne", "suivi", "charge"]):
                items_to_display = [d.get("medecin") or "" for d in donnees]
            elif any(k in q_norm for k in ["patient"]):
                items_to_display = [d.get("patient") or d.get("nom") or "" for d in donnees]
            elif any(k in q_norm for k in ["pathogene", "agent", "virus", "bacterie"]):
                items_to_display = [d.get("agentPathogene") or d.get("nom") or "" for d in donnees]
            elif any(k in q_norm for k in ["gravite"]):
                items_to_display = [f"Niveau {d.get('gravite')}" if d.get('gravite') else "" for d in donnees]

            if not any(items_to_display):
                items_to_display = [d.get("nom") or d.get("maladie") or d.get("maladieInfectieuse") or d.get("symptome") or "" for d in donnees]

            unique_items = _dedup_list(items_to_display)

            if not donnees:
                reponse_txt = f"Aucune maladie trouvée dans l'ontologie pour : « {question} »."
            elif unique_items:
                reponse_txt = f"{len(donnees)} résultat(s) — {res.get('intention', '')} : {', '.join(unique_items[:6])}."
            else:
                reponse_txt = f"{len(donnees)} résultat(s) extrait(s) de l'ontologie des maladies."

            return jsonify({
                "module": "Maladies",
                "question": question,
                "intention": res.get("intention", ""),
                "reponse": reponse_txt,
                "sparql": res.get("sparql", ""),
                "donnees": donnees,
                "count": len(donnees)
            })

        # 3. Routing vers Personnes (défaut)
        else:
            res = ia_service.answer_question(question)
            bindings = res.get("data", {}).get("results", {}).get("bindings", [])
            result_type = res.get("result_type", "personnes")

            # Index des individus pour enrichir automatiquement avec email, cin, specialite
            all_personnes = {p["id"]: p for p in rdflib_service.get_all_personnes()}
            for p in list(all_personnes.values()):
                all_personnes[p["uri"]] = p

            raw_donnees = []
            for b in bindings:
                item = {k: _clean_val(v.get("value", "")) for k, v in b.items()}

                # Enrichir seulement si ce n'est pas une requête de métadonnées
                if result_type not in ["subclasses", "classes", "properties"]:
                    ind_match = None
                    for k, v in b.items():
                        raw_v = v.get("value", "")
                        clean_v = item[k]
                        if raw_v in all_personnes:
                            ind_match = all_personnes[raw_v]
                            break
                        if clean_v in all_personnes:
                            ind_match = all_personnes[clean_v]
                            break

                    if ind_match:
                        cur_nom = (item.get("nom") or "").strip()
                        ind_nom = (ind_match.get("nom") or "").strip()
                        if cur_nom and not cur_nom.startswith("http"):
                            item["nom"] = cur_nom
                        else:
                            item["nom"] = ind_nom or cur_nom or ind_match.get("id")
                        item["specialite"] = ind_match.get("specialite") or item.get("specialite", "")
                        item["email"] = ind_match.get("email") or item.get("email", "")
                        item["cin"] = ind_match.get("cin") or item.get("cin", "")
                        item["telephone"] = ind_match.get("telephone") or item.get("telephone", "")
                        item["role"] = (ind_match.get("types") or ["Personne"])[0]
                    else:
                        if "type" in item:
                            item["role"] = _clean_val(item["type"])
                        if "role" in item:
                            item["role"] = _clean_val(item["role"])
                raw_donnees.append(item)

            donnees = _dedup_dicts(raw_donnees)

            return jsonify({
                "module": "Personnes",
                "question": question,
                "intention": res.get("intention", ""),
                "reponse": res.get("answer_summary") or res.get("explanation", ""),
                "sparql": res.get("sparql_query", ""),
                "donnees": donnees,
                "count": len(donnees),
                "result_type": result_type
            })
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

@app.route("/api/personnes/add", methods=["POST"])
def add_personne_api():
    """Ajoute un individu dans l'ontologie (bidirectionnel) et recharge les services."""
    body = request.get_json(force=True, silent=True) or {}
    try:
        res = rdflib_service.add_personne(body)
        reload_all_services("Ajout d'un individu via l'interface")
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ----------------------------------------------------------------------
# Routes CRUD interactif Ontologie (Action Modifier, Supprimer, + Ajouter)
# ----------------------------------------------------------------------
@app.route("/api/ontology/dynamic-entities", methods=["GET"])
def get_dynamic_entities_api():
    """Retourne la liste dynamique des entités de l'ontologie pour les formulaires."""
    try:
        entities = ontology_crud_service.get_dynamic_entities(rdflib_service.graph)
        return jsonify(entities)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/ontology/row/delete", methods=["POST"])
def delete_ontology_row_api():
    """Supprime une relation RDF sans supprimer le patient ou la maladie."""
    body = request.get_json(force=True, silent=True) or {}
    item = body.get("item", {})
    try:
        res = ontology_crud_service.delete_relation(item, reload_callback=reload_all_services)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/ontology/row/update", methods=["POST"])
def update_ontology_row_api():
    """Modifie une relation RDF dans l'ontologie."""
    body = request.get_json(force=True, silent=True) or {}
    old_item = body.get("old_item", {})
    new_item = body.get("new_item", {})
    try:
        res = ontology_crud_service.update_relation(old_item, new_item, reload_callback=reload_all_services)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/ontology/row/add", methods=["POST"])
def add_ontology_contextual_api():
    """Ajoute une relation ou un individu selon le contexte de la question."""
    body = request.get_json(force=True, silent=True) or {}
    data_type = body.get("type", "")
    data = body.get("data", {})
    try:
        res = ontology_crud_service.add_contextual_item(data_type, data, reload_callback=reload_all_services)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

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

@app.route("/api/ontology/maladie-structure", methods=["GET"])
def get_ontology_maladie_structure():
    try:
        data = maladie_service.get_maladie_ontology_structure()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ia-maladie/ask", methods=["POST"])
def ia_maladie_ask():
    """Traduit une question NL en SPARQL Maladie et interroge ontologie_medicale (1).ttl."""
    body = request.get_json(force=True, silent=True) or {}
    question = body.get("question", "").strip()
    if not question:
        return jsonify({"error": "Question vide"}), 400
    try:
        # Interrogation directe et dynamique de l'ontologie Protégé réelle
        res = ia_service.answer_question(question)
        return jsonify({
            "intention": res.get("intention"),
            "explication": res.get("explanation"),
            "sparql": res.get("sparql_query"),
            "data": res.get("data")
        })
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

# --- CRUD Médicament (SPARQL Update) ---------------------------------
def _crud(action):
    """Exécute une opération CRUD, recharge le vocabulaire NLP et formate les erreurs."""
    try:
        result = action()
        ia_medicament_service.refresh()   # le nouveau nom est reconnu tout de suite par l'IA
        return jsonify(result)
    except MedicamentService.ErreurValidation as e:
        return jsonify({"error": str(e)}), 400
    except KeyError as e:
        return jsonify({"error": f"Médicament introuvable : {e.args[0]}"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/medicament-options", methods=["GET"])
def get_medicament_options():
    return jsonify(medicament_service.get_options())

@app.route("/api/medicaments", methods=["POST"])
def create_medicament():
    body = request.get_json(force=True, silent=True) or {}
    return _crud(lambda: medicament_service.create_medicament(body))

@app.route("/api/medicaments/<mid>", methods=["PUT"])
def update_medicament(mid):
    body = request.get_json(force=True, silent=True) or {}
    return _crud(lambda: medicament_service.update_medicament(mid, body))

@app.route("/api/medicaments/<mid>", methods=["DELETE"])
def delete_medicament(mid):
    return _crud(lambda: medicament_service.delete_medicament(mid))

@app.route("/api/medicaments/reset", methods=["POST"])
def reset_medicaments():
    return _crud(lambda: (medicament_service.reset(), {"ok": True, "operation": "RESET"})[1])

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
        "frontend": "Actif (Angular 18 SPA)",
        "ia_api": "Actif (Traducteur NL -> SPARQL)",
        "fuseki_api": "Actif" + (" (Connecté à Fuseki distant)" if fuseki_alive else " (Mode Émulation RDFLib local)"),
        "backend": f"Actif (Python {sys.version.split()[0]} + RDFLib {rdflib_service.graph.__module__})",
        "protege_owl": f"Chargé ({len(rdflib_service.graph)} triplets depuis ontologie_personne.owl)",
        "medicament_owl": (f"Chargé ({len(medicament_service.graph)} triplets depuis ontologie_medicament.owl)"
                           if medicament_service.loaded else "Non chargé (lancez medicament_owlready2.py)"),
        "target_class": "Personne (Médecins, Patients, Stagiaires, Stuff Médical)",
        "hot_reload": "Actif (watcher toutes les 3 secondes)",
        "dernier_rechargement": {
            "raison": _last_reload_info.get("reason", ""),
            "timestamp": _last_reload_info.get("ts", 0),
            "erreurs": _last_reload_info.get("errors", [])
        }
    })

# ----------------------------------------------------------------------
# Route Rechargement Manuel des Ontologies
# ----------------------------------------------------------------------
@app.route("/api/reload", methods=["POST"])
def manual_reload():
    """
    Recharge manuellement toutes les ontologies OWL depuis le disque.
    Utile après une modification dans Protégé si le watcher n'a pas encore réagi.
    """
    try:
        errors = reload_all_services("Rechargement manuel via /api/reload")
        triplets_personne = len(rdflib_service.graph)
        triplets_medicament = len(medicament_service.graph) if medicament_service.loaded else 0
        return jsonify({
            "success": True,
            "message": "Ontologies rechargées avec succès.",
            "triplets": {
                "personne": triplets_personne,
                "medicament": triplets_medicament,
            },
            "erreurs": errors,
            "timestamp": _last_reload_info["ts"]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ----------------------------------------------------------------------
# Route Statut des Fichiers OWL
# ----------------------------------------------------------------------
@app.route("/api/ontologie/status", methods=["GET"])
def ontologie_status():
    """Retourne la date de modification de chaque fichier OWL surveillé."""
    import datetime
    status = {}
    for name, path in OWL_FILES.items():
        mtime = _get_mtime(path)
        if mtime:
            dt = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        else:
            dt = "Fichier introuvable"
        status[name] = {
            "path": os.path.basename(path),
            "derniere_modification": dt,
            "timestamp": mtime,
            "existe": os.path.exists(path)
        }
    return jsonify({
        "ontologies": status,
        "dernier_rechargement": {
            "raison": _last_reload_info.get("reason", ""),
            "timestamp": _last_reload_info.get("ts", 0),
        }
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n==================================================")
    print(f" Serveur Web Sémantique lancé sur http://127.0.0.1:{port}")
    print(f" Architecture : Front-end -> IA -> Fuseki -> RDFLib -> OWL")
    print(f" Classe ciblée: Personne")
    print(f" Hot-Reload OWL : Actif (watcher 3s)")
    print(f"==================================================\n")
    app.run(host="0.0.0.0", port=port, debug=False)
