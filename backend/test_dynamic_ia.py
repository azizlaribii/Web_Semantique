# -*- coding: utf-8 -*-
"""Test de la détection dynamique d'entités, classes et propriétés depuis ontologie_medicale (1).ttl"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

import pyparsing_patch
from rdflib_service import RDFLibService
from ia_service import IAService

print("Initialisation du service RDFLib...")
rdf = RDFLibService()
ia = IAService(rdf)

schema = rdf.get_ontology_schema()
print(f"Schéma extrait avec succès :")
print(f"  • Classes : {len(schema['classes'])}")
print(f"  • Object Properties : {len(schema['object_properties'])}")
print(f"  • Datatype Properties : {len(schema['datatype_properties'])}")
print(f"  • Individus : {len(schema['individuals'])}")

# Tester quelques requêtes dynamiques
sample_inds = schema['individuals'][:3]
for ind in sample_inds:
    q = f"qui est {ind['nom']} ?"
    res = ia.answer_question(q)
    print(f"\n[Question] {q}")
    print(f"  Intention : {res['intention']}")
    print(f"  Résultat  : {res['answer_summary']}")
    print(f"  Données count : {len(res['data'].get('results', {}).get('bindings', []))}")

# Tester une question sur les object properties
q_prop = "quelles sont les object properties ?"
res_prop = ia.answer_question(q_prop)
print(f"\n[Question] {q_prop}")
print(f"  Intention : {res_prop['intention']}")
print(f"  Données count : {len(res_prop['data'].get('results', {}).get('bindings', []))}")

# Tester une question sur les data properties
q_dp = "quelles sont les data properties ?"
res_dp = ia.answer_question(q_dp)
print(f"\n[Question] {q_dp}")
print(f"  Intention : {res_dp['intention']}")
print(f"  Données count : {len(res_dp['data'].get('results', {}).get('bindings', []))}")

print("\n[OK] Test dynamique termine avec succes.")
