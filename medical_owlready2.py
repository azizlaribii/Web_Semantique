# -*- coding: utf-8 -*-
"""Inspecte/regénère la hiérarchie du Service médical avec Owlready2.
Le fichier ontologie_medicale.owl fourni est la source de référence.
Ce script ne remplace pas automatiquement l'ontologie existante.
"""
import os
from owlready2 import get_ontology
HERE=os.path.dirname(os.path.abspath(__file__))
path=os.path.join(HERE,"ontologie_medicale.owl")
onto=get_ontology("file://"+path.replace("\\","/")).load()
print("Ontologie médicale :", onto.base_iri)
for name in ("Service_medicale","Consultation","Opération","Ordonnance"):
    cls=onto[name]
    print(name, "->", [x.name for x in cls.subclasses()] if cls else "classe absente")
print("Individus médicaux :", sum(1 for x in onto.individuals()))
