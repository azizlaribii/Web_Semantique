# -*- coding: utf-8 -*-
"""Script de test pour ia_service.py"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from ia_service import IAService

ia = IAService()

tests = [
    # (question, sous-chaine attendue dans le SPARQL)
    ("donne moi toutes les patients d'un age =8",       "FILTER(?age = 8)"),
    ("donne moi les patients a un intervalle de age de 5 a 25", "FILTER(?age >= 5 && ?age <= 25)"),
    ("patients entre 5 et 25 ans",                      "FILTER(?age >= 5 && ?age <= 25)"),
    ("patients de plus de 30 ans",                      "FILTER(?age > 30)"),
    ("patients de moins de 10 ans",                     "FILTER(?age < 10)"),
    ("patients ayant 8 ans",                            "FILTER(?age = 8)"),
    ("patients agees de 8 ans",                         "FILTER(?age = 8)"),
    ("donne moi les medecins generalistes",             "MedecinGeneraliste"),
    ("qui travaille aux urgences",                      "Service_Urgences"),
    ("tous les patients",                               ":Patient"),
    ("quels sont les medecins specialistes",            "MedecinSpecialiste"),
    ("donne moi le dossier de sami",                    ":Sami"),
    ("quel est le groupe sanguin",                      "groupeSanguin"),
    ("qui soigne qui",                                  ":soigne"),
    ("dr fatima",                                       ":Dr_Fatima"),
    ("liste des cardiologues",                          "Cardiologue"),
]

ok = True
print("=" * 65)
print(" TEST ia_service.py ".center(65, "="))
print("=" * 65)
for question, expected in tests:
    q, intention, _ = ia.translate_question_to_sparql(question)
    passed = expected in q
    status = "PASS" if passed else "FAIL"
    mark = "OK" if passed else "XX"
    print(f"  {mark} [{status}]  {question[:52]}")
    if not passed:
        ok = False
        print(f"         Expected : {expected}")
        print(f"         SPARQL   : {q[:250]}")
print("=" * 65)
print(" ALL TESTS PASSED " if ok else " SOME TESTS FAILED ", end="")
print()
print("=" * 65)
