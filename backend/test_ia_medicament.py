# -*- coding: utf-8 -*-
"""Script de test pour ia_medicament_service.py
Vérifie la requête SPARQL générée ET le nombre de résultats renvoyés par l'ontologie."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from medicament_service import MedicamentService
from ia_medicament_service import IAMedicamentService

ia = IAMedicamentService(MedicamentService())

tests = [
    # (question, sous-chaîne attendue dans le SPARQL, nombre minimal de résultats)
    ("Tous les médicaments",                                   "mdc:nomCommercial ?medicament", 8),
    ("Quels sont les effets secondaires du Brufen ?",          "mdc:Brufen mdc:peutProvoquer", 3),
    ("Effets secondaires du paracétamol",                      "mdc:Doliprane mdc:peutProvoquer", 2),
    ("Quels sont les effets secondaires graves ?",             "mdc:EffetGrave", 4),
    ("Quels médicaments provoquent des saignements ?",         "mdc:Saignement", 2),
    ("Effets secondaires digestifs",                           "mdc:EffetDigestif", 3),
    ("Quelles sont les contre-indications de l'Aspegic ?",     "mdc:Aspegic mdc:estContreIndiqueEn", 3),
    ("Je suis enceinte, quels médicaments éviter ?",           "mdc:Grossesse", 3),
    ("Médicaments contre-indiqués pour l'ulcère",              "mal:Ulcere_Gastrique_Sami", 3),
    ("Médicaments sans contre-indication",                     "FILTER NOT EXISTS", 1),
    ("Y a-t-il une interaction entre Coumadine et Aspegic ?",  "mdc:Coumadine , mdc:Aspegic", 1),
    ("Avec quoi interagit la Coumadine ?",                     "mdc:Coumadine , ?autre", 3),
    ("Toutes les interactions médicamenteuses",                "mdc:InteractionMedicamenteuse", 5),
    ("Quelle est la molécule du Glucophage ?",                 "FILTER(?m = mdc:Glucophage)", 1),
    ("Quels médicaments contiennent de l'ibuprofène ?",        "mdc:Mol_Ibuprofene", 1),
    ("Quel médicament pour la grippe ?",                       "mdc:traite mal:Grippe_Saisonniere", 3),
    ("Que traite le Clamoxyl ?",                               "mdc:Clamoxyl mdc:traite", 1),
    ("Liste des antibiotiques",                                "mdc:Antibiotique", 1),
    ("Quels sont les AINS ?",                                  "mdc:AntiInflammatoire", 2),
    ("Médicaments sans ordonnance",                            "necessiteOrdonnance false", 3),
    ("Médicaments sur ordonnance",                             "mdc:MedicamentSurOrdonnance", 5),
    ("Trier les médicaments du moins cher au plus cher",       "ORDER BY ASC(?prixTND)", 8),
    ("Quels médicaments sont à risque ?",                      "mdc:MedicamentARisque", 5),
    ("Quels sont les essais cliniques ?",                      "mdc:evalue", 6),
    ("Quel est le médicament le plus efficace ?",              "DESC(?tauxEfficacite) LIMIT 3", 3),
    ("Médicaments sans essai clinique",                        "MedicamentEvalueCliniquement", 2),
    ("Posologie du Doliprane",                                 "FILTER(?m = mdc:Doliprane)", 1),
    ("Combien de médicaments par classe ?",                    "COUNT(?m)", 5),
    ("C'est quoi Amlor ?",                                     "mdc:Amlor ?p ?v", 5),
    ("Certains médicaments sont-ils chers ?",                  "ORDER BY DESC(?prixTND)", 8),
]

ok = True
print("=" * 72)
print(" TEST ia_medicament_service.py ".center(72, "="))
print("=" * 72)
for question, expected, minimum in tests:
    res = ia.answer_question(question)
    n = len(res["data"].get("results", {}).get("bindings", []))
    passed = expected in res["sparql"] and n >= minimum and "error" not in res["data"]
    print(f"  {'OK' if passed else 'XX'} [{'PASS' if passed else 'FAIL'}] {question[:50]:50s} -> {n} résultat(s)")
    if not passed:
        ok = False
        print(f"         Intention : {res['intention']}")
        print(f"         Attendu   : {expected!r} et >= {minimum} résultat(s)")
        if "error" in res["data"]:
            print(f"         Erreur    : {res['data']['error']}")
# ----------------------------------------------------------------------
# Questions JAMAIS vues à l'entraînement (paraphrases, fautes de frappe)
# (question, intention attendue, entité attendue (id OWL) ou None)
# ----------------------------------------------------------------------
tests_nlp = [
    ("brufin effets indésirables ?",                         "effets_secondaires",   "Brufen"),
    ("Est-ce que la coumadinne est compatible avec l'aspirine ?", "interactions",    "Coumadine"),
    ("Mon fils a la grippe, que lui donner ?",                "traitement",           "Grippe_Saisonniere"),
    ("Qu'est-ce qui soulage le diabète ?",                    "traitement",           "Diabete_Type2"),
    ("Le glucophage contient quoi ?",                         "molecule",             "Glucophage"),
    ("Quel est le moins cher des médicaments ?",              "prix",                 None),
    ("Ma femme est enceinte, peut-elle prendre du Brufen ?",  "contre_indications",   "Brufen"),
    ("Donne moi les anticoagulants",                          "classe_therapeutique", "Anticoagulant"),
    ("Le Mopral provoque-t-il des vertiges ?",                "effets_secondaires",   "Mopral"),
    ("Combien coûte le Clamoxyl ?",                           "prix",                 "Clamoxyl"),
    ("Médicaments qu'on peut acheter librement",              "ordonnance",           None),
    ("Quels médicaments ont été testés en essai ?",           "essais_cliniques",     None),
    ("Fais-moi une description du Doliprane",                 "fiche_medicament",     "Doliprane"),
    ("Montre les interactions dangereuses",                   "interactions",         None),
    ("Je suis allergique à la pénicilline",                   "contre_indications",   "Allergie_Penicilline"),
    ("Quel médicament donne la diarrhée ?",                   "effets_secondaires",   "Diarrhee"),
    ("amoxiciline dans quel médicament ?",                    "molecule",             "Mol_Amoxicilline"),
]
print("-" * 72)
print(" Questions inédites (généralisation du modèle NLP) ".center(72, "-"))
for question, intent_attendu, entite in tests_nlp:
    res = ia.answer_question(question)
    nlp = res["nlp"]
    intent = nlp["intention_retenue"]["intention"]
    ids = [i for e in nlp["entites"] for i in e["ids"]]
    passed = intent == intent_attendu and (entite is None or entite in ids)
    print(f"  {'OK' if passed else 'XX'} [{'PASS' if passed else 'FAIL'}] {question[:46]:46s} -> {intent} "
          f"({nlp['intention_retenue']['confiance']:.2f})")
    if not passed:
        ok = False
        print(f"         Attendu : {intent_attendu} / {entite} — entités trouvées : {ids}")

# ----------------------------------------------------------------------
# Précision du classifieur d'intention (validation croisée à 5 plis, groupée par phrase modèle)
# ----------------------------------------------------------------------
from sklearn.base import clone
from sklearn.model_selection import GroupKFold, cross_val_score
X, y, groupes = ia.nlp.training_data
# GroupKFold : les variantes d'une même phrase modèle restent dans le même pli (pas de fuite)
scores = cross_val_score(clone(ia.nlp.classifier), X, y, groups=groupes, cv=GroupKFold(n_splits=5))
print("-" * 72)
print(f"  Validation croisée du classifieur : précision moyenne {scores.mean() * 100:.1f} % "
      f"(± {scores.std() * 100:.1f}) sur {len(X)} phrases")
print("=" * 72)
print(" ALL TESTS PASSED " if ok else " SOME TESTS FAILED ")
print("=" * 72)
sys.exit(0 if ok else 1)
