# -*- coding: utf-8 -*-
"""Tests de fumée du module Service médical."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from medical_service import MedicalService

def main():
    svc=MedicalService()
    print("Statistiques :",svc.summary())
    for q in [
        "Liste des consultations",
        "Combien de consultations existe-t-il ?",
        "Afficher les opérations médicales",
        "Quelles sont les ordonnances ?",
        "Combien d'ordonnances sont enregistrées ?",
    ]:
        r=svc.ask(q)
        assert "sparql" in r and "donnees" in r and "nlp" in r
        print("[OK]",q,"->",r["intention"],"(",r["count"],")")
    print("Tests Service médical terminés.")

if __name__=="__main__": main()
