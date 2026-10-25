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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANGULAR_DIST = os.path.join(BASE_DIR, "angular-frontend", "dist", "onto-sante-frontend", "browser")
FRONTEND_DIR = ANGULAR_DIST

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
            maladie_service._load()
            ia_maladie_service = IAMaladieService(maladie_service)
            print("[HotReload] OK ontologie_maladie.owl rechargee")
        except Exception as e:
            errors.append(f"maladie: {e}")
            print(f"[HotReload] ERREUR maladie : {e}")
        try:
            medicament_service._load()
            ia_medicament_service = IAMedicamentService(medicament_service)
            print("[HotReload] OK ontologie_medicament.owl rechargee")
        except Exception as e:
            errors.append(f"medicament: {e}")
            print(f"[HotReload] ERREUR medicament : {e}")

        _last_reload_info["ts"] = time.time()
        _last_reload_info["reason"] = reason
        _last_reload_info["errors"] = errors
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
        ql = question.lower()
        med_keywords = [
            "medicament", "médicament", "antibiotique", "molecule", "molécule", "dosage",
            "clamoxyl", "paracetamol", "paracétamol", "doliprane", "posologie", "atc",
            "forme", "anti-inflammatoire", "antalgique", "sirop", "comprime", "comprimé"
        ]
        mal_keywords = [
            "maladie", "symptome", "symptôme", "diabete", "diabète", "asthme", "hypertension",
            "covid", "grippe", "pathologie", "infection", "bronchite", "cancer", "cardiaque",
            "chronique", "aigue", "aiguë", "cause", "gravite", "gravité", "transmission"
        ]

        # 1. Routing vers Médicaments
        if target_module == "medicament" or (target_module == "auto" and any(k in ql for k in med_keywords)):
            res = ia_medicament_service.answer_question(question)
            bindings = res.get("data", {}).get("results", {}).get("bindings", [])
            donnees = []
            for b in bindings:
                item = {k: _clean_val(v.get("value", "")) for k, v in b.items()}
                donnees.append(item)

            # Réponse dynamique basée sur les données réelles
            noms_med = [d.get("medicament") or d.get("nom") or d.get("antibiotique") or d.get("antalgique") or "" for d in donnees if d.get("medicament") or d.get("nom")]
            noms_med = [n for n in noms_med if n]
            if not donnees:
                reponse_txt = f"Aucun médicament trouvé dans l'ontologie pour : « {question} »."
            elif noms_med:
                reponse_txt = f"{len(donnees)} résultat(s) — {res.get('intention', '')} : {', '.join(noms_med[:6])}."
            else:
                reponse_txt = f"{len(donnees)} résultat(s) extrait(s) de l'ontologie des médicaments."

            return jsonify({
                "module": "Médicaments",
                "question": question,
                "intention": res.get("intention", ""),
                "reponse": reponse_txt,
                "sparql": res.get("sparql", ""),
                "donnees": donnees,
                "count": len(donnees)
            })

        # 2. Routing vers Maladies
        elif target_module == "maladie" or (target_module == "auto" and any(k in ql for k in mal_keywords)):
            res = ia_maladie_service.answer_question(question)
            bindings = res.get("data", {}).get("results", {}).get("bindings", [])
            donnees = []
            for b in bindings:
                item = {k: _clean_val(v.get("value", "")) for k, v in b.items()}
                donnees.append(item)

            # Réponse dynamique basée sur les données réelles
            noms_mal = [d.get("nom") or d.get("maladie") or d.get("symptome") or "" for d in donnees]
            noms_mal = [n for n in noms_mal if n]
            if not donnees:
                reponse_txt = f"Aucune maladie trouvée dans l'ontologie pour : « {question} »."
            elif noms_mal:
                reponse_txt = f"{len(donnees)} résultat(s) — {res.get('intention', '')} : {', '.join(noms_mal[:6])}."
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

            donnees = []
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
                donnees.append(item)

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
