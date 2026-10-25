# -*- coding: utf-8 -*-
"""
Tests complets pour ia_service.py - Classe Personne
Verifie que chaque question genere bien la bonne requete SPARQL.
Catégories testées :
  A. Comptage (COUNT)
  B. Filtres d'âge (Personne / Médecin / Patient)
  C. Individus nommés (Fatima, Sami, Ahmed, Karim, Amina, Ali)
  D. Dossier médical
  E. CIN / Email
  F. Groupe sanguin
  G. Relations (soigne, connait)
  H. Hiérarchie & Métadonnées OWL
  I. Stagiaires
  J. Patients enfants / adultes
  K. Médecins (généraliste, spécialiste, cardiologue)
  L. Urgences / Service
  M. Tri dynamique (ORDER BY)
  N. Requête par défaut (fallback)
"""
import sys, os
import io
# Forcer l'encodage UTF-8 sur Windows pour eviter UnicodeEncodeError
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(__file__))

from ia_service import IAService

ia = IAService()

# ─────────────────────────────────────────────────────────────────────────────
# Définition des cas de test
# Format : (catégorie, question, sous-chaîne attendue dans le SPARQL généré)
# ─────────────────────────────────────────────────────────────────────────────
tests = [

    # ── A. COMPTAGE ──────────────────────────────────────────────────────────
    ("A", "combien de personnes sont dans l'ontologie",         "COUNT"),
    ("A", "combien de medecins y a-t-il",                       "COUNT"),
    ("A", "nombre de patients",                                  "COUNT"),
    ("A", "combien de stagiaires",                               "COUNT"),

    # ── B. FILTRES D'ÂGE ─────────────────────────────────────────────────────
    ("B", "personne agee de 35 ans",                             "FILTER(?age = 35)"),
    ("B", "personnes entre 20 et 50 ans",                        "FILTER(?age >= 20 && ?age <= 50)"),
    ("B", "personnes de plus de 60 ans",                         "FILTER(?age > 60)"),
    ("B", "personnes de moins de 18 ans",                        "FILTER(?age < 18)"),
    ("B", "patients ayant 8 ans",                                "FILTER(?age = 8)"),
    ("B", "patients entre 5 et 25 ans",                          "FILTER(?age >= 5 && ?age <= 25)"),
    ("B", "patients de plus de 30 ans",                          "FILTER(?age > 30)"),
    ("B", "patients de moins de 10 ans",                         "FILTER(?age < 10)"),
    ("B", "medecin age de 45 ans",                               "FILTER(?age = 45)"),
    ("B", "medecins entre 30 et 50 ans",                         "FILTER(?age >= 30 && ?age <= 50)"),
    ("B", "medecins de plus de 40 ans",                          "FILTER(?age > 40)"),
    ("B", "donne moi toutes les patients d'un age =8",           "FILTER(?age = 8)"),
    ("B", "donne moi les patients a un intervalle de age de 5 a 25", "FILTER(?age >= 5 && ?age <= 25)"),

    # ── C. INDIVIDUS NOMMÉS ───────────────────────────────────────────────────
    ("C", "qui est fatima",                                      ":Dr_Fatima"),
    ("C", "donne moi les infos de fatima",                       ":Dr_Fatima"),
    ("C", "fiche de sami",                                       ":Sami"),
    ("C", "informations sur sami",                               ":Sami"),
    ("C", "qui est ahmed",                                       ":Dr_Ahmed"),
    ("C", "fiche du docteur ahmed",                              ":Dr_Ahmed"),
    ("C", "qui est karim",                                       ":Dr_Karim"),
    ("C", "informations sur karim",                              ":Dr_Karim"),
    ("C", "fiche d'amina",                                       ":Amina"),
    ("C", "informations sur amina",                              ":Amina"),
    ("C", "fiche d'ali",                                         ":Ali_Stagiaire"),
    ("C", "informations sur ali",                                ":Ali_Stagiaire"),
    ("C", "dr fatima",                                           ":Dr_Fatima"),

    # ── D. DOSSIER MÉDICAL ────────────────────────────────────────────────────
    ("D", "donne moi le dossier de sami",                        ":Sami"),
    ("D", "dossier de amina",                                    ":Amina"),
    ("D", "quel est le dossier du patient PAT-001",              "PAT-001"),
    ("D", "trouver le patient avec dossier PAT-002",             "PAT-002"),
    ("D", "tous les patients enregistres",                        "numeroDossier"),

    # ── E. CIN / EMAIL ────────────────────────────────────────────────────────
    ("E", "personne avec cin 12345678",                          "numeroCIN"),
    ("E", "trouver le medecin avec cin 00345678",                "numeroCIN"),
    ("E", "patient avec cin 87654321",                           "numeroCIN"),
    ("E", "chercher par email test@hopital.tn",                  "test@hopital.tn"),

    # ── F. GROUPE SANGUIN ─────────────────────────────────────────────────────
    ("F", "quel est le groupe sanguin",                           "groupeSanguin"),
    ("F", "patients avec groupe sanguin A+",                      "groupeSanguin"),
    ("F", "trouver les patients de groupe O-",                    "groupeSanguin"),
    ("F", "liste des personnes avec sang AB+",                    "groupeSanguin"),

    # ── G. RELATIONS ──────────────────────────────────────────────────────────
    ("G", "qui soigne qui",                                       ":soigne"),
    ("G", "qui soigne sami",                                      ":soigne"),
    ("G", "quels patients soigne ahmed",                          ":Dr_Ahmed"),
    ("G", "qui connait qui",                                      ":connait"),
    ("G", "les collegues",                                        ":connait"),
    ("G", "symptomes des patients",                               ":presente"),

    # ── H. HIÉRARCHIE & MÉTADONNÉES OWL ──────────────────────────────────────
    ("H", "liste des classes de l'ontologie",                     "owl:Class"),
    ("H", "toutes les classes",                                   "owl:Class"),
    ("H", "quelles sont les sous classes de personne",            "subClassOf"),
    ("H", "hierarchie des classes",                               "subClassOf"),
    ("H", "les object properties de l'ontologie",                 "owl:ObjectProperty"),
    ("H", "les proprietes de donnee",                             "owl:DatatypeProperty"),
    ("H", "tous les individus de l'ontologie",                    "NamedIndividual"),
    ("H", "les annotations de l'ontologie",                       "rdfs:comment"),

    # ── I. STAGIAIRES ─────────────────────────────────────────────────────────
    ("I", "liste des stagiaires",                                 ":Stagiaire"),
    ("I", "tous les stagiaires",                                  ":Stagiaire"),
    ("I", "qui sont les stagiaires",                              ":Stagiaire"),

    # ── J. PATIENTS ENFANTS / ADULTES ─────────────────────────────────────────
    ("J", "patients enfants",                                     "PatientEnfant"),
    ("J", "liste des patients adultes",                           "PatientAdulte"),
    ("J", "patients adultes dans l'hopital",                      "PatientAdulte"),

    # ── K. MÉDECINS ───────────────────────────────────────────────────────────
    ("K", "donne moi les medecins generalistes",                  "MedecinGeneraliste"),
    ("K", "liste des generalistes",                               "MedecinGeneraliste"),
    ("K", "quels sont les medecins specialistes",                 "MedecinSpecialiste"),
    ("K", "liste des cardiologues",                               "Cardiologue"),
    ("K", "tous les medecins",                                    ":Medecin"),
    ("K", "liste des docteurs",                                   ":Medecin"),
    ("K", "medecins en cardiologie",                              "cardio"),

    # ── L. URGENCES / SERVICE ─────────────────────────────────────────────────
    ("L", "qui travaille aux urgences",                           "Service_Urgences"),
    ("L", "personnes au service urgence",                         "Service_Urgences"),
    ("L", "equipe du service cardiologie",                        "Service_Cardio"),

    # ── M. TRI DYNAMIQUE ──────────────────────────────────────────────────────
    ("M", "trier les patients par nom",                           "ORDER BY"),
    ("M", "patients trier par age croissant",                     "ORDER BY"),
    ("M", "liste des patients trie par dossier",                  "ORDER BY"),
    ("M", "classer les personnes par cin",                        "ORDER BY"),

    # ── N. FALLBACK (Requête par défaut) ──────────────────────────────────────
    ("N", "bonjour",                                              ":Personne"),
    ("N", "donne moi tout",                                       ":Personne"),
]

# ─────────────────────────────────────────────────────────────────────────────
# Exécution des tests avec rapport détaillé par catégorie
# ─────────────────────────────────────────────────────────────────────────────
category_stats = {}
global_ok = True

print("\n" + "=" * 75)
print("  TEST ia_service.py — Classe PERSONNE  ".center(75, "="))
print("=" * 75)

current_cat = None
for cat, question, expected in tests:
    if cat != current_cat:
        current_cat = cat
        labels = {
            "A": "A. COMPTAGE (COUNT)",
            "B": "B. FILTRES D'AGE",
            "C": "C. INDIVIDUS NOMMES",
            "D": "D. DOSSIER MEDICAL",
            "E": "E. CIN / EMAIL",
            "F": "F. GROUPE SANGUIN",
            "G": "G. RELATIONS",
            "H": "H. HIERARCHIE & METADONNEES OWL",
            "I": "I. STAGIAIRES",
            "J": "J. PATIENTS ENFANTS / ADULTES",
            "K": "K. MEDECINS",
            "L": "L. URGENCES / SERVICE",
            "M": "M. TRI DYNAMIQUE",
            "N": "N. FALLBACK (defaut)",
        }
        print(f"\n  {'-'*71}")
        print(f"  {labels.get(cat, cat)}")
        print(f"  {'-'*71}")

    try:
        sparql, intention, explication = ia.translate_question_to_sparql(question)
        passed = expected in sparql
    except Exception as e:
        sparql = f"ERREUR: {e}"
        passed = False
        intention = ""

    status = "PASS" if passed else "FAIL"
    mark   = "OK" if passed else "XX"

    # Statistiques par catégorie
    if cat not in category_stats:
        category_stats[cat] = {"pass": 0, "fail": 0}
    if passed:
        category_stats[cat]["pass"] += 1
    else:
        category_stats[cat]["fail"] += 1
        global_ok = False

    # Affichage
    q_display = question[:58].ljust(58)
    print(f"  {mark} [{status}]  {q_display}")
    if not passed:
        print(f"         >> Attendu  : {expected}")
        print(f"         >> SPARQL   : {sparql[:280]}")
        print(f"         >> Intention: {intention}")

# ─────────────────────────────────────────────────────────────────────────────
# Résumé global
# ─────────────────────────────────────────────────────────────────────────────
total_pass = sum(v["pass"] for v in category_stats.values())
total_fail = sum(v["fail"] for v in category_stats.values())
total      = total_pass + total_fail

print("\n" + "=" * 75)
print("  RESUME PAR CATEGORIE".center(75))
print("=" * 75)
labels_map = {
    "A": "Comptage",
    "B": "Filtres d'age",
    "C": "Individus nommes",
    "D": "Dossier medical",
    "E": "CIN / Email",
    "F": "Groupe sanguin",
    "G": "Relations",
    "H": "Hierarchie & OWL",
    "I": "Stagiaires",
    "J": "Enfants / Adultes",
    "K": "Medecins",
    "L": "Urgences / Service",
    "M": "Tri dynamique",
    "N": "Fallback",
}
for cat, stats in category_stats.items():
    p, f = stats["pass"], stats["fail"]
    bar = ("#" * p) + ("." * f)
    label = labels_map.get(cat, cat).ljust(20)
    result = "OK" if f == 0 else f"FAIL ({f} erreur{'s' if f>1 else ''})"
    print(f"  {cat}. {label} [{bar}] {p}/{p+f}  {result}")

print("=" * 75)
score_pct = int(total_pass / total * 100) if total > 0 else 0
print(f"  SCORE GLOBAL : {total_pass}/{total} ({score_pct}%)")
if global_ok:
    print("  TOUS LES TESTS SONT PASSES ".center(75, "="))
else:
    print(f"  {total_fail} TEST(S) ECHOUE(S) — voir details ci-dessus".center(75))
print("=" * 75 + "\n")
