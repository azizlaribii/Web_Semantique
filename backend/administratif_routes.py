# -*- coding: utf-8 -*-
"""
Routes Flask du module Service administratif (Blueprint).

Branchement dans backend/app.py (2 lignes, apres la creation de `app`) :

    from administratif_routes import register_administratif
    reload_administratif = register_administratif(app)

et dans reload_all_services(), avant `_last_reload_info["ts"] = ...` :

    try:
        reload_administratif()
        print("[HotReload] OK module administratif recharge")
    except Exception as e:
        errors.append(f"administratif: {e}")
"""
from flask import Blueprint, jsonify, request
from administratif_service import ServiceAdministratif, get_service
from ia_administratif_service import IAAdministratifService

bp = Blueprint("administratif", __name__)
_ia = None


def _svc():
    return get_service()


def _ia_service():
    global _ia
    if _ia is None:
        _ia = IAAdministratifService(_svc())
    return _ia


def _crud(action):
    """Execute une operation, rafraichit le vocabulaire NLP et formate les erreurs."""
    try:
        res = action()
        _ia_service().refresh()
        return jsonify(res)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except KeyError as e:
        return jsonify({"error": f"Element introuvable : {e.args[0]}"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _lecture(fn):
    try:
        return jsonify(fn())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------ lecture
@bp.get("/api/administratif/rendez-vous")
def rdv_list():
    return _lecture(lambda: _svc().lister_rdv(request.args.get("statut")))

@bp.get("/api/administratif/dossiers")
def dossiers_list():
    return _lecture(lambda: _svc().lister_dossiers())

@bp.get("/api/administratif/factures")
def factures_list():
    return _lecture(lambda: _svc().lister_factures())

@bp.get("/api/administratif/assurances")
def assurances_list():
    return _lecture(lambda: _svc().lister_assurances())

@bp.get("/api/administratif/options")
def options():
    return _lecture(lambda: _svc().options())

@bp.get("/api/summary-administratif")
def summary():
    return _lecture(lambda: _svc().resume())

@bp.get("/api/graph-administratif")
def graph():
    return _lecture(lambda: _svc().graphe())


# ---------------------------------------------------- CRUD (SPARQL Update)
@bp.post("/api/administratif/rendez-vous")
def rdv_create():
    return _crud(lambda: _svc().creer_rdv(request.get_json(force=True, silent=True) or {}))

@bp.put("/api/administratif/rendez-vous/<rid>")
def rdv_update(rid):
    return _crud(lambda: _svc().modifier_rdv(rid, request.get_json(force=True, silent=True) or {}))

@bp.delete("/api/administratif/rendez-vous/<rid>")
def rdv_delete(rid):
    return _crud(lambda: _svc().supprimer_rdv(rid))

@bp.post("/api/administratif/factures")
def facture_create():
    return _crud(lambda: _svc().creer_facture(request.get_json(force=True, silent=True) or {}))

@bp.post("/api/administratif/paiements")
def paiement_create():
    return _crud(lambda: _svc().enregistrer_paiement(request.get_json(force=True, silent=True) or {}))

@bp.post("/api/administratif/reset")
def reset():
    return _crud(lambda: _svc().reset())


# --------------------------------------------- SPARQL JSON + IA (NL -> SPARQL)
@bp.post("/api/administratif/sparql")
def sparql():
    q = (request.get_json(force=True, silent=True) or {}).get("query", "").strip()
    if not q:
        return jsonify({"error": "Requete vide"}), 400
    try:
        return jsonify(_svc().sparql_json(q))
    except Exception as e:
        return jsonify({"error": f"Requete SPARQL invalide : {e}"}), 400

@bp.post("/api/ia-administratif/ask")
def ia_ask():
    question = (request.get_json(force=True, silent=True) or {}).get("question", "").strip()
    if not question:
        return jsonify({"error": "Question vide"}), 400
    try:
        return jsonify(_ia_service().answer_question(question))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def register_administratif(app):
    """Enregistre le Blueprint et retourne la fonction de rechargement (hot-reload)."""
    app.register_blueprint(bp)

    def reload_administratif():
        s = _svc()
        s._charger()
        _ia_service().refresh()
    return reload_administratif
