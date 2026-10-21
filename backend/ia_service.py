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
