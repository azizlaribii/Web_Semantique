# -*- coding: utf-8 -*-
"""Blueprint Flask autonome du Service médical."""
from flask import Blueprint, jsonify, request
from medical_service import MedicalService
from ia_medical_service import IAMedicalService
bp=Blueprint("medical",__name__)
_service=None
_ia=None
def _svc():
 global _service,_ia
 if _service is None:
  _service=MedicalService();_ia=IAMedicalService(_service)
 return _service
def _ia_svc():
 _svc();return _ia
def _run(fn,code=200):
 try:return jsonify(fn()),code
 except ValueError as e:return jsonify({"error":str(e)}),400
 except KeyError as e:return jsonify({"error":f"Élément introuvable : {e.args[0]}"}),404
 except Exception as e:return jsonify({"error":str(e)}),500
@bp.get("/api/medical/records")
def records(): return _run(lambda:_svc().records(request.args.get("type")))
@bp.get("/api/medical/options")
def options(): return _run(lambda:_svc().options())
@bp.get("/api/medical/summary")
def summary(): return _run(lambda:_svc().summary())
@bp.post("/api/medical/records")
def create(): return _run(lambda:_svc().create(request.get_json(force=True,silent=True) or {}),201)
@bp.put("/api/medical/records/<path:record_id>")
def update(record_id): return _run(lambda:_svc().update(record_id,request.get_json(force=True,silent=True) or {}))
@bp.delete("/api/medical/records/<path:record_id>")
def delete(record_id): return _run(lambda:_svc().delete(record_id))
@bp.post("/api/medical/reset")
def reset(): return _run(lambda:_svc().reset())
@bp.post("/api/medical/sparql")
def sparql():
 from rdflib.plugins.sparql.processor import prepareQuery
 q=(request.get_json(force=True,silent=True) or {}).get("query","").strip()
 if not q:return jsonify({"error":"Requête vide"}),400
 try:
  result=_svc().graph.query(q)
  return jsonify({"head":{"vars":list(result.vars or [])},"results":{"bindings":[{str(v):{"type":"literal","value":str(row[v])} for v in result.vars if row[v] is not None} for row in result]}})
 except Exception as e:return jsonify({"error":f"Requête SPARQL invalide : {e}"}),400
@bp.post("/api/ia-medical/ask")
def ask():
 q=(request.get_json(force=True,silent=True) or {}).get("question","").strip()
 if not q:return jsonify({"error":"Question vide"}),400
 return _run(lambda:_ia_svc().answer_question(q))
def register_medical(app):
 app.register_blueprint(bp)
 def reload_medical():
  _svc().load();_ia_svc().refresh()
 return reload_medical
