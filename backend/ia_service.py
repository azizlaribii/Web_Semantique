# -*- coding: utf-8 -*-
"""
Module IA : Traduction Question Utilisateur en Langage Naturel -> Requête SPARQL
Conforme à l'architecture du projet (Front-end -> IA API -> Requête SPARQL -> Fuseki/Back-end).
Fonctionne de manière autonome avec un moteur d'interprétation sémantique médical.
"""

import re
import os
from typing import Dict, Any, Tuple, Optional

PREFIXES = """PREFIX : <http://example.org/ontologie-medicale#>
PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""


# ---------------------------------------------------------------------------
# Fonctions utilitaires (module-level)
# ---------------------------------------------------------------------------

def _extract_numbers(text: str):
    """Extrait tous les entiers trouvés dans le texte."""
    return re.findall(r'\d+', text)


def _detect_target_class(q: str) -> Tuple[str, str]:
    """
    Détecte la classe cible principale depuis la question.
    Retourne (classe_sparql, label_humain).
    """
    # Médecins
    if any(w in q for w in ["medecin", "médecin", "docteur", "dr", "cardiologue",
                             "specialiste", "spécialiste", "generaliste", "généraliste"]):
        return ":Medecin", "Médecin"
    # Stagiaires
    if "stagiaire" in q:
        return ":Stagiaire", "Stagiaire"
    # Patients (mot explicite)
    if "patient" in q:
        return ":Patient", "Patient"
    # Par défaut : toutes les personnes
    return ":Personne", "Personne"


def _build_age_filter_query(target_class: str, label: str,
                             age_min: Optional[int], age_max: Optional[int],
                             age_exact: Optional[int],
                             age_gt: Optional[int] = None,
                             age_lt: Optional[int] = None) -> Tuple[str, str, str]:
    """
    Construit une requête SPARQL avec filtre d'âge sur la classe cible.
    """
    if target_class == ":Medecin":
        select_vars = "?personne ?nom ?age ?specialite ?numeroOrdre"
        extra_optionals = "    OPTIONAL { ?personne :specialite ?specialite }\n    OPTIONAL { ?personne :numeroOrdre ?numeroOrdre }\n"
    elif target_class == ":Patient":
        select_vars = "?personne ?nom ?age ?dossier ?groupeSanguin"
        extra_optionals = "    OPTIONAL { ?personne :numeroDossier ?dossier }\n    OPTIONAL { ?personne :groupeSanguin ?groupeSanguin }\n"
    else:
        select_vars = "?personne ?nom ?age"
        extra_optionals = ""

    if age_exact is not None:
        filter_clause = f"FILTER(?age = {age_exact})"
        intention = f"{label}s d'âge exactement {age_exact} ans"
        explication = f"L'IA a appliqué FILTER(?age = {age_exact}) sur la propriété age."
    elif age_min is not None and age_max is not None:
        filter_clause = f"FILTER(?age >= {age_min} && ?age <= {age_max})"
        intention = f"{label}s entre {age_min} et {age_max} ans"
        explication = f"L'IA a appliqué FILTER(?age >= {age_min} && ?age <= {age_max}) — intervalle d'âge."
    elif age_gt is not None:
        filter_clause = f"FILTER(?age > {age_gt})"
        intention = f"{label}s de plus de {age_gt} ans"
        explication = f"L'IA a appliqué FILTER(?age > {age_gt}) sur la propriété age."
    elif age_lt is not None:
        filter_clause = f"FILTER(?age < {age_lt})"
        intention = f"{label}s de moins de {age_lt} ans"
        explication = f"L'IA a appliqué FILTER(?age < {age_lt}) sur la propriété age."
    else:
        filter_clause = ""
        intention = f"Âge de tous les {label}s"
        explication = "L'IA extrait l'âge sans filtre, trié par ordre croissant."

    sparql = PREFIXES + f"""SELECT {select_vars} WHERE {{
    ?personne rdf:type/rdfs:subClassOf* {target_class} ;
              :age ?age .
    OPTIONAL {{ ?personne :nom ?nom }}
{extra_optionals}    {filter_clause}
}} ORDER BY ?age"""

    return sparql, intention, explication


def _build_generic_property_and_sort_query(q_norm: str, question: str) -> Optional[Tuple[str, str, str]]:
    """
    Moteur sémantique générique (Slot-Filling & Tri dynamique) :
    Extrait automatiquement la classe cible, les filtres sur n'importe quel attribut
    (cin, dossier, groupeSanguin, tel, nom) ainsi que les clauses de tri (trier par ...).
    Évite de devoir coder chaque combinaison manuellement en if/else.
    """
    # 1. Classe cible
    if any(w in q_norm for w in ["patient", "malade", "dossier", "groupesanguin", "groupe sanguin", "sang"]):
        target_class = ":Patient"
        label = "Patient"
        inst_var = "?patient"
    elif any(w in q_norm for w in ["medecin", "docteur", "dr", "cardiologue", "specialiste", "generaliste"]):
        target_class = ":Medecin"
        label = "Médecin"
        inst_var = "?medecin"
    elif "stagiaire" in q_norm:
        target_class = ":Stagiaire"
        label = "Stagiaire"
        inst_var = "?stagiaire"
    else:
        target_class = ":Personne"
        label = "Personne"
        inst_var = "?personne"

    required_triples = []
    filter_clauses = []
    explanations = []

    # --- Filtre CIN (ex: "cin =00345678", "cin 00345678", "numero cin = 00345678")
    m_cin = re.search(r'\b(?:cin|numero\s+cin|n[°o]\s*cin)\b\s*(?:=|est|a|de|:)\s*([0-9a-zA-Z]+)', q_norm)
    if not m_cin:
        m_cin = re.search(r'\b(?:cin|numero\s+cin|n[°o]\s*cin)\b\s+(\d{6,})', q_norm)
    if m_cin:
        val = m_cin.group(1).strip()
        stop_words = ["par", "le", "la", "les", "un", "une", "des", "tous", "toutes", "patient", "patients", "medecin"]
        if val not in stop_words:
            required_triples.append(f"{inst_var} :numeroCIN ?cin .")
            filter_clauses.append(f'STR(?cin) = "{val}" || CONTAINS(LCASE(STR(?cin)), "{val.lower()}")')
            explanations.append(f"CIN = {val}")

    # --- Filtre Dossier (ex: "dossier = PAT-001", "dossier PAT-001", "numero de dossier = PAT-001")
    m_dos = re.search(r'\b(?:dossier|numero\s+dossier|n[°o]\s*dossier|num\s+dossier)\b\s*(?:=|est|a|de|:)\s*([0-9a-zA-Z\-]+)', q_norm)
    if not m_dos:
        m_dos = re.search(r'\b(pat-\d+)\b', q_norm)
    if m_dos:
        val = m_dos.group(1).strip().upper()
        stop_words = ["PAR", "LE", "LA", "LES", "UN", "UNE", "DES", "TOUS", "TOUTES", "PATIENT", "PATIENTS", "MEDECIN", "GROUPESANGUIN", "TEL", "NOM"]
        if val not in stop_words:
            required_triples.append(f"{inst_var} :numeroDossier ?dossier .")
            filter_clauses.append(f'UCASE(STR(?dossier)) = "{val}" || CONTAINS(UCASE(STR(?dossier)), "{val}")')
            explanations.append(f"Dossier = {val}")

    # --- Filtre Groupe Sanguin (ex: "groupe sanguin = A+", "groupe A+", "groupe sanguin O+", "sang A+")
    m_sang = re.search(r'\b(?:groupe\s+sanguin|groupe\s+sang|groupesanguin|sang)\b\s*(?:=|est|a|de|:)?\s*(a\+|a\-|b\+|b\-|ab\+|ab\-|o\+|o\-)', q_norm)
    if not m_sang and any(w in q_norm for w in ["groupe", "sanguin", "sang"]):
        m_sang = re.search(r'\b(a\+|a\-|b\+|b\-|ab\+|ab\-|o\+|o\-)\b', q_norm)
    if m_sang:
        val = m_sang.group(1).strip().upper()
        required_triples.append(f"{inst_var} :groupeSanguin ?groupeSanguin .")
        filter_clauses.append(f'UCASE(STR(?groupeSanguin)) = "{val}"')
        explanations.append(f"Groupe Sanguin = {val}")

    # --- Filtre Téléphone (ex: "tel = +216...", "telephone +216...", "tel 22333444")
    m_tel = re.search(r'\b(?:telephone|tel|num\s+tel|portable)\b\s*(?:=|est|a|de|:)\s*([\+0-9\s]{6,})', q_norm)
    if m_tel:
        val = m_tel.group(1).strip()
        clean = re.sub(r'\s+', '', val)
        required_triples.append(f"{inst_var} :telephone ?tel .")
        filter_clauses.append(f'CONTAINS(REPLACE(STR(?tel), " ", ""), "{clean}")')
        explanations.append(f"Téléphone = {val}")

    # --- Filtre Nom (ex: "nom = Sami", "nomme Sami", "nom : Amina")
    m_nom = re.search(r'\b(?:nom|nomme|nommee)\b\s*(?:=|est|a|de|:)\s*([a-zA-Z]{3,})', q_norm)
    if m_nom:
        val = m_nom.group(1).strip()
        stop_words = ["par", "le", "la", "les", "un", "une", "des", "tous", "toutes", "patient", "patients", "medecin", "dossier"]
        if val not in stop_words:
            required_triples.append(f"{inst_var} :nom ?nom .")
            filter_clauses.append(f'CONTAINS(LCASE(STR(?nom)), "{val.lower()}")')
            explanations.append(f"Nom = {val}")

    # --- Détection du Tri / Triage (ex: "trier par le dossier", "triage par groupeSanguin", "tri par nom", "trier par tel")
    sort_keywords = ["trie", "trier", "triage", "tri", "classer", "classe", "ordonner", "ordre"]
    order_clause = ""
    sort_expl = ""
    if any(k in q_norm for k in sort_keywords):
        desc = any(w in q_norm for w in ["decroissant", "descendant", "desc", "inverse"])
        d = "DESC" if desc else "ASC"
        d_lbl = "décroissant" if desc else "croissant"

        if any(w in q_norm for w in ["dossier", "numerodossier"]):
            order_clause = f"ORDER BY {d}(?dossier)"
            sort_expl = f"trié par numéro de dossier ({d_lbl})"
        elif any(w in q_norm for w in ["groupesanguin", "groupe", "sang", "sanguin"]):
            order_clause = f"ORDER BY {d}(?groupeSanguin)"
            sort_expl = f"trié par groupe sanguin ({d_lbl})"
        elif any(w in q_norm for w in ["telephone", "tel"]):
            order_clause = f"ORDER BY {d}(?tel)"
            sort_expl = f"trié par téléphone ({d_lbl})"
        elif any(w in q_norm for w in ["nom", "patient", "personne", "alphabetique"]):
            order_clause = f"ORDER BY {d}(?nom)"
            sort_expl = f"trié par nom ({d_lbl})"
        elif any(w in q_norm for w in ["age", "ans"]):
            order_clause = f"ORDER BY {d}(?age)"
            sort_expl = f"trié par âge ({d_lbl})"
        elif any(w in q_norm for w in ["cin", "numerocin"]):
            order_clause = f"ORDER BY {d}(?cin)"
            sort_expl = f"trié par CIN ({d_lbl})"

    # Si aucun filtre ni tri détecté, on retourne None pour laisser les autres règles s'appliquer
    if not filter_clauses and not order_clause:
        return None

    # Construction dynamique de la requête SPARQL selon la classe cible
    if target_class == ":Patient":
        select_clause = f"SELECT DISTINCT {inst_var} ?nom ?age ?cin ?dossier ?groupeSanguin ?tel WHERE {{"
        optionals = f"""    {inst_var} rdf:type/rdfs:subClassOf* :Patient .
    OPTIONAL {{ {inst_var} :nom ?nom }}
    OPTIONAL {{ {inst_var} :age ?age }}
    OPTIONAL {{ {inst_var} :numeroCIN ?cin }}
    OPTIONAL {{ {inst_var} :numeroDossier ?dossier }}
    OPTIONAL {{ {inst_var} :groupeSanguin ?groupeSanguin }}
    OPTIONAL {{ {inst_var} :telephone ?tel }}"""
    elif target_class == ":Medecin":
        select_clause = f"SELECT DISTINCT {inst_var} ?nom ?age ?cin ?specialite ?numeroOrdre ?tel WHERE {{"
        optionals = f"""    {inst_var} rdf:type/rdfs:subClassOf* :Medecin .
    OPTIONAL {{ {inst_var} :nom ?nom }}
    OPTIONAL {{ {inst_var} :age ?age }}
    OPTIONAL {{ {inst_var} :numeroCIN ?cin }}
    OPTIONAL {{ {inst_var} :specialite ?specialite }}
    OPTIONAL {{ {inst_var} :numeroOrdre ?numeroOrdre }}
    OPTIONAL {{ {inst_var} :telephone ?tel }}"""
    elif target_class == ":Stagiaire":
        select_clause = f"SELECT DISTINCT {inst_var} ?nom ?age ?cin ?tel WHERE {{"
        optionals = f"""    {inst_var} rdf:type :Stagiaire .
    OPTIONAL {{ {inst_var} :nom ?nom }}
    OPTIONAL {{ {inst_var} :age ?age }}
    OPTIONAL {{ {inst_var} :numeroCIN ?cin }}
    OPTIONAL {{ {inst_var} :telephone ?tel }}"""
    else:
        select_clause = f"SELECT DISTINCT {inst_var} ?type ?nom ?age ?cin ?dossier ?groupeSanguin ?tel WHERE {{"
        optionals = f"""    {inst_var} rdf:type ?type .
    ?type rdfs:subClassOf* :Personne .
    OPTIONAL {{ {inst_var} :nom ?nom }}
    OPTIONAL {{ {inst_var} :age ?age }}
    OPTIONAL {{ {inst_var} :numeroCIN ?cin }}
    OPTIONAL {{ {inst_var} :numeroDossier ?dossier }}
    OPTIONAL {{ {inst_var} :groupeSanguin ?groupeSanguin }}
    OPTIONAL {{ {inst_var} :telephone ?tel }}"""

    body_lines = [optionals]
    for req in required_triples:
        body_lines.append(f"    {req}")
    for flt in filter_clauses:
        body_lines.append(f"    FILTER({flt})")

    sparql_body = "\n".join(body_lines)
    sparql = PREFIXES + f"""{select_clause}
{sparql_body}
}} {order_clause}""".strip()

    desc_filters = " avec " + " et ".join(explanations) if explanations else ""
    desc_sort = f" ({sort_expl})" if sort_expl else ""
    intention = f"Recherche de {label}s{desc_filters}{desc_sort}".strip()
    explication = f"L'IA a extrait dynamiquement les critères : {', '.join(explanations) if explanations else 'aucun filtre'} et le tri {sort_expl or 'par défaut'}."

    return sparql, intention, explication


# ---------------------------------------------------------------------------
# Classe principale
# ---------------------------------------------------------------------------

class IAService:
    def __init__(self, rdflib_service=None):
        self.rdflib_service = rdflib_service

    def translate_question_to_sparql(self, question: str) -> Tuple[str, str, str]:
        """
        Analyse la question utilisateur en langage naturel et génère la requête SPARQL.
        Retourne : (sparql_query, intention_detectee, explication_ia)

        ORDRE DE PRIORITÉ :
          0. Âge (en premier pour éviter la capture par "patient")
          1. Urgences / Service
          2. Cardiologue
          3. Spécialiste
          4. Généraliste
          5. Médecin générique
          6. Enfant / Adulte
          7. Relations de soins
          8. Relations de connaissance
          9. Symptômes
         10. Dossier / Groupe sanguin
         11. Stagiaire
         12. Individus spécifiques (Fatima, Sami, Ahmed, Karim, Amina, Ali)
         13. Patients en général (sans filtre âge)
         14. Hiérarchie
         15. Défaut
        """
        q = question.lower().strip()
        # Normalisation des accents courants pour simplifier la détection
        q_norm = (q.replace("â", "a").replace("à", "a").replace("é", "e")
                   .replace("è", "e").replace("ê", "e").replace("î", "i")
                   .replace("ô", "o").replace("û", "u").replace("ù", "u"))

        # ============================================================
        # PRIORITÉ -1 : Questions relatives à la Classe Maladie,
        #               ses individus, Object Properties et Data Properties
        #               (basées sur ontologie_medicale (1).ttl de Protégé)
        # ============================================================

        # 1. Symptômes d'une maladie (ex: "quels sont les symptomes de la grippe / angine / diabete ?")
        if any(w in q_norm for w in ["symptome", "symptomes", "signe", "manifestation"]) and any(w in q_norm for w in ["grippe", "angine", "diabete", "hypertension", "ulcere"]):
            m_target = "Grippe" if "grippe" in q_norm else ("Angine" if "angine" in q_norm else ("Diabete" if "diabete" in q_norm else ("Hypertension" if "hypertension" in q_norm else "Ulcere_Exemple")))
            sparql = PREFIXES + f"""SELECT ?symptome ?nomSymptome WHERE {{
    :{m_target} :aPourSymptome ?s .
    OPTIONAL {{ ?s rdfs:label ?nomSymptome }}
    BIND(STRAFTER(STR(?s), "#") AS ?symptome)
}}"""
            return sparql, f"Symptômes de {m_target} (Ontologie Protégé)", \
                   f"L'IA extrait les individus reliés à :{m_target} via la propriété d'objet :aPourSymptome."

        # 2. Quels symptômes pour quelle maladie (général)
        if any(w in q_norm for w in ["symptome", "symptomes"]) and any(w in q_norm for w in ["maladie", "maladies", "provoque", "cause"]):
            sparql = PREFIXES + """SELECT ?maladie ?symptome WHERE {
    ?m :aPourSymptome ?s .
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
    BIND(STRAFTER(STR(?s), "#") AS ?symptome)
} ORDER BY ?maladie"""
            return sparql, "Association Maladie - Symptôme (aPourSymptome)", \
                   "L'IA extrait les couples (Maladie, Symptôme) via la relation :aPourSymptome de l'ontologie."

        # 3. Contre-indications (ex: "quels medicaments sont contre-indiques pour l'ulcere ?")
        if any(w in q_norm for w in ["contre indique", "contre-indique", "contre indication", "interdit"]) or ("contre" in q_norm and any(w in q_norm for w in ["ulcere", "grippe", "angine", "diabete", "hypertension"])):
            m_target = "Ulcere_Exemple" if "ulcere" in q_norm else ("Grippe" if "grippe" in q_norm else ("Angine" if "angine" in q_norm else ("Diabete" if "diabete" in q_norm else "Hypertension")))
            sparql = PREFIXES + f"""SELECT ?medicament ?maladie WHERE {{
    ?med :estContreIndiquePour ?m .
    BIND(STRAFTER(STR(?med), "#") AS ?medicament)
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
}}"""
            return sparql, "Médicaments contre-indiqués (Relation estContreIndiquePour)", \
                   "L'IA recherche les contre-indications médicamenteuses via la propriété :estContreIndiquePour."

        # 4a. Médicaments associés à la maladie d'un patient (ex: "quels médicaments sont associés à la maladie d'Ahmed / Sami ?")
        patient_names = ["ahmed", "sami", "sara", "omar", "leila", "youssef"]
        matched_patient = next((p for p in patient_names if p in q_norm), None)

        if matched_patient and any(w in q_norm for w in ["medicament", "medicaments", "traitement", "associe", "associes", "traite"]) and any(w in q_norm for w in ["maladie", "souffre", "malade", "trait"]):
            p_filter = f'REGEX(STR(?p), "{matched_patient}", "i") || REGEX(STR(?nomPatient), "{matched_patient}", "i")'
            sparql = PREFIXES + f"""SELECT DISTINCT ?patient ?nomPatient ?maladie ?medicament ?nomMedicament WHERE {{
    ?p :souffreDe ?m .
    OPTIONAL {{ ?p :nom ?nomPatient }}
    {{
        ?m :estTraiteePar ?med .
    }} UNION {{
        ?med :traite ?m .
    }}
    OPTIONAL {{ ?med rdfs:label ?nomMedicament }}
    BIND(STRAFTER(STR(?p), "#") AS ?patient)
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
    BIND(STRAFTER(STR(?med), "#") AS ?medicament)
    FILTER({p_filter})
}}"""
            return sparql, f"Médicaments associés à la maladie de {matched_patient.capitalize()} (:souffreDe -> :estTraiteePar)", \
                   f"L'IA recherche les maladies dont souffre {matched_patient.capitalize()} et extrait les médicaments qui les traitent."

        # 4b. Traitements / Médicaments associés à une maladie (ex: "quels médicaments sont associés à la grippe / au diabète ?")
        disease_map = {
            "grippe": "Grippe", "angine": "Angine", "diabete": "Diabete",
            "hypertension": "Hypertension", "ulcere": "Ulcere_gastrique",
            "asthme": "Asthme", "bronchite": "Bronchite", "arthrite": "Arthrite",
            "anemie": "Anemie", "paludisme": "Paludisme", "gastrite": "Gastrite", "migraine": "Migraine"
        }
        matched_disease = next((k for k in disease_map if k in q_norm), None)

        if any(w in q_norm for w in ["trait", "traite", "medicament", "medicaments", "soigne", "remede", "associe", "associes"]) and matched_disease:
            m_target = disease_map[matched_disease]
            sparql = PREFIXES + f"""SELECT DISTINCT ?medicament ?nomMedicament WHERE {{
    {{
        :{m_target} :estTraiteePar ?med .
        BIND(STRAFTER(STR(?med), "#") AS ?medicament)
    }} UNION {{
        ?med :traite :{m_target} .
        BIND(STRAFTER(STR(?med), "#") AS ?medicament)
    }}
    OPTIONAL {{ ?med rdfs:label ?nomMedicament }}
}}"""
            return sparql, f"Médicaments associés à {m_target} (Object Property estTraiteePar / traite)", \
                   f"L'IA recherche les médicaments associés à :{m_target} dans l'ontologie médicale."

        # 5a. De quelle maladie souffre CHAQUE patient ? / Quelles sont les maladies de chaque patient ?
        if any(w in q_norm for w in ["chaque patient", "tous les patients", "chacun des patients", "de chaque patient"]):
            sparql = PREFIXES + """SELECT DISTINCT ?patient ?nomPatient ?maladie ?typeMaladie WHERE {
    ?p :souffreDe ?m .
    OPTIONAL { ?p :nom ?nomPatient }
    OPTIONAL { ?m rdf:type ?type . FILTER(?type != owl:NamedIndividual && ?type != :Maladie) }
    BIND(STRAFTER(STR(?p), "#") AS ?patient)
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
    BIND(STRAFTER(STR(?type), "#") AS ?typeMaladie)
} ORDER BY ?nomPatient ?patient"""
            return sparql, "Maladie(s) de chaque patient (Relation :souffreDe)", \
                   "L'IA extrait pour chaque patient la liste des maladies dont il souffre via :souffreDe."

        # 5b. De quelle maladie souffre un patient quelconque (Ahmed, Sami, Leila, Sara, Omar, Youssef, etc.) ?
        if matched_patient and any(w in q_norm for w in ["maladie", "souffre", "atteint", "malade"]):
            p_filter = f'REGEX(STR(?p), "{matched_patient}", "i") || REGEX(STR(?nomPatient), "{matched_patient}", "i")'
            sparql = PREFIXES + f"""SELECT DISTINCT ?patient ?nomPatient ?maladie ?typeMaladie WHERE {{
    ?p :souffreDe ?m .
    OPTIONAL {{ ?p :nom ?nomPatient }}
    OPTIONAL {{ ?m rdf:type ?type . FILTER(?type != owl:NamedIndividual && ?type != :Maladie) }}
    BIND(STRAFTER(STR(?p), "#") AS ?patient)
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
    BIND(STRAFTER(STR(?type), "#") AS ?typeMaladie)
    FILTER({p_filter})
}}"""
            return sparql, f"Maladie de {matched_patient.capitalize()} (Relation :souffreDe)", \
                   f"L'IA extrait la ou les maladies dont souffre {matched_patient.capitalize()} via la propriété d'objet :souffreDe."

        # 6. Qui a / souffre de quelle maladie ? (ex: "quels patients ont le diabete ?", "qui a la grippe ?", "qui souffre de la grippe ?")
        has_disease_kw = any(w in q_norm for w in ["diabete", "grippe", "angine", "hypertension", "ulcere", "asthme", "bronchite", "arthrite", "anemie", "paludisme", "gastrite", "migraine", "maladie"])
        has_patient_kw = any(w in q_norm for w in ["patient", "patients", "qui", "personne", "gens"])
        has_have_kw = any(w in q_norm for w in ["souffre", "atteint", "touche", " ont", " a le", " a la", " a l ", " ont le", " ont la", " ont l "])

        if (has_patient_kw and has_disease_kw and (has_have_kw or "maladie" in q_norm)) or any(w in q_norm for w in ["souffre", "atteint"]):
            m_clause = ""
            label_m = "toutes maladies"
            if "diabete" in q_norm:
                m_clause = "FILTER(?m = :Diabete)"
                label_m = "le diabète"
            elif "grippe" in q_norm:
                m_clause = "FILTER(?m = :Grippe)"
                label_m = "la grippe"
            elif "angine" in q_norm:
                m_clause = "FILTER(?m = :Angine)"
                label_m = "l'angine"
            elif "hypertension" in q_norm:
                m_clause = "FILTER(?m = :Hypertension)"
                label_m = "l'hypertension"
            elif "ulcere" in q_norm:
                m_clause = "FILTER(?m = :Ulcere_gastrique || ?m = :Ulcere_Exemple)"
                label_m = "l'ulcère"
            elif "asthme" in q_norm:
                m_clause = "FILTER(?m = :Asthme)"
                label_m = "l'asthme"
            elif "arthrite" in q_norm:
                m_clause = "FILTER(?m = :Arthrite)"
                label_m = "l'arthrite"
            elif "anemie" in q_norm:
                m_clause = "FILTER(?m = :Anemie)"
                label_m = "l'anémie"
            elif "paludisme" in q_norm:
                m_clause = "FILTER(?m = :Paludisme)"
                label_m = "le paludisme"
            elif "gastrite" in q_norm:
                m_clause = "FILTER(?m = :Gastrite)"
                label_m = "la gastrite"
            elif "migraine" in q_norm:
                m_clause = "FILTER(?m = :Migraine)"
                label_m = "la migraine"

            sparql = PREFIXES + f"""SELECT DISTINCT ?patient ?nom ?maladie WHERE {{
    {{
        ?p :souffreDe ?m .
    }} UNION {{
        ?m :touche ?p .
    }}
    OPTIONAL {{ ?p :nom ?nom }}
    BIND(STRAFTER(STR(?p), "#") AS ?patient)
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
    {m_clause}
}}"""
            return sparql, f"Patients atteints par {label_m} (Relation souffreDe / touche)", \
                   f"L'IA interroge les patients enregistrés dans l'ontologie via les relations :souffreDe et :touche pour {label_m}."

        # 7. Sous-classes de maladies (ex: "maladies chroniques", "maladies infectieuses", "maladies digestives")
        if any(w in q_norm for w in ["chronique", "chroniques"]) and any(w in q_norm for w in ["maladie", "maladies", "liste"]):
            sparql = PREFIXES + """SELECT ?maladie ?label ?description ?gravite ?contagieuse WHERE {
    ?m rdf:type/rdfs:subClassOf* :MaladieChronique .
    FILTER(?m != owl:NamedIndividual && ?m != :MaladieChronique && ?m != :Type && ?m != :Maladie)
    OPTIONAL { ?m rdfs:label ?label }
    OPTIONAL { ?m :description ?description }
    OPTIONAL { ?m :gravite ?gravite }
    OPTIONAL { ?m :estContagieuse ?contagieuse }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
}"""
            return sparql, "Maladies Chroniques (Sous-classe de Maladie)", \
                   "L'IA extrait les individus de la sous-classe :MaladieChronique et leurs propriétés."

        if any(w in q_norm for w in ["infectieuse", "infectieuses", "infection"]) and any(w in q_norm for w in ["maladie", "maladies", "liste"]):
            sparql = PREFIXES + """SELECT ?maladie ?label ?symptome ?traitement WHERE {
    ?m rdf:type/rdfs:subClassOf* :MaladieInfectieuse .
    FILTER(?m != owl:NamedIndividual && ?m != :MaladieInfectieuse && ?m != :Type && ?m != :Maladie)
    OPTIONAL { ?m rdfs:label ?label }
    OPTIONAL { ?m :aPourSymptome ?s . BIND(STRAFTER(STR(?s), "#") AS ?symptome) }
    OPTIONAL { ?m :estTraiteePar ?t . BIND(STRAFTER(STR(?t), "#") AS ?traitement) }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
}"""
            return sparql, "Maladies Infectieuses (Sous-classe de Maladie)", \
                   "L'IA extrait les individus de la classe :MaladieInfectieuse (Grippe, Angine) avec symptômes et traitements."

        if any(w in q_norm for w in ["digestive", "digestives", "digestif", "estomac"]) and any(w in q_norm for w in ["maladie", "maladies"]):
            sparql = PREFIXES + """SELECT ?maladie ?label ?symptome WHERE {
    ?m rdf:type/rdfs:subClassOf* :MaladieDigestive .
    FILTER(?m != owl:NamedIndividual && ?m != :MaladieDigestive && ?m != :Type && ?m != :Maladie)
    OPTIONAL { ?m rdfs:label ?label }
    OPTIONAL { ?m :aPourSymptome ?s . BIND(STRAFTER(STR(?s), "#") AS ?symptome) }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
}"""
            return sparql, "Maladies Digestives (Sous-classe de Maladie)", \
                   "L'IA extrait les individus de :MaladieDigestive (ex: Ulcere_Exemple) depuis l'ontologie."

        # 8. Data Properties de Maladie : description, gravite, estContagieuse (ex: "c'est quoi le diabete ?", "gravite du diabete", "maladies contagieuses")
        if any(w in q_norm for w in ["c'est quoi", "qu'est ce que", "definition", "definir", "description"]) and any(w in q_norm for w in ["diabete", "grippe", "angine", "hypertension", "ulcere"]):
            m_target = "Diabete" if "diabete" in q_norm else ("Grippe" if "grippe" in q_norm else ("Angine" if "angine" in q_norm else ("Hypertension" if "hypertension" in q_norm else "Ulcere_Exemple")))
            sparql = PREFIXES + f"""SELECT ?propriete ?valeur WHERE {{
    :{m_target} ?p ?valeur .
    FILTER(?p IN (:description, :gravite, :estContagieuse, rdfs:comment, rdfs:label, :aPourSymptome, :estTraiteePar))
    BIND(STRAFTER(STR(?p), "#") AS ?propriete)
}}"""
            return sparql, f"Description et propriétés de {m_target} (Data & Object Properties)", \
                   f"L'IA extrait les propriétés de données (description, gravite, estContagieuse) et relations de :{m_target}."

        if any(w in q_norm for w in ["contagieuse", "contagieux", "contagieuses"]):
            sparql = PREFIXES + """SELECT DISTINCT ?maladie ?label ?estContagieuse WHERE {
    ?m rdf:type/rdfs:subClassOf* :Maladie .
    ?m :estContagieuse ?estContagieuse .
    FILTER(?estContagieuse = true)
    OPTIONAL { ?m rdfs:label ?label }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
}"""
            return sparql, "Maladies contagieuses (Data Property estContagieuse = true)", \
                   "L'IA filtre les maladies contagieuses via FILTER(:estContagieuse = true)."

        if any(w in q_norm for w in ["gravite", "grave", "severite"]):
            sparql = PREFIXES + """SELECT ?maladie ?label ?gravite WHERE {
    ?m rdf:type/rdfs:subClassOf* :Maladie .
    ?m :gravite ?gravite .
    OPTIONAL { ?m rdfs:label ?label }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
}"""
            return sparql, "Gravité des maladies (Data Property gravite)", \
                   "L'IA extrait la gravité des maladies via la propriété de données :gravite."

        # 9. Individus spécifiques de Maladie (ex: "fiche diabete", "donnees sur la grippe")
        for m_name in ["diabete", "grippe", "angine", "hypertension", "ulcere"]:
            if m_name in q_norm and not any(w in q_norm for w in ["medecin", "patient", "soigne", "age", "stagiaire"]):
                m_target = "Diabete" if m_name == "diabete" else ("Grippe" if m_name == "grippe" else ("Angine" if m_name == "angine" else ("Hypertension" if m_name == "hypertension" else "Ulcere_Exemple")))
                sparql = PREFIXES + f"""SELECT ?propriete ?valeur WHERE {{
    :{m_target} ?p ?valeur .
    FILTER(?p != rdf:type)
    BIND(STRAFTER(STR(?p), "#") AS ?propriete)
}}"""
                return sparql, f"Fiche complète de la maladie {m_target}", \
                       f"L'IA extrait toutes les assertions et propriétés de l'individu :{m_target} dans l'ontologie médicale Protégé."

    # 10. Liste de toutes les maladies de la classe Maladie
        if any(w in q_norm for w in ["toutes les maladies", "liste des maladies", "quelles sont les maladies", "les maladies"]):
            sparql = PREFIXES + """SELECT DISTINCT ?maladie ?type ?label ?description ?gravite WHERE {
    ?m rdf:type owl:NamedIndividual .
    ?m rdf:type ?t .
    ?t rdfs:subClassOf* :Maladie .
    FILTER(?t NOT IN (:Maladie, :Symptome, :SymptomeGeneral, :SymptomeDigestif, :SymptomeRespiratoire, :Type))
    FILTER(?m NOT IN (:Grippe_Sami, :Ulcere_Exemple))
    OPTIONAL { ?m rdfs:label ?label }
    OPTIONAL { ?m :description ?description }
    OPTIONAL { ?m :gravite ?gravite }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
    BIND(STRAFTER(STR(?t), "#") AS ?type)
} ORDER BY ?maladie"""
            return sparql, "Inventaire des individus de la classe Maladie", \
                   "L'IA interroge les individus de la classe Maladie et ses sous-classes (MaladieInfectieuse, MaladieChronique, MaladieDigestive)."

        # ============================================================
        # PRIORITÉ 0 : Filtres d'âge
        # ============================================================
        # Utilisation de regex \b pour éviter faux positifs (ex: "triage", "stagiaire", "dans")
        has_age = bool(re.search(r'\b(age|ages|agee|agees|ans|annee|annees)\b', q_norm))
        is_sort_request = bool(re.search(r'\b(triage|tri|trie|trier|classer|classe|ordonner|ordre)\b', q_norm))
        if has_age and not is_sort_request:

            target_class, label = _detect_target_class(q_norm)
            numbers = _extract_numbers(q_norm)

            # --- Intervalle : "entre X et Y", "de X à Y", "de X a Y",
            #                  "X à Y ans", "intervalle de X à Y"
            m_interval = (
                re.search(r'entre\s+(\d+)\s+et\s+(\d+)', q_norm)
                or re.search(r'de\s+(\d+)\s+a\s+(\d+)', q_norm)
                or re.search(r'(\d+)\s+a\s+(\d+)\s+ans', q_norm)
                or re.search(r'intervalle.{0,20}?(\d+).{0,10}?(\d+)', q_norm)
            )
            if m_interval:
                age_min = int(m_interval.group(1))
                age_max = int(m_interval.group(2))
                return _build_age_filter_query(target_class, label,
                                               age_min=age_min, age_max=age_max,
                                               age_exact=None)

            # --- Supérieur : "> X", "plus de X", "superieur a X", ">= X"
            m_gte = re.search(r'>=\s*(\d+)', q_norm)
            m_gt = (re.search(r'>\s*(\d+)', q_norm)
                    or re.search(r'plus\s+de\s+(\d+)', q_norm)
                    or re.search(r'sup[ée]rieur[s]?\s+[a]\s+(\d+)', q_norm))

            if m_gte:
                limit = int(m_gte.group(1))
                return _build_age_filter_query(target_class, label,
                                               age_min=limit, age_max=None,
                                               age_exact=None, age_gt=None,
                                               age_lt=None)
            if m_gt:
                limit = int(m_gt.group(1))
                return _build_age_filter_query(target_class, label,
                                               age_min=None, age_max=None,
                                               age_exact=None, age_gt=limit)

            # --- Inférieur : "< X", "moins de X", "inferieur a X", "<= X"
            m_lte = re.search(r'<=\s*(\d+)', q_norm)
            m_lt = (re.search(r'<\s*(\d+)', q_norm)
                    or re.search(r'moins\s+de\s+(\d+)', q_norm)
                    or re.search(r'inf[ée]rieur[s]?\s+[a]\s+(\d+)', q_norm))

            if m_lte:
                limit = int(m_lte.group(1))
                return _build_age_filter_query(target_class, label,
                                               age_min=None, age_max=limit,
                                               age_exact=None)
            if m_lt:
                limit = int(m_lt.group(1))
                return _build_age_filter_query(target_class, label,
                                               age_min=None, age_max=None,
                                               age_exact=None, age_lt=limit)

            # --- Exact : "= X", "=X", ": X", "ayant X ans", "age X", "de X ans"
            m_exact = (
                re.search(r'[=:]\s*(\d+)', q_norm)
                or re.search(r'ayant\s+(\d+)\s+ans', q_norm)
                or re.search(r'age\s+(\d+)', q_norm)
                or re.search(r'agee?\s+de\s+(\d+)', q_norm)
                or re.search(r'de\s+(\d+)\s+ans', q_norm)
            )
            if m_exact:
                age_val = int(m_exact.group(1))
                return _build_age_filter_query(target_class, label,
                                               age_min=None, age_max=None,
                                               age_exact=age_val)

            # --- Fallback : un seul nombre trouvé → traité comme exact
            if len(numbers) == 1:
                age_val = int(numbers[0])
                return _build_age_filter_query(target_class, label,
                                               age_min=None, age_max=None,
                                               age_exact=age_val)

            # --- Aucun nombre → liste tous les âges triés
            return _build_age_filter_query(target_class, label,
                                           age_min=None, age_max=None,
                                           age_exact=None)


        # ============================================================
        # PRIORITÉ 1 : Individus spécifiques nommés (priorité haute
        #              pour éviter capture par blocs génériques)
        # ============================================================
        # Fatima (avant "medecin" générique)
        if "fatima" in q_norm:
            sparql = PREFIXES + """SELECT ?propriete ?valeur WHERE {
    :Dr_Fatima ?p ?valeur .
    BIND(STRAFTER(STR(?p), "#") AS ?propriete)
    FILTER(?p != rdf:type)
}"""
            return sparql, "Fiche complète du Dr Fatima", \
                   "L'IA extrait l'ensemble des assertions associées à l'individu Dr_Fatima."

        if "sami" in q_norm and not any(w in q_norm for w in ["soigne", "soin", "docteur", "medecin", "affecte", "traite"]):
            sparql = PREFIXES + """SELECT ?propriete ?valeur WHERE {
    :Sami ?p ?valeur .
    BIND(STRAFTER(STR(?p), "#") AS ?propriete)
    FILTER(?p != rdf:type)
}"""
            return sparql, "Fiche complète de Sami", \
                   "L'IA extrait l'ensemble des assertions associées à l'individu Sami."

        if "ahmed" in q_norm and not any(w in q_norm for w in ["soigne", "soin"]):
            sparql = PREFIXES + """SELECT ?propriete ?valeur WHERE {
    :Dr_Ahmed ?p ?valeur .
    BIND(STRAFTER(STR(?p), "#") AS ?propriete)
    FILTER(?p != rdf:type)
}"""
            return sparql, "Fiche complète du Dr Ahmed", \
                   "L'IA extrait l'ensemble des assertions associées à l'individu Dr_Ahmed."

        if "karim" in q_norm:
            sparql = PREFIXES + """SELECT ?propriete ?valeur WHERE {
    :Dr_Karim ?p ?valeur .
    BIND(STRAFTER(STR(?p), "#") AS ?propriete)
    FILTER(?p != rdf:type)
}"""
            return sparql, "Fiche complète du Dr Karim", \
                   "L'IA extrait l'ensemble des assertions associées à l'individu Dr_Karim."

        if "amina" in q_norm:
            sparql = PREFIXES + """SELECT ?propriete ?valeur WHERE {
    :Amina ?p ?valeur .
    BIND(STRAFTER(STR(?p), "#") AS ?propriete)
    FILTER(?p != rdf:type)
}"""
            return sparql, "Fiche complète d'Amina", \
                   "L'IA extrait l'ensemble des assertions associées à l'individu Amina."

        if re.search(r'\bali\b', q_norm):
            sparql = PREFIXES + """SELECT ?propriete ?valeur WHERE {
    :Ali_Stagiaire ?p ?valeur .
    BIND(STRAFTER(STR(?p), "#") AS ?propriete)
    FILTER(?p != rdf:type)
}"""
            return sparql, "Fiche complète d'Ali (Stagiaire)", \
                   "L'IA extrait l'ensemble des assertions associées à l'individu Ali_Stagiaire."

        # ============================================================
        # PRIORITÉ 1.5 : Moteur Sémantique Générique (Filtres & Tri)
        # Permet de filtrer par CIN, Dossier, Groupe Sanguin, Tel, Nom,
        # et de trier dynamiquement (ORDER BY) sans coder chaque cas.
        # ============================================================
        generic_res = _build_generic_property_and_sort_query(q_norm, question)
        if generic_res is not None:
            return generic_res

        # ============================================================
        # PRIORITÉ 2 : Urgences / Service
        # ============================================================
        if any(w in q_norm for w in ["urgence", "urgences", "service urgence"]):
            sparql = PREFIXES + """SELECT DISTINCT ?personne ?nom ?age WHERE {
    ?personne :appartientA :Service_Urgences .
    OPTIONAL { ?personne :nom ?nom }
    OPTIONAL { ?personne :age ?age }
}"""
            return sparql, "Personnes rattachées au Service des Urgences", \
                   "L'IA a filtré les individus via la propriété appartientA et l'individu Service_Urgences."

        # ============================================================
        # PRIORITÉ 2 : Cardiologue
        # ============================================================
        if "cardiologue" in q_norm or "cardiologie" in q_norm:
            sparql = PREFIXES + """SELECT ?medecin ?nom ?age ?specialite ?tel WHERE {
    { ?medecin rdf:type :Cardiologue . }
    UNION
    {
        ?medecin :specialite ?specialite .
        FILTER(CONTAINS(LCASE(STR(?specialite)), "cardio"))
    }
    OPTIONAL { ?medecin :nom ?nom }
    OPTIONAL { ?medecin :age ?age }
    OPTIONAL { ?medecin :specialite ?specialite }
    OPTIONAL { ?medecin :telephone ?tel }
}"""
            return sparql, "Recherche des Cardiologues", \
                   "L'IA a identifié la recherche des médecins avec la spécialité Cardiologie ou de type Cardiologue."

        # ============================================================
        # PRIORITÉ 3 : Spécialiste
        # ============================================================
        if "specialiste" in q_norm or "spécialiste" in q:
            sparql = PREFIXES + """SELECT ?medecin ?nom ?age ?specialite ?numeroOrdre WHERE {
    ?medecin rdf:type/rdfs:subClassOf* :MedecinSpecialiste .
    OPTIONAL { ?medecin :nom ?nom }
    OPTIONAL { ?medecin :age ?age }
    OPTIONAL { ?medecin :specialite ?specialite }
    OPTIONAL { ?medecin :numeroOrdre ?numeroOrdre }
}"""
            return sparql, "Recherche des Médecins Spécialistes", \
                   "L'IA a extrait la classe MedecinSpecialiste avec ses propriétés spécifiques (specialite, numeroOrdre)."

        # ============================================================
        # PRIORITÉ 4 : Généraliste
        # ============================================================
        if "generaliste" in q_norm or "généraliste" in q:
            sparql = PREFIXES + """SELECT ?medecin ?nom ?age ?tel WHERE {
    ?medecin rdf:type :MedecinGeneraliste .
    OPTIONAL { ?medecin :nom ?nom }
    OPTIONAL { ?medecin :age ?age }
    OPTIONAL { ?medecin :telephone ?tel }
}"""
            return sparql, "Recherche des Médecins Généralistes", \
                   "L'IA a extrait la sous-classe MedecinGeneraliste."

        # ============================================================
        # PRIORITÉ 5 : Médecin générique
        # ============================================================
        if (any(w in q_norm for w in ["medecin", "médecin", "docteur"])
                and not any(w in q_norm for w in ["soigne", "patient", "connait", "connait"])):
            sparql = PREFIXES + """SELECT ?medecin ?nom ?age ?specialite ?numeroOrdre ?telephone WHERE {
    ?medecin rdf:type/rdfs:subClassOf* :Medecin .
    OPTIONAL { ?medecin :nom ?nom }
    OPTIONAL { ?medecin :age ?age }
    OPTIONAL { ?medecin :specialite ?specialite }
    OPTIONAL { ?medecin :numeroOrdre ?numeroOrdre }
    OPTIONAL { ?medecin :telephone ?telephone }
}"""
            return sparql, "Recherche de tous les Médecins", \
                   "L'IA a sélectionné toutes les instances dont le rdf:type dérive de la classe Medecin."

        # ============================================================
        # PRIORITÉ 6 : Enfants / Adultes
        # ============================================================
        if "enfant" in q_norm:
            sparql = PREFIXES + """SELECT ?patient ?nom ?age ?dossier ?groupeSanguin WHERE {
    ?patient rdf:type :PatientEnfant .
    OPTIONAL { ?patient :nom ?nom }
    OPTIONAL { ?patient :age ?age }
    OPTIONAL { ?patient :numeroDossier ?dossier }
    OPTIONAL { ?patient :groupeSanguin ?groupeSanguin }
}"""
            return sparql, "Recherche des Patients Enfants", \
                   "L'IA a ciblé la sous-classe PatientEnfant (disjointe de PatientAdulte)."

        if "adulte" in q_norm:
            sparql = PREFIXES + """SELECT ?patient ?nom ?age ?dossier ?groupeSanguin ?cin WHERE {
    ?patient rdf:type :PatientAdulte .
    OPTIONAL { ?patient :nom ?nom }
    OPTIONAL { ?patient :age ?age }
    OPTIONAL { ?patient :numeroDossier ?dossier }
    OPTIONAL { ?patient :groupeSanguin ?groupeSanguin }
    OPTIONAL { ?patient :numeroCIN ?cin }
}"""
            return sparql, "Recherche des Patients Adultes", \
                   "L'IA a ciblé la sous-classe PatientAdulte."

        # ============================================================
        # PRIORITÉ 7 : Relations de soins
        # ============================================================
        if "qui soigne sami" in q_norm or ("soigne" in q_norm and "sami" in q_norm) or ("docteur" in q_norm and "sami" in q_norm) or ("medecin" in q_norm and "sami" in q_norm):
            sparql = PREFIXES + """SELECT DISTINCT ?docteur ?nom ?specialite ?telephone WHERE {
    {
        ?docteur :soigne :Sami .
    } UNION {
        :Sami :estSoignePar ?docteur .
    }
    OPTIONAL { ?docteur :nom ?nom }
    OPTIONAL { ?docteur :specialite ?specialite }
    OPTIONAL { ?docteur :telephone ?telephone }
}"""
            return sparql, "Médecin traitant affecté à Sami", \
                   "L'IA extrait le docteur affecté au suivi du patient Sami via les propriétés soigne et estSoignePar."

        if any(w in q_norm for w in ["qui soigne", "soigne", "soin", "soigne par", "est soigne"]):
            if "ahmed" in q_norm:
                sparql = PREFIXES + """SELECT ?medecin ?nomMedecin ?patient ?nomPatient WHERE {
    {
        :Dr_Ahmed :soigne ?patient .
        BIND(:Dr_Ahmed AS ?medecin)
    } UNION {
        ?patient :estSoignePar :Dr_Ahmed .
        BIND(:Dr_Ahmed AS ?medecin)
    }
    OPTIONAL { ?medecin :nom ?nomMedecin }
    OPTIONAL { ?patient :nom ?nomPatient }
}"""
                return sparql, "Recherche des patients soignés par Dr Ahmed", \
                       "L'IA interroge les triplets liés à l'individu Dr_Ahmed via soigne et estSoignePar."
            else:
                sparql = PREFIXES + """SELECT ?medecin ?nomMedecin ?patient ?nomPatient WHERE {
    ?medecin :soigne ?patient .
    OPTIONAL { ?medecin :nom ?nomMedecin }
    OPTIONAL { ?patient :nom ?nomPatient }
}"""
                return sparql, "Cartographie des soins (Médecin -> Patient)", \
                       "L'IA utilise la propriété d'objet soigne liant Medecin à Patient."

        # ============================================================
        # PRIORITÉ 8 : Relations de connaissance (propriété symétrique)
        # ============================================================
        if any(w in q_norm for w in ["connait", "connait", "relation", "collegue", "collègue"]):
            sparql = PREFIXES + """SELECT ?p1 ?nom1 ?p2 ?nom2 WHERE {
    ?p1 :connait ?p2 .
    OPTIONAL { ?p1 :nom ?nom1 }
    OPTIONAL { ?p2 :nom ?nom2 }
}"""
            return sparql, "Recherche des liens de connaissance (SymmetricProperty)", \
                   "L'IA utilise la propriété symétrique connait liant deux instances de Personne."

        # ============================================================
        # PRIORITÉ 9 : Symptômes
        # ============================================================
        if any(w in q_norm for w in ["symptome", "symptôme", "presente", "présente", "fievre", "toux"]):
            sparql = PREFIXES + """SELECT ?patient ?nomPatient ?symptome WHERE {
    ?patient :presente ?symptome .
    OPTIONAL { ?patient :nom ?nomPatient }
}"""
            return sparql, "Recherche des symptômes par patient", \
                   "L'IA utilise la relation presente reliant un Patient à ses instances de Symptome."

        # ============================================================
        # PRIORITÉ 10 : Dossier médical / Groupe sanguin
        # ============================================================
        if any(w in q_norm for w in ["dossier", "enregistre", "enregistré"]):
            sparql = PREFIXES + """SELECT ?patient ?nom ?dossier ?groupeSanguin WHERE {
    ?patient rdf:type/rdfs:subClassOf* :Patient ;
             :numeroDossier ?dossier .
    OPTIONAL { ?patient :nom ?nom }
    OPTIONAL { ?patient :groupeSanguin ?groupeSanguin }
}"""
            return sparql, "Recherche des Patients Enregistrés (avec N° Dossier)", \
                   "L'IA interroge la propriété de données numeroDossier."

        if any(w in q_norm for w in ["groupe sanguin", "sang", "sanguin"]):
            sparql = PREFIXES + """SELECT ?patient ?nom ?groupeSanguin WHERE {
    ?patient :groupeSanguin ?groupeSanguin .
    OPTIONAL { ?patient :nom ?nom }
}"""
            return sparql, "Recherche des groupes sanguins", \
                   "L'IA filtre sur la propriété de données groupeSanguin."

        # ============================================================
        # PRIORITÉ 11 : Stagiaires
        # ============================================================
        if "stagiaire" in q_norm:
            sparql = PREFIXES + """SELECT ?stagiaire ?nom ?age ?cin ?tel WHERE {
    ?stagiaire rdf:type :Stagiaire .
    OPTIONAL { ?stagiaire :nom ?nom }
    OPTIONAL { ?stagiaire :age ?age }
    OPTIONAL { ?stagiaire :numeroCIN ?cin }
    OPTIONAL { ?stagiaire :telephone ?tel }
}"""
            return sparql, "Recherche des Stagiaires", \
                   "L'IA filtre sur la classe Stagiaire (sous-classe de Role, disjointe de Medecin et Patient)."

        # ============================================================
        # PRIORITÉ 12 : Patients en général (SANS filtre âge)
        # ============================================================
        if "patient" in q_norm:
            sparql = PREFIXES + """SELECT ?patient ?nom ?age ?dossier ?groupeSanguin ?tel WHERE {
    ?patient rdf:type/rdfs:subClassOf* :Patient .
    OPTIONAL { ?patient :nom ?nom }
    OPTIONAL { ?patient :age ?age }
    OPTIONAL { ?patient :numeroDossier ?dossier }
    OPTIONAL { ?patient :groupeSanguin ?groupeSanguin }
    OPTIONAL { ?patient :telephone ?tel }
}"""
            return sparql, "Recherche de tous les Patients", \
                   "L'IA sélectionne tous les individus dont le rdf:type est une sous-classe de Patient."

        # ============================================================
        # PRIORITÉ 14 : Hiérarchie des classes
        # ============================================================
        if any(w in q_norm for w in ["hierarchie", "hiérarchie", "sous-classe", "sous classe", "arbre"]):
            sparql = PREFIXES + """SELECT ?sousClasse ?classeParente ?label WHERE {
    ?sousClasse rdfs:subClassOf ?classeParente .
    ?sousClasse rdfs:subClassOf* :Personne .
    OPTIONAL { ?sousClasse rdfs:label ?label }
}"""
            return sparql, "Hiérarchie taxonomique de Personne", \
                   "L'IA utilise rdfs:subClassOf pour reconstruire l'arbre d'héritage de la classe Personne."

        # ============================================================
        # PRIORITÉ 15 : Requête générale par défaut
        # ============================================================
        sparql = PREFIXES + """SELECT ?personne ?type ?nom ?age ?tel ?cin WHERE {
    ?personne rdf:type ?type .
    ?type rdfs:subClassOf* :Personne .
    OPTIONAL { ?personne :nom ?nom }
    OPTIONAL { ?personne :age ?age }
    OPTIONAL { ?personne :telephone ?tel }
    OPTIONAL { ?personne :numeroCIN ?cin }
}"""
        return sparql, "Inventaire général des Personnes", \
               "L'IA a formulé une requête globale englobant toutes les instances de la classe Personne et ses sous-classes."

    # -----------------------------------------------------------------------
    # Alternative sans règles en dur : Traduction via LLM (Gemini / OpenAI)
    # -----------------------------------------------------------------------
    def translate_with_llm(self, question: str) -> Optional[Tuple[str, str, str]]:
        """
        Alternative moderne sans règles en code : Text-to-SPARQL par LLM.
        Active si la variable d'environnement GEMINI_API_KEY ou OPENAI_API_KEY est définie.
        Permet de répondre à toute question sans coder chaque cas manuellement.
        """
        gemini_key = os.environ.get("GEMINI_API_KEY")
        openai_key = os.environ.get("OPENAI_API_KEY")

        if not gemini_key and not openai_key:
            return None

        prompt_system = """Tu es un traducteur de Langage Naturel vers SPARQL pour une ontologie médicale OWL.
Ontologie :
Préfixe : : <http://example.org/ontologie-medicale#>
Classes : Personne, Medecin, MedecinGeneraliste, MedecinSpecialiste, Cardiologue, Patient, PatientEnfant, PatientAdulte, Stagiaire, Service.
Propriétés de données : nom, prenom, age, telephone, email, adresse, numeroCIN, specialite, numeroOrdre, groupeSanguin, numeroDossier.
Propriétés d'objets : soigne, estSoignePar, connait, aConsulte, presente, appartientA, estPrisEnChargePar.

Règle absolue : Retourne UNIQUEMENT le code SPARQL valide commençant par PREFIX, sans formatage markdown, sans backticks."""

        # 1. Essai avec Gemini API si clé présente
        if gemini_key:
            try:
                import urllib.request
                import json
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": prompt_system},
                            {"text": f"Question de l'utilisateur : {question}"}
                        ]
                    }]
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    res_json = json.loads(resp.read().decode("utf-8"))
                    text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                    clean_sparql = re.sub(r"^```sparql\s*", "", text, flags=re.IGNORECASE)
                    clean_sparql = re.sub(r"^```\s*", "", clean_sparql)
                    clean_sparql = re.sub(r"\s*```$", "", clean_sparql).strip()
                    return clean_sparql, "Génération SPARQL par Modèle de Langage (Gemini LLM)", \
                           "La requête SPARQL a été générée dynamiquement par le LLM à partir du schéma OWL sans règles statiques."
            except Exception as e:
                print(f"[LLM Error - Gemini] {e}")

        # 2. Essai avec OpenAI API si clé présente
        if openai_key:
            try:
                import urllib.request
                import json
                url = "https://api.openai.com/v1/chat/completions"
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": prompt_system},
                        {"role": "user", "content": f"Question de l'utilisateur : {question}"}
                    ],
                    "temperature": 0.0
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {openai_key}"
                    }
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    res_json = json.loads(resp.read().decode("utf-8"))
                    text = res_json["choices"][0]["message"]["content"].strip()
                    clean_sparql = re.sub(r"^```sparql\s*", "", text, flags=re.IGNORECASE)
                    clean_sparql = re.sub(r"^```\s*", "", clean_sparql)
                    clean_sparql = re.sub(r"\s*```$", "", clean_sparql).strip()
                    return clean_sparql, "Génération SPARQL par Modèle de Langage (OpenAI LLM)", \
                           "La requête SPARQL a été générée dynamiquement par OpenAI à partir du schéma OWL sans règles statiques."
            except Exception as e:
                print(f"[LLM Error - OpenAI] {e}")

        return None

    # -----------------------------------------------------------------------
    # Flux complet : Question -> SPARQL -> Exécution -> Réponse
    # -----------------------------------------------------------------------
    def answer_question(self, question: str) -> Dict[str, Any]:
        """
        Traite le flux complet :
        Question -> Traduction SPARQL -> Exécution via RDFLib/Fuseki -> Formatage réponse.
        """
        # Tentative LLM si activé ou si clé API disponible
        use_llm = os.environ.get("USE_LLM", "").lower() in ["true", "1", "yes"]
        sparql_query, intention, explanation = None, None, None
        if use_llm or os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY"):
            llm_res = self.translate_with_llm(question)
            if llm_res:
                sparql_query, intention, explanation = llm_res

        # Fallback automatique sur le Moteur Sémantique Autonome (Slot-Filling + Règles)
        if not sparql_query:
            sparql_query, intention, explanation = self.translate_question_to_sparql(question)

        data = {}
        if self.rdflib_service:
            data = self.rdflib_service.execute_sparql(sparql_query)

        nb_results = len(data.get("results", {}).get("bindings", []))

        if nb_results == 0:
            summary_text = f"Aucun résultat trouvé pour : « {question} »."
        elif nb_results == 1:
            summary_text = f"1 résultat trouvé pour : « {question} »."
        else:
            summary_text = f"{nb_results} résultats trouvés pour : « {question} »."

        return {
            "question": question,
            "intention": intention,
            "explanation": explanation,
            "sparql_query": sparql_query,
            "data": data,
            "count": nb_results,
            "answer_summary": summary_text
        }
