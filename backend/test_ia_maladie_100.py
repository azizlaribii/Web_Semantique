# -*- coding: utf-8 -*-
"""
Test de validation de l'IA Maladie sur 100 questions en langage naturel.
Exécute chaque question dynamiquement sur le graphe ontologique RDFLib.
Vérifie la génération SPARQL et la cohérence des données extraites.
"""

import os
import sys
import io

# Encodage UTF-8 pour Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import pyparsing_patch
from rdflib_service import MaladieService
from ia_maladie_service import IAMaladieService

ms = MaladieService()
ia = IAMaladieService(ms)

# 100 questions organisées en 10 catégories thématiques
TEST_SUITE = [
    # ── Catégorie 1 : Prise en charge & Médecins (10 questions) ──
    ("Quels médecins prennent en charge chaque maladie ?", "medecin", 4),
    ("Quel médecin prend en charge le diabète ?", "Dr_Ali", 1),
    ("Quel médecin assure le suivi de l'hypertension ?", "Dr_Sonia", 1),
    ("Quel médecin a diagnostiqué la grippe de Sami ?", "Dr_Ahmed", 1),
    ("Qui soigne Sami ?", "Dr_Ahmed", 1),
    ("Quels médecins traitent chaque maladie ?", "medecin", 4),
    ("Quelles maladies nécessitent un suivi par un médecin ?", "necessiteSuiviPar", 2),
    ("Quels sont les médecins qui ont posé un diagnostic ?", "diagnostique", 2),
    ("Quelles maladies a diagnostiquées le Dr Ahmed ?", "Grippe", 1),
    ("Qui prend en charge l'hypertension artérielle ?", "Dr_Sonia", 1),

    # ── Catégorie 2 : Patients & Pathologies (10 questions) ──
    ("De quelle maladie souffre chaque patient ?", "patient", 10),
    ("De quelle maladie souffre Ahmed ?", "Diabete", 2),
    ("Quels patients sont atteints de diabète ?", "Patient", 2),
    ("Quels patients ont la grippe ?", "Sami", 1),
    ("Quels patients ont de l'hypertension ?", "Hypertension", 3),
    ("De quelle maladie souffre Sami ?", "Grippe", 1),
    ("Quels patients souffrent d'asthme ?", "Sara", 1),
    ("Quels patients ont le paludisme ?", "Omar", 1),
    ("Quels patients ont la migraine ?", "Sara", 1),
    ("Patients atteints d'une maladie chronique", "patient", 2),

    # ── Catégorie 3 : Médicaments & Traitements de la Grippe (10 questions) ──
    ("Quels médicaments sont associés à la grippe ?", "medicament", 3),
    ("Quel traitement pour la grippe saisonnière ?", "Paracetamol", 2),
    ("Quels médicaments traitent la grippe ?", "medicament", 3),
    ("Le paracétamol traite-t-il la grippe ?", "Paracetamol", 1),
    ("Quels antalgiques pour la grippe ?", "Paracetamol", 1),
    ("Quel médicament est prescrit pour la grippe de Sami ?", "Paracetamol", 1),
    ("Quels médicaments contre la grippe sont disponibles ?", "medicament", 2),
    ("Peut-on traiter la grippe avec de l'ibuprofène ?", "Ibuprofene", 1),
    ("Donne-moi les médicaments associés à la grippe", "medicament", 3),
    ("Quels sont les traitements enregistrés pour la grippe ?", "medicament", 2),

    # ── Catégorie 4 : Médicaments & Traitements de l'Angine (10 questions) ──
    ("Quel médicament est associé à l’angine ?", "medicament", 2),
    ("Quels médicaments traitent l'angine ?", "medicament", 2),
    ("Quel antibiotique traite l'angine à streptocoque ?", "Amoxicilline", 1),
    ("L'amoxicilline soigne-t-elle l'angine ?", "Amoxicilline", 1),
    ("Quels médicaments contre l'angine ?", "medicament", 2),
    ("Traitement de l'angine streptococcique", "Amoxicilline", 1),
    ("Quels antibiotiques pour l'angine ?", "Amoxicilline", 1),
    ("Quel est le médicament prescrit pour l'angine ?", "medicament", 2),
    ("Médicament associé à Angine", "medicament", 2),
    ("Quels médicaments soulagent l'angine ?", "medicament", 2),

    # ── Catégorie 5 : Traitements globaux & Contre-indications (10 questions) ──
    ("Quels médicaments sont associés à chaque maladie ?", "medicament", 20),
    ("Quels médicaments traitent le diabète ?", "Metformine", 1),
    ("Quels médicaments traitent l'hypertension ?", "Amlodipine", 1),
    ("Quels médicaments traitent l'asthme ?", "Ventoline", 1),
    ("Quels médicaments traitent le paludisme ?", "Artemisinine", 1),
    ("Quels médicaments sont contre-indiqués pour l'ulcère ?", "ContreIndique", 1),
    ("Quels médicaments traitent la migraine ?", "medicament", 1),
    ("Quels médicaments traitent la gastrite ?", "medicament", 1),
    ("Quels médicaments traitent l'arthrite ?", "medicament", 1),
    ("Quels médicaments contiennent du paracétamol ?", "Paracetamol", 1),

    # ── Catégorie 6 : Symptômes spécifiques des Maladies (10 questions) ──
    ("Quels sont les symptômes du diabète ?", "symptome", 2),
    ("Quels sont les symptômes de l’asthme ?", "symptome", 2),
    ("Quels sont les symptômes de la angine ?", "symptome", 2),
    ("Quels sont les symptômes de lagrippe?", "symptome", 3),
    ("Quels sont les symptômes de la grippe ?", "symptome", 3),
    ("Quels sont les symptômes de l'hypertension ?", "symptome", 1),
    ("Quels sont les symptômes de l'ulcère ?", "symptome", 1),
    ("Quelles maladies provoquent la fièvre ?", "Fievre", 2),
    ("Quelles maladies ont la toux comme symptôme ?", "Toux", 1),
    ("Quels sont les symptômes de la grippe saisonnière ?", "symptome", 3),

    # ── Catégorie 7 : Symptômes catégorisés & Symptômes Communs (10 questions) ──
    ("Quel symptôme est commun à la grippe et à l'angine ?", "Fievre", 1),
    ("Quels sont les symptômes digestifs ?", "SymptomeDigestif", 2),
    ("Quels sont les symptômes generale?", "SymptomeGeneral", 4),
    ("Quels sont les symptômes généraux ?", "SymptomeGeneral", 4),
    ("Quels sont les symptômes associés à chaque maladie infectieuse ?", "symptome", 10),
    ("Liste des symptômes respiratoires", "SymptomeRespiratoire", 2),
    ("Existe-t-il un symptôme partagé entre grippe et angine ?", "Fievre", 1),
    ("Quels symptômes provoquent des nausées ?", "Nausee", 1),
    ("Quels symptômes sont liés à la fatigue ?", "Fatigue", 1),
    ("Quelles maladies provoquent de la fatigue ?", "Fatigue", 1),

    # ── Catégorie 8 : Statistiques, Agrégations & Tri (10 questions) ──
    ("Quelle maladie a le plus de symptômes ?", "nb_symptomes", 1),
    ("Maladies avec le maximum de symptômes", "nb_symptomes", 1),
    ("Combien y a-t-il de maladies ?", "nb_maladies", 1),
    ("Quelle est la maladie la plus fréquente ?", "nb_patients", 1),
    ("Maladies avec plus de 2 symptômes", "COUNT", 1),
    ("Combien de patients ont la grippe ?", "nb_patients", 1),
    ("Trier les maladies par gravité", "ORDER BY DESC", 5),
    ("Quelles sont les maladies graves ?", "gravite", 2),
    ("Patients qui ont plusieurs maladies", "nb_maladies", 1),
    ("Nombre total de maladies dans l'ontologie", "COUNT", 1),

    # ── Catégorie 9 : Classes, Hiérarchies & Types (10 questions) ──
    ("Quelles sont les maladies chroniques dans l’ontologie ?", "MaladieChronique", 4),
    ("Quelles sont les maladies infectieuses ?", "MaladieInfectieuse", 2),
    ("Quelles sont les maladies contagieuses ?", "contagieuse", 2),
    ("Liste des maladies non contagieuses", "false", 2),
    ("Quelles maladies sont digestives ?", "MaladieDigestive", 1),
    ("Le diabète est-il une maladie chronique ?", "chronique", 1),
    ("La grippe est-elle contagieuse ?", "contagieuse", 1),
    ("Le diabète est-il contagieux ?", "contagieuse", 1),
    ("L'hypertension est-elle chronique ?", "chronique", 1),
    ("Toutes les maladies de l'ontologie", "maladie", 10),

    # ── Catégorie 10 : Agents pathogènes, Fiches & CIM-10 (10 questions) ──
    ("Quel est l'agent pathogène de la grippe ?", "Influenza", 1),
    ("Quel est l'agent pathogène de l'angine ?", "Streptocoque", 1),
    ("Quel est le virus de la grippe ?", "Influenza", 1),
    ("Quelle est la bactérie de l'angine ?", "Streptocoque", 1),
    ("Liste des virus de l'ontologie", "Virus", 1),
    ("Liste des bactéries de l'ontologie", "Bacterie", 1),
    ("C'est quoi le diabète ?", "Diabete", 1),
    ("Quelle est la gravité de l'hypertension ?", "gravite", 1),
    ("Quel est le code CIM-10 de la grippe ?", "J11", 1),
    ("Quel est le code CIM-10 du diabète ?", "E11", 1),
]

def run_100_tests():
    print("=" * 80)
    print("   TEST DE VALIDATION DE LA CLASSE MALADIE SUR 100 QUESTIONS")
    print("   Ontologie RDFLib (ontologie_medicale (1).ttl + ontologie_maladie.owl)")
    print("=" * 80)

    total = len(TEST_SUITE)
    correct = 0
    incorrect = 0
    failures = []

    for idx, (question, expected_pattern, min_results) in enumerate(TEST_SUITE, 1):
        res = ia.answer_question(question)
        sparql = res.get("sparql", "")
        intention = res.get("intention", "")
        data = res.get("data", {})
        bindings = data.get("results", {}).get("bindings", [])
        count = len(bindings)
        has_error = "error" in data or not sparql

        # Validation : motif attendu dans sparql/bindings + résultats dynamiques non nuls + pas d'erreur
        pattern_in_sparql = expected_pattern.lower() in sparql.lower()
        pattern_in_results = any(
            expected_pattern.lower() in v.get("value", "").lower()
            for b in bindings for v in b.values()
        )
        pattern_in_intention = expected_pattern.lower() in intention.lower()

        is_valid = (
            not has_error
            and (pattern_in_sparql or pattern_in_results or pattern_in_intention)
            and count >= min_results
        )

        if is_valid:
            correct += 1
            status = "✓ OK"
        else:
            incorrect += 1
            status = "✗ FAIL"
            failures.append({
                "id": idx,
                "question": question,
                "expected": expected_pattern,
                "min_results": min_results,
                "actual_count": count,
                "intention": intention,
                "error": data.get("error", "Motif non trouvé ou résultats insuffisants")
            })

        print(f"[{idx:03d}/100] {status} | Q: {question[:50]:<50} | R: {count:2d} | Int: {intention[:25]}")

    print("=" * 80)
    print("                      BILAN GLOBAL DU TEST")
    print("=" * 80)
    print(f"  • Total de questions testées : {total}")
    print(f"  • Réponses CORRECTES         : {correct} / {total} ({correct / total * 100:.1f}%)")
    print(f"  • Réponses INCORRECTES       : {incorrect} / {total} ({incorrect / total * 100:.1f}%)")
    print("=" * 80)

    if failures:
        print("\nDétail des échecs :")
        for f in failures:
            print(f"  [Q {f['id']}] {f['question']}")
            print(f"         Attendu: '{f['expected']}' (min {f['min_results']}) | Obtenu: {f['actual_count']} résultat(s)")
            print(f"         Intention: {f['intention']}")
            print(f"         Détail: {f['error']}\n")

    return correct, incorrect, total

if __name__ == "__main__":
    run_100_tests()
