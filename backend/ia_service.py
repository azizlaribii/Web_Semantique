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


# ---------------------------------------------------------------------------
# Registre dynamique des sous-classes de l'ontologie (ordonné du spécifique au général)
# ---------------------------------------------------------------------------
_PERSONNE_SUBCLASSES_REGISTRY = [
    # 1. Sous-classes de Stuff_Médicale
    (
        ["agents_de_service_hospitalier", "agent_de_service_hospitalier",
         "agents de service hospitalier", "agent de service hospitalier",
         "agent service hospitalier", "agents service hospitalier",
         "agents de service", "agent de service", "ash"],
        "med:Agents_de_service_hospitalier",
        "Agent de service hospitalier",
        "?individu rdf:type/rdfs:subClassOf* med:Agents_de_service_hospitalier ."
    ),
    (
        ["aide_soignant", "aides_soignants", "aide soignant", "aides soignants",
         "aide-soignant", "aides-soignants", "aide soignante", "aides soignantes"],
        "med:Aide_soignant",
        "Aide-soignant",
        "?individu rdf:type/rdfs:subClassOf* med:Aide_soignant ."
    ),
    (
        ["sages_femmes", "sage_femme", "sages femmes", "sage femme",
         "sages-femmes", "sage-femme"],
        "med:sages-femmes",
        "Sage-femme",
        "?individu rdf:type/rdfs:subClassOf* med:sages-femmes ."
    ),
    (
        ["chefs_de_service", "chef_de_service", "chefs de service", "chef de service"],
        "med:chefs_de_service",
        "Chef de service",
        "?individu rdf:type/rdfs:subClassOf* med:chefs_de_service ."
    ),
    (
        ["medico_techniques", "medico_technique", "medico techniques", "medico technique",
         "médico-techniques", "médico-technique", "medico-techniques", "medico-technique"],
        "med:Médico-techniques",
        "Médico-technique",
        "?individu rdf:type/rdfs:subClassOf* med:Médico-techniques ."
    ),
    (
        ["kinesitherapeutes", "kinesitherapeute", "kinésithérapeutes", "kinésithérapeute", "kine", "kines"],
        "med:kinésithérapeutes",
        "Kinésithérapeute",
        "?individu rdf:type/rdfs:subClassOf* med:kinésithérapeutes ."
    ),
    (
        ["secretaires_medicales", "secretaire_medicale", "secrétaires_médicales", "secrétaire_médicale",
         "secretaires medicales", "secretaire medicale", "secrétaires médicales", "secrétaire médicale"],
        "med:Secrétaires_médicales",
        "Secrétaire médicale",
        "?individu rdf:type/rdfs:subClassOf* med:Secrétaires_médicales ."
    ),
    (
        ["infirmiers", "infirmier", "infirmieres", "infirmiere", "infirmerie"],
        "med:infirmier",
        "Infirmier",
        "{ ?individu rdf:type/rdfs:subClassOf* med:infirmier . } UNION { ?individu rdf:type/rdfs:subClassOf* med:Infirmier . }"
    ),
    (
        ["stuff_medicale", "stuff_médicale", "stuff_medical", "stuff_médical",
         "stuff medicale", "stuff médicale", "stuff medicales", "stuff médicales",
         "stuff medical", "stuff médical", "stuff medicals", "stuff médicals",
         "staff medical", "staff medicale", "staff medicals", "staff médical", "staff médicales",
         "personnel medical", "personnel médical"],
        "med:Stuff_Médicale",
        "Stuff Médical",
        "{ ?individu rdf:type/rdfs:subClassOf* <http://example.org/ontologie-medicale#Stuff_Médicale> . } UNION { ?individu rdf:type/rdfs:subClassOf* med:Stuff_Medicale . }"
    ),

    # 2. Médecins Spécialistes précis
    (["cardiologue", "cardiologues"], "med:Cardiologue", "Cardiologue", "?individu rdf:type/rdfs:subClassOf* med:Cardiologue ."),
    (["dermatologue", "dermatologues"], "med:Dermatologue", "Dermatologue", "?individu rdf:type/rdfs:subClassOf* med:Dermatologue ."),
    (["endocrinologue", "endocrinologues"], "med:Endocrinologue", "Endocrinologue", "?individu rdf:type/rdfs:subClassOf* med:Endocrinologue ."),
    (["gastro_enterologue", "gastro-entérologue", "gastro enterologue", "gastroenterologue"], "med:Gastro-entérologue", "Gastro-entérologue", "?individu rdf:type/rdfs:subClassOf* med:Gastro-entérologue ."),
    (["neurologue", "neurologues"], "med:Neurologue", "Neurologue", "?individu rdf:type/rdfs:subClassOf* med:Neurologue ."),
    (["pneumologue", "pneumologues"], "med:Pneumologue", "Pneumologue", "?individu rdf:type/rdfs:subClassOf* med:Pneumologue ."),
    (["psychiatre", "psychiatres"], "med:Psychiatre", "Psychiatre", "?individu rdf:type/rdfs:subClassOf* med:Psychiatre ."),
    (["anesthesiste", "anesthesistes", "anesthésiste", "anesthésistes"], "med:Anesthésiste", "Anesthésiste", "?individu rdf:type/rdfs:subClassOf* med:Anesthésiste ."),
    (["medecin generaliste", "medecins generalistes", "generaliste", "généraliste", "generalistes", "généralistes"], "med:MedecinGeneraliste", "Médecin Généraliste", "?individu rdf:type/rdfs:subClassOf* med:MedecinGeneraliste ."),
    (["medecin specialiste", "medecins specialistes", "specialiste", "spécialiste", "specialistes", "spécialistes"], "med:MedecinSpecialiste", "Médecin Spécialiste", "?individu rdf:type/rdfs:subClassOf* med:MedecinSpecialiste ."),

    # 3. Rôles et sous-classes principales
    (["stagiaire", "stagiaires"], "med:Stagiaire", "Stagiaire", "{ ?individu rdf:type/rdfs:subClassOf* med:Stagiaire . } UNION { ?individu med:joueLeRoleDe med:Stagiaire . } UNION { ?individu med:role med:Stagiaire . }"),
    (["patient enfant", "patients enfants", "enfant", "enfants"], "med:PatientEnfant", "Patient Enfant", "?individu rdf:type/rdfs:subClassOf* med:PatientEnfant ."),
    (["patient adulte", "patients adultes", "adulte", "adultes"], "med:PatientAdulte", "Patient Adulte", "?individu rdf:type/rdfs:subClassOf* med:PatientAdulte ."),
    (["patient", "patients", "patiente", "patientes"], "med:Patient", "Patient", "?individu rdf:type/rdfs:subClassOf* med:Patient ."),
    (["medecin", "médecin", "medecins", "médecins", "docteur", "docteurs", "dr"], "med:Medecin", "Médecin", "?individu rdf:type/rdfs:subClassOf* med:Medecin ."),
    (["role", "roles", "rôle", "rôles"], "med:Role", "Rôle", "?individu rdf:type/rdfs:subClassOf* med:Role ."),
]


def _detect_target_class(q: str) -> Tuple[str, str]:
    """
    Détecte la classe cible principale depuis la question.
    Retourne (classe_sparql, label_humain).
    """
    q_l = q.lower()
    for keywords, cls_iri, label, _ in _PERSONNE_SUBCLASSES_REGISTRY:
        if any(k in q_l for k in keywords):
            return cls_iri, label
    return "med:Personne", "Personne"


# Classes qui sont des sous-classes précises (on utilise rdf:type direct, pas subClassOf*)
_LEAF_SUBCLASSES = {
    "med:MedecinGeneraliste", "med:MedecinSpecialiste", "med:Cardiologue",
    "med:PatientAdulte", "med:PatientEnfant", "med:Stagiaire",
    "med:Agents_de_service_hospitalier", "med:Aide_soignant",
    "med:sages-femmes", "med:chefs_de_service", "med:infirmier"
}


def _build_age_filter_query(target_class: str, label: str,
                             age_min: Optional[int], age_max: Optional[int],
                             age_exact: Optional[int],
                             age_gt: Optional[int] = None,
                             age_lt: Optional[int] = None) -> Tuple[str, str, str]:
    """
    Construit une requête SPARQL avec filtre d'âge sur la classe cible.
    Extrait l'ensemble des coordonnées et attributs sans doublon de prénom.
    """
    clean_target = target_class if target_class.startswith("med:") else ("med:" + target_class.lstrip(":"))
    if target_class in _LEAF_SUBCLASSES or clean_target in _LEAF_SUBCLASSES:
        type_clause = f"?personne rdf:type {clean_target} ;"
    else:
        type_clause = f"?personne rdf:type/rdfs:subClassOf* {clean_target} ;"

    if age_exact is not None:
        filter_clause = f"FILTER(?ageVal = {age_exact})"
        intention = f"{label}s d'âge exactement {age_exact} ans"
        explication = f"L'IA a appliqué FILTER(?ageVal = {age_exact}) sur la propriété med:age."
    elif age_min is not None and age_max is not None:
        filter_clause = f"FILTER(?ageVal >= {age_min} && ?ageVal <= {age_max})"
        intention = f"{label}s entre {age_min} et {age_max} ans"
        explication = f"L'IA a appliqué FILTER(?ageVal >= {age_min} && ?ageVal <= {age_max}) — intervalle d'âge."
    elif age_min is not None:
        filter_clause = f"FILTER(?ageVal >= {age_min})"
        intention = f"{label}s d'au moins {age_min} ans"
        explication = f"L'IA a appliqué FILTER(?ageVal >= {age_min}) sur la propriété med:age."
    elif age_max is not None:
        filter_clause = f"FILTER(?ageVal <= {age_max})"
        intention = f"{label}s d'au plus {age_max} ans"
        explication = f"L'IA a appliqué FILTER(?ageVal <= {age_max}) sur la propriété med:age."
    elif age_gt is not None:
        filter_clause = f"FILTER(?ageVal > {age_gt})"
        intention = f"{label}s de plus de {age_gt} ans"
        explication = f"L'IA a appliqué FILTER(?ageVal > {age_gt}) sur la propriété med:age."
    elif age_lt is not None:
        filter_clause = f"FILTER(?ageVal < {age_lt})"
        intention = f"{label}s de moins de {age_lt} ans"
        explication = f"L'IA a appliqué FILTER(?ageVal < {age_lt}) sur la propriété med:age."
    else:
        filter_clause = ""
        intention = f"Âge de tous les {label}s"
        explication = "L'IA extrait l'âge sans filtre, trié par ordre croissant."

    sparql = PREFIXES + f"""SELECT DISTINCT ?personne (SAMPLE(?nomClean) AS ?nom) (SAMPLE(?typeVal) AS ?role) (SAMPLE(?speVal) AS ?specialite) (SAMPLE(?emailVal) AS ?email) (SAMPLE(?cinVal) AS ?cin) (SAMPLE(?telVal) AS ?telephone) (SAMPLE(?ageVal) AS ?age) (SAMPLE(?ordVal) AS ?numeroOrdre) (SAMPLE(?dosVal) AS ?dossier) (SAMPLE(?sangVal) AS ?groupeSanguin) WHERE {{
    {type_clause}
              med:age ?ageVal .
    OPTIONAL {{ ?personne med:nom ?nomProp }}
    OPTIONAL {{ ?personne med:prenom ?prenomProp }}
    OPTIONAL {{ ?personne rdfs:label ?labelProp }}
    BIND(COALESCE(
        IF(BOUND(?prenomProp) && BOUND(?nomProp) && !CONTAINS(LCASE(STR(?nomProp)), LCASE(STR(?prenomProp))), CONCAT(?prenomProp, " ", ?nomProp), ?nomProp),
        ?labelProp,
        REPLACE(REPLACE(STR(?personne), "^.*[#/]", ""), "_", " ")
    ) AS ?nomClean)
    OPTIONAL {{ ?personne rdf:type ?typeVal . FILTER(?typeVal != owl:NamedIndividual) }}
    OPTIONAL {{ ?personne med:specialite ?speVal }}
    OPTIONAL {{ ?personne med:email ?emailVal }}
    OPTIONAL {{ ?personne med:numeroCIN ?cinVal }}
    OPTIONAL {{ ?personne med:telephone ?telVal }}
    OPTIONAL {{ ?personne med:numeroOrdre ?ordVal }}
    OPTIONAL {{ ?personne med:numeroDossier ?dosVal }}
    OPTIONAL {{ ?personne med:groupeSanguin ?sangVal }}
    BIND(?ageVal AS ?age)
    {filter_clause}
}} GROUP BY ?personne ORDER BY ?age"""

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
    OPTIONAL {{ {inst_var} :nom ?nomProp }}
    OPTIONAL {{ {inst_var} rdfs:label ?labelProp }}
    OPTIONAL {{ {inst_var} :age ?age }}
    OPTIONAL {{ {inst_var} :numeroCIN ?cin }}
    OPTIONAL {{ {inst_var} :numeroDossier ?dossier }}
    OPTIONAL {{ {inst_var} :groupeSanguin ?groupeSanguin }}
    OPTIONAL {{ {inst_var} :telephone ?tel }}
    BIND(COALESCE(?nomProp, ?labelProp, REPLACE(REPLACE(STR({inst_var}), "^.*[#/]", ""), "_", " ")) AS ?nom)"""
    elif target_class == ":Medecin":
        select_clause = f"SELECT DISTINCT {inst_var} ?nom ?age ?cin ?specialite ?numeroOrdre ?tel WHERE {{"
        optionals = f"""    {inst_var} rdf:type/rdfs:subClassOf* :Medecin .
    OPTIONAL {{ {inst_var} :nom ?nomProp }}
    OPTIONAL {{ {inst_var} rdfs:label ?labelProp }}
    OPTIONAL {{ {inst_var} :age ?age }}
    OPTIONAL {{ {inst_var} :numeroCIN ?cin }}
    OPTIONAL {{ {inst_var} :specialite ?specialite }}
    OPTIONAL {{ {inst_var} :numeroOrdre ?numeroOrdre }}
    OPTIONAL {{ {inst_var} :telephone ?tel }}
    BIND(COALESCE(?nomProp, ?labelProp, REPLACE(REPLACE(STR({inst_var}), "^.*[#/]", ""), "_", " ")) AS ?nom)"""
    elif target_class == ":Stagiaire":
        select_clause = f"SELECT DISTINCT {inst_var} ?nom ?age ?cin ?tel WHERE {{"
        optionals = f"""    {inst_var} rdf:type :Stagiaire .
    OPTIONAL {{ {inst_var} :nom ?nomProp }}
    OPTIONAL {{ {inst_var} rdfs:label ?labelProp }}
    OPTIONAL {{ {inst_var} :age ?age }}
    OPTIONAL {{ {inst_var} :numeroCIN ?cin }}
    OPTIONAL {{ {inst_var} :telephone ?tel }}
    BIND(COALESCE(?nomProp, ?labelProp, REPLACE(REPLACE(STR({inst_var}), "^.*[#/]", ""), "_", " ")) AS ?nom)"""
    else:
        select_clause = f"SELECT DISTINCT {inst_var} ?type ?nom ?age ?cin ?dossier ?groupeSanguin ?tel WHERE {{"
        optionals = f"""    {inst_var} rdf:type ?type .
    ?type rdfs:subClassOf* :Personne .
    OPTIONAL {{ {inst_var} :nom ?nomProp }}
    OPTIONAL {{ {inst_var} rdfs:label ?labelProp }}
    OPTIONAL {{ {inst_var} :age ?age }}
    OPTIONAL {{ {inst_var} :numeroCIN ?cin }}
    OPTIONAL {{ {inst_var} :numeroDossier ?dossier }}
    OPTIONAL {{ {inst_var} :groupeSanguin ?groupeSanguin }}
    OPTIONAL {{ {inst_var} :telephone ?tel }}
    BIND(COALESCE(?nomProp, ?labelProp, REPLACE(REPLACE(STR({inst_var}), "^.*[#/]", ""), "_", " ")) AS ?nom)"""

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
        # PRIORITÉ 0.05 : COMPTAGE & STATISTIQUES (COUNT)
        # "Combien de personnes ?", "combien de medecins ?", "nombre de patients ?"
        # ============================================================
        if any(w in q_norm for w in ["combien", "nombre de", "nombre d", "total des", "compter"]):
            if any(w in q_norm for w in ["medecin", "medecins", "docteur", "docteurs"]):
                sparql = PREFIXES + """SELECT (COUNT(DISTINCT ?medecin) AS ?total) WHERE {
    ?medecin rdf:type/rdfs:subClassOf* :Medecin .
}"""
                return sparql, "Nombre total de Médecins", \
                       "L'IA exécute une fonction d'agrégation COUNT(?) sur la classe Medecin."
            elif any(w in q_norm for w in ["patient", "patients"]):
                sparql = PREFIXES + """SELECT (COUNT(DISTINCT ?patient) AS ?total) WHERE {
    ?patient rdf:type/rdfs:subClassOf* :Patient .
}"""
                return sparql, "Nombre total de Patients", \
                       "L'IA exécute une fonction d'agrégation COUNT(?) sur la classe Patient."
            elif any(w in q_norm for w in ["stagiaire", "stagiaires"]):
                sparql = PREFIXES + """SELECT (COUNT(DISTINCT ?stagiaire) AS ?total) WHERE {
    ?stagiaire rdf:type/rdfs:subClassOf* :Stagiaire .
}"""
                return sparql, "Nombre total de Stagiaires", \
                       "L'IA exécute une fonction d'agrégation COUNT(?) sur la classe Stagiaire."
            else:
                sparql = PREFIXES + """SELECT (COUNT(DISTINCT ?personne) AS ?total) WHERE {
    ?personne rdf:type ?type .
    ?type rdfs:subClassOf* :Personne .
    FILTER(?type != <http://www.w3.org/2002/07/owl#NamedIndividual>)
}"""
                return sparql, "Nombre total de Personnes dans l'Ontologie", \
                       "L'IA exécute un comptage global COUNT(?) de tous les individus de l'ontologie Personne."

        # ============================================================
        # PRIORITÉ 0.1 : MÉTADONNÉES DE L'ONTOLOGIE (OWL & RDF Schema)
        # Reconnaissance automatique : Classes, Sous-classes, ObjectProperties,
        # DataProperties, Individus (NamedIndividuals), et Annotations.
        # ============================================================

        # 1. Object Properties (Propriétés d'objet)
        is_obj_prop = (
            any(w in q_norm for w in ["objectproperty", "objectproperties", "object property", "object properties",
                                      "propriete d'objet", "proprietes d'objet", "proprietes d'objets",
                                      "propriete objet", "proprietes objets", "relations entre classes",
                                      "relations de l'ontologie", "relations d'objet"])
            or (any(p in q_norm for p in ["propriete", "proprietes", "property", "properties"])
                and any(w in q_norm for w in ["objet", "objets", "object", "objects", "relation", "relations"]))
        )
        if is_obj_prop:
            sparql = PREFIXES + """SELECT DISTINCT ?propriete (SAMPLE(?nomClean) AS ?nom) (SAMPLE(?domClean) AS ?domaine) (SAMPLE(?rngClean) AS ?range) (SAMPLE(?lbl) AS ?label) (SAMPLE(?desc) AS ?description) WHERE {
    ?propriete rdf:type owl:ObjectProperty .
    FILTER(!isBlank(?propriete))
    FILTER(!STRSTARTS(STR(?propriete), "http://www.w3.org/2002/07/owl#"))
    OPTIONAL { ?propriete rdfs:domain ?dom . FILTER(!isBlank(?dom)) }
    OPTIONAL { ?propriete rdfs:range ?rng . FILTER(!isBlank(?rng)) }
    OPTIONAL { ?propriete rdfs:label ?lbl }
    OPTIONAL { ?propriete rdfs:comment ?desc }
    BIND(REPLACE(REPLACE(STR(?propriete), "^.*[#/]", ""), "_", " ") AS ?nomClean)
    BIND(REPLACE(REPLACE(STR(?dom), "^.*[#/]", ""), "_", " ") AS ?domClean)
    BIND(REPLACE(REPLACE(STR(?rng), "^.*[#/]", ""), "_", " ") AS ?rngClean)
} GROUP BY ?propriete ORDER BY ?nom"""
            return sparql, "Liste des Object Properties (Propriétés d'objet)", \
                   "L'IA extrait toutes les propriétés d'objet (owl:ObjectProperty) reliant les concepts de l'ontologie, avec leur domaine et leur portée."

        # 2. Data Properties (Propriétés de type de données)
        is_data_prop = (
            any(w in q_norm for w in ["dataproperty", "dataproperties", "data property", "data properties",
                                      "datatype property", "datatype properties", "datatypeproperty", "datatypeproperties",
                                      "propriete de donnee", "proprietes de donnees", "propriete donnee", "proprietes donnees",
                                      "proprietes de type donnee", "attributs de donnee", "attributs"])
            or (any(p in q_norm for p in ["propriete", "proprietes", "property", "properties"])
                and any(w in q_norm for w in ["donnee", "donnees", "data", "datatype", "type de donnee", "valeur", "litteral"]))
        )
        if is_data_prop:
            sparql = PREFIXES + """SELECT DISTINCT ?propriete (SAMPLE(?nomClean) AS ?nom) (SAMPLE(?domClean) AS ?domaine) (SAMPLE(?rngClean) AS ?range) (SAMPLE(?lbl) AS ?label) (SAMPLE(?desc) AS ?description) WHERE {
    ?propriete rdf:type owl:DatatypeProperty .
    FILTER(!isBlank(?propriete))
    FILTER(!STRSTARTS(STR(?propriete), "http://www.w3.org/2002/07/owl#"))
    OPTIONAL { ?propriete rdfs:domain ?dom . FILTER(!isBlank(?dom)) }
    OPTIONAL { ?propriete rdfs:range ?rng . FILTER(!isBlank(?rng)) }
    OPTIONAL { ?propriete rdfs:label ?lbl }
    OPTIONAL { ?propriete rdfs:comment ?desc }
    BIND(REPLACE(REPLACE(STR(?propriete), "^.*[#/]", ""), "_", " ") AS ?nomClean)
    BIND(REPLACE(REPLACE(STR(?dom), "^.*[#/]", ""), "_", " ") AS ?domClean)
    BIND(REPLACE(REPLACE(STR(?rng), "^.*[#/]", ""), "_", " ") AS ?rngClean)
} GROUP BY ?propriete ORDER BY ?nom"""
            return sparql, "Liste des Data Properties (Propriétés de données)", \
                   "L'IA extrait toutes les propriétés de données (owl:DatatypeProperty) avec leur domaine (classe cible) et type de valeur (xsd:*)."

        # 3. Toutes les propriétés confondues (Object + Data)
        is_all_props = (
            any(w in q_norm for w in ["toutes les proprietes", "liste des proprietes", "quelles sont les proprietes",
                                      "proprietes de l'ontologie", "properties de l'ontologie", "all properties"])
        )
        if is_all_props:
            sparql = PREFIXES + """SELECT DISTINCT ?propriete (SAMPLE(?nomClean) AS ?nom) (SAMPLE(?genreClean) AS ?typePropriete) (SAMPLE(?domClean) AS ?domaine) (SAMPLE(?rngClean) AS ?range) WHERE {
    { ?propriete rdf:type owl:ObjectProperty . BIND("ObjectProperty" AS ?genreClean) }
    UNION
    { ?propriete rdf:type owl:DatatypeProperty . BIND("DatatypeProperty" AS ?genreClean) }
    FILTER(!isBlank(?propriete))
    FILTER(!STRSTARTS(STR(?propriete), "http://www.w3.org/2002/07/owl#"))
    OPTIONAL { ?propriete rdfs:domain ?dom . FILTER(!isBlank(?dom)) }
    OPTIONAL { ?propriete rdfs:range ?rng . FILTER(!isBlank(?rng)) }
    BIND(REPLACE(REPLACE(STR(?propriete), "^.*[#/]", ""), "_", " ") AS ?nomClean)
    BIND(REPLACE(REPLACE(STR(?dom), "^.*[#/]", ""), "_", " ") AS ?domClean)
    BIND(REPLACE(REPLACE(STR(?rng), "^.*[#/]", ""), "_", " ") AS ?rngClean)
} GROUP BY ?propriete ORDER BY ?genreClean ?nomClean"""
            return sparql, "Toutes les Propriétés de l'Ontologie (Object & Datatype)", \
                   "L'IA liste l'ensemble des propriétés (relations d'objet et attributs de données) de l'ontologie."

        # 4. Sous-classes (rdfs:subClassOf)
        is_subclass = any(w in q_norm for w in [
            "sous classe", "sous-classe", "sous classes", "sous-classes",
            "subclass", "subclasses", "subclassof", "hierarchie des classes", "arbre des classes"
        ])
        if is_subclass:
            parent_match = None
            # Extraction dynamique : "sous classes de X", "sous-classes d'X", etc.
            m_dyn = re.search(r'(?:sous[- ]?classes?|subclass(?:es)?)\s+(?:de\s+|d[\'’])?([a-zA-Z0-9_\-]+)', q_norm)
            if m_dyn:
                cand = m_dyn.group(1).strip()
                if cand not in ["l", "la", "le", "les", "tous", "toutes", "ontologie", "cette", "chaque", "des"]:
                    parent_match = cand

            if not parent_match:
                for p_cand in ["medecin", "personne", "patient", "maladie", "medicament", "symptome", "service", "operation", "ordonnance", "role", "chirurgie", "consultation", "stuff"]:
                    if p_cand in q_norm:
                        parent_match = p_cand
                        break

            if parent_match:
                sparql = PREFIXES + f"""SELECT DISTINCT ?sousClasse (SAMPLE(?nomClean) AS ?nom) (SAMPLE(?parentClean) AS ?parent) (SAMPLE(?directVal) AS ?estDirecte) (SAMPLE(?lbl) AS ?label) (SAMPLE(?desc) AS ?description) WHERE {{
    {{
        ?sousClasse rdfs:subClassOf ?parent .
        FILTER(CONTAINS(LCASE(STR(?parent)), "{parent_match}"))
        BIND("Oui" AS ?directVal)
    }}
    UNION
    {{
        ?sousClasse rdfs:subClassOf+ ?ancestor .
        ?sousClasse rdfs:subClassOf ?parent .
        FILTER(CONTAINS(LCASE(STR(?ancestor)), "{parent_match}"))
        FILTER(!CONTAINS(LCASE(STR(?parent)), "{parent_match}"))
        BIND("Non" AS ?directVal)
    }}
    FILTER(!isBlank(?sousClasse) && !isBlank(?parent))
    FILTER(?sousClasse != ?parent)
    FILTER(!STRSTARTS(STR(?sousClasse), "http://www.w3.org/2002/07/owl#"))
    FILTER(!STRSTARTS(STR(?parent), "http://www.w3.org/2002/07/owl#"))
    OPTIONAL {{ ?sousClasse rdfs:label ?lbl }}
    OPTIONAL {{ ?sousClasse rdfs:comment ?desc }}
    BIND(REPLACE(REPLACE(STR(?sousClasse), "^.*[#/]", ""), "_", " ") AS ?nomClean)
    BIND(REPLACE(REPLACE(STR(?parent), "^.*[#/]", ""), "_", " ") AS ?parentClean)
}} GROUP BY ?sousClasse ORDER BY DESC(?directVal) ?parentClean ?nomClean"""
                return sparql, f"Sous-classes de '{parent_match.capitalize()}'", \
                       f"L'IA extrait la hiérarchie rdfs:subClassOf (directe et dérivée) pour la classe {parent_match.capitalize()}."
            else:
                sparql = PREFIXES + """SELECT DISTINCT ?sousClasse (SAMPLE(?nomClean) AS ?nom) (SAMPLE(?parentClean) AS ?parent) (SAMPLE(?lbl) AS ?label) (SAMPLE(?desc) AS ?description) WHERE {
    ?sousClasse rdfs:subClassOf ?parent .
    FILTER(!isBlank(?sousClasse) && !isBlank(?parent))
    FILTER(?sousClasse != ?parent)
    FILTER(?parent != owl:Thing)
    FILTER(!STRSTARTS(STR(?sousClasse), "http://www.w3.org/2002/07/owl#"))
    FILTER(!STRSTARTS(STR(?parent), "http://www.w3.org/2002/07/owl#"))
    OPTIONAL { ?sousClasse rdfs:label ?lbl }
    OPTIONAL { ?sousClasse rdfs:comment ?desc }
    BIND(REPLACE(REPLACE(STR(?sousClasse), "^.*[#/]", ""), "_", " ") AS ?nomClean)
    BIND(REPLACE(REPLACE(STR(?parent), "^.*[#/]", ""), "_", " ") AS ?parentClean)
} GROUP BY ?sousClasse ORDER BY ?parentClean ?nom"""
                return sparql, "Hiérarchie de toutes les Sous-classes (rdfs:subClassOf)", \
                       "L'IA extrait l'ensemble des relations de sous-classes entre concepts de l'ontologie."

        # 5. Classes (owl:Class)
        is_classes = (
            (any(w in q_norm for w in ["classe", "classes", "owl:class", "rdfs:class", "concepts de l'ontologie", "concepts"])
             and any(w in q_norm for w in ["toutes", "liste", "quelles", "quels", "donne", "affiche", "montre", "ontologie", "definies", "existantes", "tous"]))
            or q_norm.strip() in ["classes", "les classes", "classes de l'ontologie", "toutes les classes", "quelles sont les classes", "liste des classes", "donne moi les classes"]
        )
        if is_classes:
            sparql = PREFIXES + """SELECT DISTINCT ?classe (SAMPLE(?nomClean) AS ?nom) (SAMPLE(?parentClean) AS ?parent) (SAMPLE(?lbl) AS ?label) (SAMPLE(?desc) AS ?description) WHERE {
    { ?classe rdf:type owl:Class } UNION { ?classe rdf:type rdfs:Class }
    FILTER(!isBlank(?classe))
    FILTER(!STRSTARTS(STR(?classe), "http://www.w3.org/2002/07/owl#"))
    FILTER(!STRSTARTS(STR(?classe), "http://www.w3.org/1999/02/22-rdf-syntax-ns#"))
    FILTER(!STRSTARTS(STR(?classe), "http://www.w3.org/2000/01/rdf-schema#"))
    OPTIONAL { ?classe rdfs:subClassOf ?parent . FILTER(!isBlank(?parent)) }
    OPTIONAL { ?classe rdfs:label ?lbl }
    OPTIONAL { ?classe rdfs:comment ?desc }
    BIND(REPLACE(REPLACE(STR(?classe), "^.*[#/]", ""), "_", " ") AS ?nomClean)
    BIND(REPLACE(REPLACE(STR(?parent), "^.*[#/]", ""), "_", " ") AS ?parentClean)
} GROUP BY ?classe ORDER BY ?nom"""
            return sparql, "Liste de toutes les Classes de l'Ontologie (owl:Class)", \
                   "L'IA extrait toutes les classes et concepts définis dans l'ontologie avec leur classe parente éventuelle."

        # 6. Individus / Instances (owl:NamedIndividual)
        is_individuals = any(w in q_norm for w in [
            "tous les individus", "liste des individus", "quels sont les individus",
            "individus de l'ontologie", "tous les instances", "toutes les instances",
            "liste des instances", "instances de l'ontologie", "quelles sont les instances",
            "named individual", "namedindividual", "named individuals", "namedindividuals"
        ])
        if is_individuals:
            sparql = PREFIXES + """SELECT DISTINCT ?individu (SAMPLE(?nomClean) AS ?nom) (SAMPLE(?typeClean) AS ?role) (SAMPLE(?speVal) AS ?specialite) (SAMPLE(?emailVal) AS ?email) (SAMPLE(?telVal) AS ?telephone) WHERE {
    ?individu rdf:type ?t .
    FILTER(?t != owl:NamedIndividual && ?t != owl:Thing)
    FILTER(!isBlank(?individu))
    FILTER(!STRSTARTS(STR(?individu), "http://www.w3.org/2002/07/owl#"))
    OPTIONAL { ?individu :nom ?nomProp }
    OPTIONAL { ?individu :prenom ?prenomProp }
    OPTIONAL { ?individu rdfs:label ?labelProp }
    OPTIONAL { ?individu :specialite ?speVal }
    OPTIONAL { ?individu :email ?emailVal }
    OPTIONAL { ?individu :telephone ?telVal }
    BIND(COALESCE(
        IF(BOUND(?prenomProp) && BOUND(?nomProp) && !CONTAINS(LCASE(STR(?nomProp)), LCASE(STR(?prenomProp))), CONCAT(?prenomProp, " ", ?nomProp), ?nomProp),
        ?nomProp, ?labelProp,
        REPLACE(REPLACE(STR(?individu), "^.*[#/]", ""), "_", " ")
    ) AS ?nomClean)
    BIND(REPLACE(REPLACE(STR(?t), "^.*[#/]", ""), "_", " ") AS ?typeClean)
} GROUP BY ?individu ORDER BY ?nomClean"""
            return sparql, "Tous les Individus et Instances de l'Ontologie", \
                   "L'IA extrait toutes les instances instanciées (NamedIndividuals) avec leur type rdf:type respectif."

        # 7. Annotations (rdfs:comment, rdfs:label, owl:AnnotationProperty)
        is_annotations = any(w in q_norm for w in [
            "annotation", "annotations", "annotationproperty", "annotationproperties",
            "annotation property", "annotation properties", "commentaires", "commentaire",
            "rdfs:comment", "rdfs:label", "labels de l'ontologie", "documentation de l'ontologie",
            "quelles sont les annotations", "toutes les annotations"
        ])
        if is_annotations:
            sparql = PREFIXES + """SELECT DISTINCT ?entite (SAMPLE(?nomEntite) AS ?nom) (SAMPLE(?propClean) AS ?typeAnnotation) (SAMPLE(?valeur) AS ?valeurAnnotation) WHERE {
    ?entite ?prop ?valeur .
    FILTER(?prop IN (rdfs:comment, rdfs:label, rdfs:isDefinedBy, rdfs:seeAlso, owl:versionInfo))
    FILTER(!isBlank(?entite))
    FILTER(!STRSTARTS(STR(?entite), "http://www.w3.org/2002/07/owl#"))
    BIND(REPLACE(REPLACE(STR(?entite), "^.*[#/]", ""), "_", " ") AS ?nomEntite)
    BIND(REPLACE(REPLACE(STR(?prop), "^.*[#/]", ""), "_", " ") AS ?propClean)
} GROUP BY ?entite ?prop ORDER BY ?nomEntite LIMIT 40"""
            return sparql, "Annotations de l'Ontologie (rdfs:comment, rdfs:label)", \
                   "L'IA extrait les métadonnées et annotations textuelles associées aux entités de l'ontologie."

        # ============================================================
        # PRIORITÉ 0.5 : Filtre DYNAMIQUE par Spécialité (ANY keyword)
        # Détecte "spécialité X", "spécialiste en X", "pour spécialité X"
        # et génère un SPARQL avec FILTER(CONTAINS(LCASE(?specialite), ...)).
        # Fonctionne avec TOUTE valeur : Cardiologie, Cardiologue, Pédiatrie...
        # ============================================================
        _SPECIALITE_TRIGGERS = [
            r"(?:specialite|specialiste)\s+(?:en\s+|de\s+|d[eu]\s+)?([a-z]{4,})",
            r"pour\s+(?:la\s+)?specialite\s+([a-z]{4,})",
            r"(?:specialite|specialiste)\s*[=:]\s*([a-z]{4,})",
            r"(?:qui\s+)?(?:a|ont)\s+(?:pour|la)\s+specialite\s+([a-z]{4,})",
            r"(?:de|en)\s+specialite\s+([a-z]{4,})",
        ]
        _SPE_EXCLUDE = {"medecin", "medecins", "docteur", "patient", "personne",
                        "qui", "quel", "quels", "quelles", "liste", "tous", "toutes", "dans", "avec"}
        detected_spe = None
        for pat in _SPECIALITE_TRIGGERS:
            m_spe = re.search(pat, q_norm)
            if m_spe:
                candidate = m_spe.group(1).strip()
                if len(candidate) >= 4 and candidate not in _SPE_EXCLUDE:
                    detected_spe = candidate
                    break
        if detected_spe:
            # Normalise : 'cardiologie' et 'cardiologue' → same search root 'cardio'
            # On cherche le préfixe commun (5 chars suffisants pour être sélectif)
            spe_root = detected_spe[:min(6, len(detected_spe))]
            sparql = PREFIXES + f"""SELECT ?medecin (SAMPLE(?nomDisplay) AS ?nom) (SAMPLE(?ageVal) AS ?age) (SAMPLE(?speVal) AS ?specialite) (SAMPLE(?telVal) AS ?telephone) (SAMPLE(?cinVal) AS ?cin) WHERE {{
    ?medecin rdf:type ?t .
    ?t rdfs:subClassOf* :Personne .
    OPTIONAL {{ ?medecin :nom ?nomProp }}
    OPTIONAL {{ ?medecin :prenom ?prenomProp }}
    OPTIONAL {{ ?medecin rdfs:label ?labelProp }}
    OPTIONAL {{ ?medecin :specialite ?speVal }}
    OPTIONAL {{ ?medecin :age ?ageVal }}
    OPTIONAL {{ ?medecin :telephone ?telVal }}
    OPTIONAL {{ ?medecin :numeroCIN ?cinVal }}
    BIND(COALESCE(
        IF(BOUND(?prenomProp) && BOUND(?nomProp) && !CONTAINS(LCASE(STR(?nomProp)), LCASE(STR(?prenomProp))), CONCAT(?prenomProp, " ", ?nomProp), ?nomProp),
        ?nomProp, ?labelProp,
        REPLACE(REPLACE(STR(?medecin), "^.*[#/]", ""), "_", " ")
    ) AS ?nomDisplay)
    FILTER(
        CONTAINS(LCASE(COALESCE(STR(?speVal), "")), "{spe_root}") ||
        CONTAINS(LCASE(STR(?t)), "{spe_root}")
    )
}} GROUP BY ?medecin"""
            return sparql, f"Personnes avec la spécialité '{detected_spe}'", \
                   f"L'IA a détecté le filtre de spécialité '{{spe_root}}' et génère un FILTER(CONTAINS(?specialite,...)) dynamique sur toute l'ontologie."

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

            # --- Supérieur ou égal : ">= X", "au moins X", "X ans et plus", "X ans ou plus"
            m_gte = (re.search(r'>=\s*(\d+)', q_norm)
                     or re.search(r'au\s+moins\s+(\d+)', q_norm)
                     or re.search(r'(\d+)\s*ans?\s*(?:et|ou)\s*plus', q_norm))
            # --- Supérieur strict : "> X", "plus de X", "superieur a X"
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

            # --- Inférieur ou égal : "<= X", "au plus X", "maximum X", "X ans et moins"
            m_lte = (re.search(r'<=\s*(\d+)', q_norm)
                     or re.search(r'au\s+plus\s+(\d+)', q_norm)
                     or re.search(r'maximum\s+(\d+)', q_norm)
                     or re.search(r'(\d+)\s*ans?\s*(?:et|ou)\s*moins', q_norm))
            # --- Inférieur strict : "< X", "moins de X", "inferieur a X"
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
        # PRIORITÉ 0.8 : Urgences / Service (doit précéder les noms candidats)
        # ============================================================
        if any(w in q_norm for w in ["urgence", "urgences", "service urgence"]):
            sparql = PREFIXES + """SELECT DISTINCT ?personne (SAMPLE(?nomClean) AS ?nom) (SAMPLE(?speVal) AS ?specialite) (SAMPLE(?telVal) AS ?telephone) WHERE {
    { ?personne :appartientA :Service_Urgences . }
    UNION
    { ?personne :appartient_à :Service_Urgences . }
    OPTIONAL { ?personne :nom ?nomProp }
    OPTIONAL { ?personne :prenom ?prenomProp }
    OPTIONAL { ?personne rdfs:label ?labelProp }
    OPTIONAL { ?personne :specialite ?speVal }
    OPTIONAL { ?personne :telephone ?telVal }
    BIND(COALESCE(
        IF(BOUND(?prenomProp) && BOUND(?nomProp) && !CONTAINS(LCASE(STR(?nomProp)), LCASE(STR(?prenomProp))), CONCAT(?prenomProp, " ", ?nomProp), ?nomProp),
        ?nomProp, ?labelProp,
        REPLACE(REPLACE(STR(?personne), "^.*[#/]", ""), "_", " ")
    ) AS ?nomClean)
} GROUP BY ?personne"""
            return sparql, "Personnes rattachées au Service des Urgences", \
                   "L'IA a filtré les individus via la propriété appartientA et l'individu Service_Urgences."

        if "service" in q_norm and any(w in q_norm for w in ["cardio", "cardiologie"]):
            sparql = PREFIXES + """SELECT DISTINCT ?personne (SAMPLE(?nomClean) AS ?nom) (SAMPLE(?speVal) AS ?specialite) (SAMPLE(?telVal) AS ?telephone) WHERE {
    { ?personne :appartientA :Service_Cardio . }
    UNION
    { ?personne :appartient_à :Service_Cardio . }
    OPTIONAL { ?personne :nom ?nomProp }
    OPTIONAL { ?personne :prenom ?prenomProp }
    OPTIONAL { ?personne rdfs:label ?labelProp }
    OPTIONAL { ?personne :specialite ?speVal }
    OPTIONAL { ?personne :telephone ?telVal }
    BIND(COALESCE(
        IF(BOUND(?prenomProp) && BOUND(?nomProp) && !CONTAINS(LCASE(STR(?nomProp)), LCASE(STR(?prenomProp))), CONCAT(?prenomProp, " ", ?nomProp), ?nomProp),
        ?nomProp, ?labelProp,
        REPLACE(REPLACE(STR(?personne), "^.*[#/]", ""), "_", " ")
    ) AS ?nomClean)
} GROUP BY ?personne"""
            return sparql, "Personnes rattachées au Service de Cardiologie", \
                   "L'IA a filtré les individus via la propriété appartientA et l'individu Service_Cardio."

        # ============================================================
        # PRIORITÉ 0.85 : Recherche de dossier médical d'un individu spécifique
        # ============================================================
        # PRIORITÉ 0.85 : RECHERCHE DYNAMIQUE de dossier médical par nom
        # Fonctionne pour TOUT nom sans restriction statique
        # ============================================================
        m_dos_nom = re.search(r'\bdossier\s+(?:de|du\s+patient|pour)\s+([a-zA-Z]{3,})\b', q_norm)
        if m_dos_nom:
            nom_dos_target = m_dos_nom.group(1).strip().lower()
            # Recherche 100% dynamique : cherche dans toute l'ontologie par nom ou URI
            sparql = PREFIXES + f"""SELECT ?patient (SAMPLE(?nomDisplay) AS ?nom) (SAMPLE(?dosVal) AS ?dossier) (SAMPLE(?sangVal) AS ?groupeSanguin) (SAMPLE(?ageVal) AS ?age) (SAMPLE(?telVal) AS ?telephone) (SAMPLE(?typeClean) AS ?role) WHERE {{
    ?patient rdf:type ?typeVal .
    ?typeVal rdfs:subClassOf* :Personne .
    ?patient :numeroDossier ?dosVal .
    FILTER(?typeVal != <http://www.w3.org/2002/07/owl#NamedIndividual>)
    OPTIONAL {{ ?patient :nom ?nomProp }}
    OPTIONAL {{ ?patient :prenom ?prenomProp }}
    OPTIONAL {{ ?patient rdfs:label ?labelProp }}
    OPTIONAL {{ ?patient :groupeSanguin ?sangVal }}
    OPTIONAL {{ ?patient :age ?ageVal }}
    OPTIONAL {{ ?patient :telephone ?telVal }}
    BIND(COALESCE(
        IF(BOUND(?prenomProp) && BOUND(?nomProp) && !CONTAINS(LCASE(STR(?nomProp)), LCASE(STR(?prenomProp))), CONCAT(?prenomProp, " ", ?nomProp), ?nomProp),
        ?nomProp, ?labelProp,
        REPLACE(REPLACE(STR(?patient), "^.*[#/]", ""), "_", " ")
    ) AS ?nomDisplay)
    BIND(REPLACE(REPLACE(STR(?typeVal), "^.*[#/]", ""), "_", " ") AS ?typeClean)
    FILTER(CONTAINS(LCASE(STR(?nomDisplay)), "{nom_dos_target}") || CONTAINS(LCASE(STR(?patient)), "{nom_dos_target}"))
}} GROUP BY ?patient"""
            return sparql, f"Dossier médical de '{nom_dos_target.capitalize()}'", \
                   f"L'IA extrait dynamiquement le dossier de '{nom_dos_target.capitalize()}' depuis l'ontologie."

        # ============================================================
        # PRIORITÉ 0.9 : RECHERCHE D'INDIVIDUS PAR ATTRIBUT / IDENTIFIANT (100% DYNAMIQUE)
        # Gère : Numéro d'ordre (MED-003...), Numéro de dossier (PAT-001...),
        # CIN (00678901...), Email, Téléphone, Groupe Sanguin.
        # ============================================================

        # 1. Numéro d'Ordre (MED-xxx ou "numéro d'ordre MED-003")
        m_ord = re.search(r'\b(med-\d+)\b', q_norm) or re.search(
            r'\b(?:numero\s+d[\'\s]*ordre|num[°o\s]*d[\'\s]*ordre|numero\s+ordre)\b\s*(?:=|est|a|de|:)?\s*([a-zA-Z0-9\-]+)', q_norm
        )
        if m_ord:
            ord_val = m_ord.group(1).strip().upper()
            sparql = PREFIXES + f"""SELECT ?individu (SAMPLE(?nomDisplay) AS ?nom) (SAMPLE(?typeVal) AS ?role) (SAMPLE(?speVal) AS ?specialite) (SAMPLE(?emailVal) AS ?email) (SAMPLE(?cinVal) AS ?cin) (SAMPLE(?telVal) AS ?telephone) (SAMPLE(?ageVal) AS ?age) (SAMPLE(?ordVal) AS ?numeroOrdre) WHERE {{
    ?individu rdf:type/rdfs:subClassOf* :Medecin .
    ?individu rdf:type ?typeVal .
    ?individu :numeroOrdre ?ordVal .
    OPTIONAL {{ ?individu :nom ?nomProp }}
    OPTIONAL {{ ?individu :prenom ?prenomProp }}
    OPTIONAL {{ ?individu rdfs:label ?labelProp }}
    OPTIONAL {{ ?individu :specialite ?speVal }}
    OPTIONAL {{ ?individu :email ?emailVal }}
    OPTIONAL {{ ?individu :numeroCIN ?cinVal }}
    OPTIONAL {{ ?individu :telephone ?telVal }}
    OPTIONAL {{ ?individu :age ?ageVal }}
    BIND(COALESCE(
        IF(BOUND(?prenomProp) && BOUND(?nomProp) && !CONTAINS(LCASE(STR(?nomProp)), LCASE(STR(?prenomProp))), CONCAT(?prenomProp, " ", ?nomProp), ?nomProp),
        ?nomProp, ?labelProp,
        REPLACE(REPLACE(STR(?individu), "^.*[#/]", ""), "_", " ")
    ) AS ?nomDisplay)
    FILTER(CONTAINS(UCASE(STR(?ordVal)), "{ord_val}"))
    FILTER(?typeVal != <http://www.w3.org/2002/07/owl#NamedIndividual>)
}} GROUP BY ?individu"""
            return sparql, f"Médecin avec le numéro d'ordre '{ord_val}'", \
                   f"L'IA a extrait dynamiquement le filtre sur le numéro d'ordre (med:numeroOrdre = '{ord_val}')."

        # 2. Numéro de Dossier (PAT-xxx ou "numéro de dossier PAT-001")
        m_dos = re.search(r'\b(pat-\d+)\b', q_norm)
        if not m_dos:
            m_dos_cand = re.search(
                r'\b(?:numero\s+de\s+dossier|num[°o\s]*dossier|numero\s+dossier)\b\s*(?:=|est|a|de|:)?\s*([a-zA-Z0-9\-]+)', q_norm
            ) or re.search(r'\bdossier\s*(?:=|est|:)\s*([a-zA-Z0-9\-]+)', q_norm)
            if m_dos_cand:
                cand_val = m_dos_cand.group(1).strip().upper()
                _DOS_EXCLUDE = {"SAMI", "AMINA", "ALI", "FATIMA", "AHMED", "KARIM", "PATIENT", "PATIENTS", "DE", "DU", "DES", "LE", "LA", "UN", "UNE"}
                if cand_val not in _DOS_EXCLUDE and (len(cand_val) >= 4 or cand_val.isdigit() or "-" in cand_val):
                    m_dos = m_dos_cand
        if m_dos:
            dos_val = m_dos.group(1).strip().upper()
            sparql = PREFIXES + f"""SELECT ?individu (SAMPLE(?nomDisplay) AS ?nom) (SAMPLE(?typeVal) AS ?role) (SAMPLE(?speVal) AS ?specialite) (SAMPLE(?emailVal) AS ?email) (SAMPLE(?cinVal) AS ?cin) (SAMPLE(?telVal) AS ?telephone) (SAMPLE(?ageVal) AS ?age) (SAMPLE(?dosVal) AS ?numeroDossier) WHERE {{
    ?individu rdf:type/rdfs:subClassOf* :Patient .
    ?individu rdf:type ?typeVal .
    ?individu :numeroDossier ?dosVal .
    OPTIONAL {{ ?individu :nom ?nomProp }}
    OPTIONAL {{ ?individu :prenom ?prenomProp }}
    OPTIONAL {{ ?individu rdfs:label ?labelProp }}
    OPTIONAL {{ ?individu :specialite ?speVal }}
    OPTIONAL {{ ?individu :email ?emailVal }}
    OPTIONAL {{ ?individu :numeroCIN ?cinVal }}
    OPTIONAL {{ ?individu :telephone ?telVal }}
    OPTIONAL {{ ?individu :age ?ageVal }}
    BIND(COALESCE(
        IF(BOUND(?prenomProp) && BOUND(?nomProp) && !CONTAINS(LCASE(STR(?nomProp)), LCASE(STR(?prenomProp))), CONCAT(?prenomProp, " ", ?nomProp), ?nomProp),
        ?nomProp, ?labelProp,
        REPLACE(REPLACE(STR(?individu), "^.*[#/]", ""), "_", " ")
    ) AS ?nomDisplay)
    FILTER(CONTAINS(UCASE(STR(?dosVal)), "{dos_val}"))
    FILTER(?typeVal != <http://www.w3.org/2002/07/owl#NamedIndividual>)
}} GROUP BY ?individu"""
            return sparql, f"Patient avec le numéro de dossier '{dos_val}'", \
                   f"L'IA a extrait dynamiquement le filtre sur le numéro de dossier (med:numeroDossier = '{dos_val}')."

        # 3. CIN (Numéro d'identité nationale avec \b obligatoire pour ne pas capturer le mot 'medecin')
        m_cin = re.search(r'\b(?:cin|numero\s+cin|n[°o\s]*cin)\b\s*(?:=|est|a|de|:)?\s*([0-9a-zA-Z]+)', q_norm)
        if not m_cin:
            m_cin = re.search(r'\b(\d{8})\b', q_norm)
        if m_cin:
            cin_val = m_cin.group(1).strip()
            _CIN_EXCLUDE = {"medecin", "medecins", "patient", "patients", "stagiaire", "stagiaires", "s", "generaliste", "specialiste", "de", "le", "la", "les", "un", "une", "des"}
            if cin_val.lower() not in _CIN_EXCLUDE and (len(cin_val) >= 4 or cin_val.isdigit()):
                if any(w in q_norm for w in ["medecin", "medecins", "docteur", "dr"]):
                    role_filter = "?individu rdf:type/rdfs:subClassOf* :Medecin .\n    "
                    role_label = "Médecin"
                elif any(w in q_norm for w in ["patient", "patients"]):
                    role_filter = "?individu rdf:type/rdfs:subClassOf* :Patient .\n    "
                    role_label = "Patient"
                elif any(w in q_norm for w in ["stagiaire", "stagiaires"]):
                    role_filter = "?individu rdf:type/rdfs:subClassOf* :Stagiaire .\n    "
                    role_label = "Stagiaire"
                else:
                    role_filter = ""
                    role_label = "Individu"

                sparql = PREFIXES + f"""SELECT ?individu (SAMPLE(?nomDisplay) AS ?nom) (SAMPLE(?typeVal) AS ?role) (SAMPLE(?speVal) AS ?specialite) (SAMPLE(?emailVal) AS ?email) (SAMPLE(?cinVal) AS ?cin) (SAMPLE(?telVal) AS ?telephone) (SAMPLE(?ageVal) AS ?age) WHERE {{
    {role_filter}?individu rdf:type ?typeVal .
    ?typeVal rdfs:subClassOf* :Personne .
    ?individu :numeroCIN ?cinVal .
    OPTIONAL {{ ?individu :nom ?nomProp }}
    OPTIONAL {{ ?individu :prenom ?prenomProp }}
    OPTIONAL {{ ?individu rdfs:label ?labelProp }}
    OPTIONAL {{ ?individu :specialite ?speVal }}
    OPTIONAL {{ ?individu :email ?emailVal }}
    OPTIONAL {{ ?individu :telephone ?telVal }}
    OPTIONAL {{ ?individu :age ?ageVal }}
    BIND(COALESCE(
        IF(BOUND(?prenomProp) && BOUND(?nomProp) && !CONTAINS(LCASE(STR(?nomProp)), LCASE(STR(?prenomProp))), CONCAT(?prenomProp, " ", ?nomProp), ?nomProp),
        ?nomProp, ?labelProp,
        REPLACE(REPLACE(STR(?individu), "^.*[#/]", ""), "_", " ")
    ) AS ?nomDisplay)
    FILTER(CONTAINS(STR(?cinVal), "{cin_val}"))
    FILTER(?typeVal != <http://www.w3.org/2002/07/owl#NamedIndividual>)
}} GROUP BY ?individu"""
                return sparql, f"{role_label} avec le CIN '{cin_val}'", \
                       f"L'IA a extrait dynamiquement le filtre sur le numéro CIN (med:numeroCIN = '{cin_val}')."

        # 4. Email
        m_email = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', q_norm) or re.search(
            r'\b(?:email|e-mail|mail|courriel)\b\s*(?:=|est|a|de|:)?\s*(\S+)', q_norm
        )
        if m_email:
            email_val = m_email.group(1).strip().lower()
            sparql = PREFIXES + f"""SELECT ?individu (SAMPLE(?nomDisplay) AS ?nom) (SAMPLE(?typeVal) AS ?role) (SAMPLE(?speVal) AS ?specialite) (SAMPLE(?emailVal) AS ?email) (SAMPLE(?cinVal) AS ?cin) (SAMPLE(?telVal) AS ?telephone) (SAMPLE(?ageVal) AS ?age) WHERE {{
    ?individu rdf:type ?typeVal .
    ?typeVal rdfs:subClassOf* :Personne .
    ?individu :email ?emailVal .
    OPTIONAL {{ ?individu :nom ?nomProp }}
    OPTIONAL {{ ?individu :prenom ?prenomProp }}
    OPTIONAL {{ ?individu rdfs:label ?labelProp }}
    OPTIONAL {{ ?individu :specialite ?speVal }}
    OPTIONAL {{ ?individu :numeroCIN ?cinVal }}
    OPTIONAL {{ ?individu :telephone ?telVal }}
    OPTIONAL {{ ?individu :age ?ageVal }}
    BIND(COALESCE(
        IF(BOUND(?prenomProp) && BOUND(?nomProp) && !CONTAINS(LCASE(STR(?nomProp)), LCASE(STR(?prenomProp))), CONCAT(?prenomProp, " ", ?nomProp), ?nomProp),
        ?nomProp, ?labelProp,
        REPLACE(REPLACE(STR(?individu), "^.*[#/]", ""), "_", " ")
    ) AS ?nomDisplay)
    FILTER(CONTAINS(LCASE(STR(?emailVal)), "{email_val}"))
    FILTER(?typeVal != <http://www.w3.org/2002/07/owl#NamedIndividual>)
}} GROUP BY ?individu"""
            return sparql, f"Individu avec l'email '{email_val}'", \
                   f"L'IA a extrait dynamiquement le filtre sur l'adresse email (med:email = '{email_val}')."

        # ============================================================
        # PRIORITÉ 1.0 : RECHERCHE DYNAMIQUE d'individus par nom
        # Remplace tous les blocs statiques (Fatima, Sami, Ahmed, Karim,
        # Amina, Ali...) — cherche dans TOUTE l'ontologie par nom/URI.
        # Fonctionne pour n'importe quel individu présent dans l'OWL.
        # ============================================================
        _INDIVIDU_EXCLUSIONS = ["soigne", "soin", "traite", "affecte", "connait",
                                 "urgence", "urgences", "service", "tous", "toutes",
                                 "liste", "combien", "nombre"]
        # Mots courts potentiellement confondus avec des noms (à exclure)
        _SHORT_EXCLUSIONS = {"ali"}  # garder pour regex \bali\b seulement
        # Détecter un nom propre candidat isolé dans la question
        # On cherche un mot de 3+ lettres qui n'est pas un mot-outil
        _INDIVIDU_STOP = {
            "donne", "donner", "donnez", "moi", "nous", "lui", "les", "des", "une", "qui",
            "quel", "quels", "quelles", "quelle", "liste", "tous", "toutes", "trouve",
            "cherche", "affiche", "montre", "patient", "patients", "patiente", "patientes",
            "medecin", "medecins", "medecine", "docteur", "docteurs", "docteure", "doctoresse",
            "infos", "info", "fiche", "profil", "detail", "details",
            "coordonnees", "coordonnee", "informations", "information", "age", "ans",
            "telephone", "email", "cin", "dossier", "groupe", "sanguin", "stagiaire", "stagiaires",
            "generaliste", "generalistes", "specialiste", "specialistes", "cardiologue", "cardiologues", "urgence", "urgences", "service", "services",
            "soigne", "soin", "traite", "affecte", "connait", "dans", "pour", "avec",
            "sur", "par", "vers", "aux", "son", "ses", "leur", "leurs", "est", "sont",
            "avoir", "etre", "ont", "peux", "peut", "merci", "bonjour",
            "enfant", "enfants", "adulte", "adultes", "hopital", "trier", "trie",
            "classe", "classer", "classes", "croissant", "decroissant", "collegues",
            "collegue", "symptomes", "symptome", "maladie", "maladies", "medicament",
            "medicaments", "ordonnance", "consultation", "operation", "sous", "sousclasse", "sousclasses",
            "stuff", "staff", "medical", "medicals", "medicale", "medicales",
            "agent", "agents", "hospitalier", "hospitaliers", "ash",
            "soignant", "soignants", "soignante", "soignantes", "aide", "aides",
            "sage", "sages", "femme", "femmes",
            "chef", "chefs", "technique", "techniques", "medico",
            "kine", "kines", "kinesitherapeute", "kinesitherapeutes",
            "secretaire", "secretaires",
            "infirmier", "infirmiers", "infirmiere", "infirmieres", "infirmerie",
            "dermatologue", "dermatologues", "anesthesiste", "anesthesistes",
            "endocrinologue", "endocrinologues", "psychiatre", "psychiatres",
            "gastro", "gastroenterologue", "neurologue", "neurologues",
            "pneumologue", "pneumologues", "role", "roles"
        }
        # Extraire les candidats noms propres (avant la recherche générique Priorité 1.2)
        _early_words = re.findall(r'\b([a-z]{3,})\b', q_norm)
        _early_candidates = [w for w in _early_words if w not in _INDIVIDU_STOP]
        _is_early_relation = any(w in q_norm for w in ["soigne", "soin", "traite", "affecte", "connait"])
        _is_early_list = any(w in q_norm for w in ["tous", "toutes", "liste", "combien", "nombre"])
        _is_early_service = any(w in q_norm for w in ["urgence", "urgences", "service"])

        if (_early_candidates
                and not _is_early_relation
                and not _is_early_list
                and not _is_early_service):
            # Construire les filtres CONTAINS pour chaque token du nom
            _early_filters = []
            for token in _early_candidates:
                _early_filters.append(
                    f'(CONTAINS(LCASE(STR(?nomDisplay)), "{token}") || '
                    f'CONTAINS(LCASE(STR(?individu)), "{token}"))'
                )
            _early_filter_str = " && ".join(_early_filters)
            _early_names_display = " ".join([c.capitalize() for c in _early_candidates])

            sparql = PREFIXES + f"""SELECT ?individu (SAMPLE(?nomDisplay) AS ?nom) (SAMPLE(?typeClean) AS ?role) (SAMPLE(?speVal) AS ?specialite) (SAMPLE(?emailVal) AS ?email) (SAMPLE(?cinVal) AS ?cin) (SAMPLE(?telVal) AS ?telephone) (SAMPLE(?ageVal) AS ?age) (SAMPLE(?dosVal) AS ?dossier) (SAMPLE(?sangVal) AS ?groupeSanguin) (SAMPLE(?ordVal) AS ?numeroOrdre) WHERE {{
    ?individu rdf:type ?typeVal .
    ?typeVal rdfs:subClassOf* :Personne .
    FILTER(?typeVal != <http://www.w3.org/2002/07/owl#NamedIndividual>)
    OPTIONAL {{ ?individu :nom ?nomProp }}
    OPTIONAL {{ ?individu :prenom ?prenomProp }}
    OPTIONAL {{ ?individu rdfs:label ?labelProp }}
    OPTIONAL {{ ?individu :specialite ?speVal }}
    OPTIONAL {{ ?individu :email ?emailVal }}
    OPTIONAL {{ ?individu :numeroCIN ?cinVal }}
    OPTIONAL {{ ?individu :telephone ?telVal }}
    OPTIONAL {{ ?individu :age ?ageVal }}
    OPTIONAL {{ ?individu :numeroDossier ?dosVal }}
    OPTIONAL {{ ?individu :groupeSanguin ?sangVal }}
    OPTIONAL {{ ?individu :numeroOrdre ?ordVal }}
    BIND(COALESCE(
        IF(BOUND(?prenomProp) && BOUND(?nomProp) && !CONTAINS(LCASE(STR(?nomProp)), LCASE(STR(?prenomProp))), CONCAT(?prenomProp, " ", ?nomProp), ?nomProp),
        ?nomProp, ?labelProp,
        REPLACE(REPLACE(STR(?individu), "^.*[#/]", ""), "_", " ")
    ) AS ?nomDisplay)
    BIND(REPLACE(REPLACE(STR(?typeVal), "^.*[#/]", ""), "_", " ") AS ?typeClean)
    FILTER({_early_filter_str})
}} GROUP BY ?individu"""
            return sparql, f"Recherche de '{_early_names_display}' dans l'ontologie", \
                   f"L'IA extrait dynamiquement tout individu correspondant au nom '{_early_names_display}' dans l'ensemble de l'ontologie (aucune restriction de type)."

        # ============================================================
        # PRIORITÉ 1.2 : Individus spécifiques recherchés par nom (DYNAMIQUE)
        # On détecte un prénom/nom isolé dans la question et on cherche
        # dynamiquement dans toute l'ontologie — pour tout nouvel individu.
        # ============================================================
        # Mots à exclure pour ne pas confondre avec des noms propres
        _STOP_WORDS = {
            "tous", "toutes", "liste", "donne", "donnez", "donner", "affiche", "afficher",
            "montre", "montrer", "trouve", "trouver", "cherche", "chercher", "recherche",
            "rechercher", "quels", "quelles", "qui", "quel", "quelle", "les", "des",
            "patient", "patients", "medecin", "medecins", "docteur", "docteurs", "dr",
            "professeur", "prof", "pr", "soin", "soins", "soigne", "soignent", "moi",
            "nous", "lui", "eux", "elle", "traitement", "avec", "sans", "dans", "pour",
            "sur", "par", "vers", "voir", "generaliste", "generalistes", "specialiste",
            "specialistes", "cardiologue", "cardiologues", "stagiaire", "stagiaires",
            "info", "infos", "information", "informations", "fiche", "profil", "compte",
            "detail", "details", "personne", "personnes", "individu", "individus",
            "utilisateur", "utilisateurs", "age", "ages", "ans", "annee", "annees",
            "groupe", "sang", "sanguin", "dossier", "cin", "tel", "telephone",
            "numero", "numeros", "num", "ordre", "code", "codes", "valeur", "attribut",
            "adresse", "urgence", "urgences", "service", "services", "adulte", "adultes",
            "enfant", "enfants", "symptome", "symptomes", "hierarchie", "est", "sont",
            "etre", "avoir", "ont", "a", "une", "un", "son", "sa", "ses", "leur", "leurs",
            "mon", "ma", "mes", "ton", "ta", "tes", "notre", "nos", "votre", "vos",
            "trier", "triage", "trie", "tri", "classer", "classe", "ordonner", "ordre",
            "croissant", "decroissant", "groupesanguin", "specialite", "specialites",
            "nom", "prenom", "nomme", "nommee", "nomment", "appelle", "appele", "appelee",
            "peux", "peut", "pouvez", "merci", "bonjour", "salut",
            "stuff", "staff", "medical", "medicals", "medicale", "medicales",
            "agent", "agents", "hospitalier", "hospitaliers", "ash",
            "infirmier", "infirmiere", "infirmiers", "infirmieres", "infirmerie",
            "aide", "aides", "soignant", "soignants", "soignante", "soignantes",
            "sage", "sages", "femme", "femmes", "kine", "kines", "kinesitherapeute", "kinesitherapeutes",
            "secretaire", "secretaires", "chef", "chefs", "technicien", "techniciens", "technique", "techniques", "medico",
            "dermatologue", "dermatologues", "anesthesiste", "anesthesistes",
            "endocrinologue", "endocrinologues", "psychiatre", "psychiatres",
            "gastro", "gastroenterologue", "neurologue", "neurologues", "pneumologue", "pneumologues",
            "role", "roles",
            "travaille", "travaillent", "travail", "travaillant", "aux", "au", "en", "combien", "nombre", "total",
            "compter", "quantite", "enregistre", "enregistres", "enregistree", "enregistrees", "ontologie", "graphe", "base"
        }
        # Extraire les mots de 3+ lettres qui ressemblent à des noms propres
        words_in_question = re.findall(r'\b([a-z]{3,})\b', q_norm)
        candidate_names = [
            w for w in words_in_question
            if w not in _STOP_WORDS
            and not any(w in sw for sw in ["soigne", "affecte", "traite", "connait", "urgence", "service"])
        ]
        _RELATION_WORDS = ["soigne", "soin", "traite", "affecte", "connait"]
        is_relation_query = any(w in q_norm for w in _RELATION_WORDS)
        is_sort_query = bool(re.search(r'\b(triage|tri|trie|trier|classer|classe|ordonner|ordre)\b', q_norm))
        is_service_query = any(w in q_norm for w in ["urgence", "urgences", "service"])

        if candidate_names and not is_relation_query and not is_sort_query and not is_service_query:
            # Détection du rôle mentionné pour l'affichage seulement
            # La recherche SPARQL est toujours faite sur TOUTE l'ontologie (:Personne)
            # pour être 100% dynamique (aucune restriction codée en dur par type).
            if any(w in q_norm for w in ["medecin", "medecins", "docteur", "docteurs", "dr"]):
                role_lbl = "Médecin"
            elif any(w in q_norm for w in ["patient", "patients"]):
                role_lbl = "Patient"
            elif any(w in q_norm for w in ["stagiaire", "stagiaires"]):
                role_lbl = "Stagiaire"
            elif any(w in q_norm for w in ["cardiologue", "cardiologues"]):
                role_lbl = "Cardiologue"
            elif any(w in q_norm for w in ["generaliste", "generalistes"]):
                role_lbl = "Médecin Généraliste"
            elif any(w in q_norm for w in ["specialiste", "specialistes"]):
                role_lbl = "Médecin Spécialiste"
            else:
                role_lbl = "Personne"

            # Construction des filtres de recherche par nom (AND entre les tokens)
            # Chaque token doit apparaître dans le nom affiché, l'URI ou l'email
            filter_clauses = []
            for token in candidate_names:
                filter_clauses.append(
                    f'(CONTAINS(LCASE(STR(?nomDisplay)), "{token}") || '
                    f'CONTAINS(LCASE(STR(?individu)), "{token}") || '
                    f'CONTAINS(LCASE(COALESCE(STR(?emailVal), "")), "{token}"))'
                )
            filter_str = " && ".join(filter_clauses)

            # Requête SPARQL 100% dynamique : cherche dans TOUTE l'ontologie (:Personne)
            # Le rôle n'est pas une contrainte — n'importe quel individu peut être trouvé par son nom
            sparql = PREFIXES + f"""SELECT ?individu (SAMPLE(?nomDisplay) AS ?nom) (SAMPLE(?typeClean) AS ?role) (SAMPLE(?speVal) AS ?specialite) (SAMPLE(?emailVal) AS ?email) (SAMPLE(?cinVal) AS ?cin) (SAMPLE(?telVal) AS ?telephone) (SAMPLE(?ageVal) AS ?age) WHERE {{
    ?individu rdf:type ?typeVal .
    ?typeVal rdfs:subClassOf* :Personne .
    FILTER(?typeVal != <http://www.w3.org/2002/07/owl#NamedIndividual>)
    OPTIONAL {{ ?individu :nom ?nomProp }}
    OPTIONAL {{ ?individu :prenom ?prenomProp }}
    OPTIONAL {{ ?individu rdfs:label ?labelProp }}
    OPTIONAL {{ ?individu :specialite ?speVal }}
    OPTIONAL {{ ?individu :email ?emailVal }}
    OPTIONAL {{ ?individu :numeroCIN ?cinVal }}
    OPTIONAL {{ ?individu :telephone ?telVal }}
    OPTIONAL {{ ?individu :age ?ageVal }}
    BIND(COALESCE(
        IF(BOUND(?prenomProp) && BOUND(?nomProp) && !CONTAINS(LCASE(STR(?nomProp)), LCASE(STR(?prenomProp))), CONCAT(?prenomProp, " ", ?nomProp), ?nomProp),
        ?nomProp, ?labelProp,
        REPLACE(REPLACE(STR(?individu), "^.*[#/]", ""), "_", " ")
    ) AS ?nomDisplay)
    BIND(REPLACE(REPLACE(STR(?typeVal), "^.*[#/]", ""), "_", " ") AS ?typeClean)
    FILTER({filter_str})
}} GROUP BY ?individu"""
            names_display = " ".join([c.capitalize() for c in candidate_names])
            return sparql, f"Recherche de '{names_display}' dans l'ontologie", \
                   f"L'IA a recherché dynamiquement toute personne correspondant au nom '{names_display}' dans l'ensemble de l'ontologie (aucune restriction de type)."

        # ============================================================
        # PRIORITÉ 1.3 : SOUS-CLASSES & RÔLES DYNAMIQUES
        # Recherche des individus de n'importe quelle sous-classe de Personne / Role / Stuff
        # (Agents_de_service_hospitalier, Stuff_Médicale, Aide_soignant, Sages-femmes,
        #  Chefs_de_service, Médico-techniques, Kinésithérapeutes, Secrétaires_médicales,
        #  Infirmiers, Cardiologues, Dermatologues, Stagiaires, etc.)
        # ============================================================
        q_sub_norm = q_norm.replace("_", " ")
        q_raw_norm = question.lower()
        for kw_list, cls_iri, label, pat in _PERSONNE_SUBCLASSES_REGISTRY:
            if any(k in q_norm or k in q_sub_norm or k in q_raw_norm for k in kw_list):
                sparql = PREFIXES + f"""SELECT DISTINCT ?individu (SAMPLE(?nomClean) AS ?nom) (SAMPLE(?typeClean) AS ?role) (SAMPLE(?speVal) AS ?specialite) (SAMPLE(?emailVal) AS ?email) (SAMPLE(?cinVal) AS ?cin) (SAMPLE(?telVal) AS ?telephone) (SAMPLE(?ageVal) AS ?age) (SAMPLE(?dosVal) AS ?dossier) (SAMPLE(?sangVal) AS ?groupeSanguin) (SAMPLE(?ordVal) AS ?numeroOrdre) WHERE {{
    {pat}
    OPTIONAL {{ ?individu med:nom ?nomProp }}
    OPTIONAL {{ ?individu med:prenom ?prenomProp }}
    OPTIONAL {{ ?individu rdfs:label ?labelProp }}
    OPTIONAL {{ ?individu med:specialite ?speVal }}
    OPTIONAL {{ ?individu med:email ?emailVal }}
    OPTIONAL {{ ?individu med:numeroCIN ?cinVal }}
    OPTIONAL {{ ?individu med:telephone ?telVal }}
    OPTIONAL {{ ?individu med:age ?ageVal }}
    OPTIONAL {{ ?individu med:numeroDossier ?dosVal }}
    OPTIONAL {{ ?individu med:groupeSanguin ?sangVal }}
    OPTIONAL {{ ?individu med:numeroOrdre ?ordVal }}
    OPTIONAL {{ ?individu rdf:type ?typeVal . FILTER(?typeVal != owl:NamedIndividual) }}
    BIND(COALESCE(
        IF(BOUND(?prenomProp) && BOUND(?nomProp) && !CONTAINS(LCASE(STR(?nomProp)), LCASE(STR(?prenomProp))), CONCAT(?prenomProp, " ", ?nomProp), ?nomProp),
        ?labelProp,
        REPLACE(REPLACE(STR(?individu), "^.*[#/]", ""), "_", " ")
    ) AS ?nomClean)
    BIND(REPLACE(REPLACE(STR(?typeVal), "^.*[#/]", ""), "_", " ") AS ?typeClean)
}} GROUP BY ?individu"""
                return sparql, f"Recherche de tous les {label}s", \
                       f"L'IA extrait dynamiquement tous les individus appartenant à la sous-classe ou au rôle '{label}' ({cls_iri}) dans l'ontologie."

        # ============================================================
        # PRIORITÉ 1.5 : Moteur Sémantique Générique (Filtres & Tri)
        # Permet de filtrer par CIN, Dossier, Groupe Sanguin, Tel, Nom,
        # et de trier dynamiquement (ORDER BY) sans coder chaque cas.
        # ============================================================
        generic_res = _build_generic_property_and_sort_query(q_norm, question)
        if generic_res is not None:
            return generic_res


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
        # PRIORITÉ 4 : Généraliste (DYNAMIQUE - lit l'ontologie en temps réel)
        # Inclut : rdf:type :MedecinGeneraliste OU toute sous-classe de :Medecin
        # qui n'est pas :MedecinSpecialiste ni :Cardiologue
        # ============================================================
        # ============================================================
        # PRIORITÉ 4 : Généraliste (DYNAMIQUE - lit l'ontologie en temps réel)
        # ============================================================
        if "generaliste" in q_norm or "généraliste" in q:
            sparql = PREFIXES + """SELECT ?medecin (SAMPLE(?nomDisplay) AS ?nom) (SAMPLE(?ageVal) AS ?age) (SAMPLE(?telVal) AS ?telephone) (SAMPLE(?typeVal) AS ?type) WHERE {
    {
        # Cas 1 : typé MedecinGeneraliste ou sous-classe
        ?medecin rdf:type ?typeVal .
        ?typeVal rdfs:subClassOf* :MedecinGeneraliste .
    } UNION {
        # Cas 2 : typé Medecin avec propriété specialite = Généraliste
        ?medecin rdf:type/rdfs:subClassOf* :Medecin .
        ?medecin :specialite ?spe .
        FILTER(regex(str(?spe), "general|général", "i"))
        BIND(:MedecinGeneraliste AS ?typeVal)
    } UNION {
        # Cas 3 : typé Medecin sans spécialité médicale restrictive
        ?medecin rdf:type :Medecin .
        BIND(:Medecin AS ?typeVal)
        FILTER NOT EXISTS { ?medecin rdf:type :MedecinSpecialiste }
        FILTER NOT EXISTS { ?medecin rdf:type :Cardiologue }
        FILTER NOT EXISTS { ?medecin rdf:type ?subSpe . ?subSpe rdfs:subClassOf :MedecinSpecialiste }
        FILTER NOT EXISTS { 
            ?medecin :specialite ?otherSpe . 
            FILTER(!regex(str(?otherSpe), "general|général", "i"))
        }
    }
    OPTIONAL { ?medecin :nom ?nomProp }
    OPTIONAL { ?medecin :prenom ?prenomProp }
    OPTIONAL { ?medecin rdfs:label ?labelProp }
    OPTIONAL { ?medecin :age ?ageVal }
    OPTIONAL { ?medecin :telephone ?telVal }
    BIND(COALESCE(
        IF(BOUND(?prenomProp) && BOUND(?nomProp) && !CONTAINS(LCASE(STR(?nomProp)), LCASE(STR(?prenomProp))), CONCAT(?prenomProp, " ", ?nomProp), ?nomProp),
        ?nomProp,
        ?labelProp,
        REPLACE(REPLACE(STR(?medecin), "^.*[#/]", ""), "_", " ")
    ) AS ?nomDisplay)
} GROUP BY ?medecin"""
            return sparql, "Recherche des Médecins Généralistes", \
                   "L'IA a extrait dynamiquement tous les Médecins Généralistes depuis l'ontologie (classes, sous-classes, spécialités et individus)."

        # ============================================================
        # PRIORITÉ 5 : Médecin générique
        # ============================================================
        if (any(w in q_norm for w in ["medecin", "médecin", "docteur"])
                and not any(w in q_norm for w in ["soigne", "patient", "connait", "connait"])):
            sparql = PREFIXES + """SELECT ?medecin (SAMPLE(?nomDisplay) AS ?nom) (SAMPLE(?ageVal) AS ?age) (SAMPLE(?speVal) AS ?specialite) (SAMPLE(?ordVal) AS ?numeroOrdre) (SAMPLE(?telVal) AS ?telephone) WHERE {
    ?medecin rdf:type/rdfs:subClassOf* :Medecin .
    OPTIONAL { ?medecin :nom ?nomProp }
    OPTIONAL { ?medecin :prenom ?prenomProp }
    OPTIONAL { ?medecin rdfs:label ?labelProp }
    OPTIONAL { ?medecin :age ?ageVal }
    OPTIONAL { ?medecin :specialite ?speVal }
    OPTIONAL { ?medecin :numeroOrdre ?ordVal }
    OPTIONAL { ?medecin :telephone ?telVal }
    BIND(COALESCE(
        IF(BOUND(?prenomProp) && BOUND(?nomProp) && !CONTAINS(LCASE(STR(?nomProp)), LCASE(STR(?prenomProp))), CONCAT(?prenomProp, " ", ?nomProp), ?nomProp),
        ?nomProp,
        ?labelProp,
        REPLACE(REPLACE(STR(?medecin), "^.*[#/]", ""), "_", " ")
    ) AS ?nomDisplay)
} GROUP BY ?medecin"""
            return sparql, "Recherche de tous les Médecins", \
                   "L'IA a sélectionné toutes les instances dont le rdf:type dérive de la classe Medecin."

        # ============================================================
        # PRIORITÉ 6 : Enfants / Adultes / Patients
        # ============================================================
        if "enfant" in q_norm:
            sparql = PREFIXES + """SELECT ?patient (SAMPLE(?nomDisplay) AS ?nom) (SAMPLE(?ageVal) AS ?age) (SAMPLE(?dosVal) AS ?dossier) (SAMPLE(?sangVal) AS ?groupeSanguin) WHERE {
    ?patient rdf:type/rdfs:subClassOf* :PatientEnfant .
    OPTIONAL { ?patient :nom ?nomProp }
    OPTIONAL { ?patient :prenom ?prenomProp }
    OPTIONAL { ?patient rdfs:label ?labelProp }
    OPTIONAL { ?patient :age ?ageVal }
    OPTIONAL { ?patient :numeroDossier ?dosVal }
    OPTIONAL { ?patient :groupeSanguin ?sangVal }
    BIND(COALESCE(
        IF(BOUND(?prenomProp) && BOUND(?nomProp) && !CONTAINS(LCASE(STR(?nomProp)), LCASE(STR(?prenomProp))), CONCAT(?prenomProp, " ", ?nomProp), ?nomProp),
        ?nomProp,
        ?labelProp,
        REPLACE(REPLACE(STR(?patient), "^.*[#/]", ""), "_", " ")
    ) AS ?nomDisplay)
} GROUP BY ?patient"""
            return sparql, "Recherche des Patients Enfants", \
                   "L'IA a ciblé la sous-classe PatientEnfant (disjointe de PatientAdulte)."

        if "adulte" in q_norm:
            sparql = PREFIXES + """SELECT ?patient (SAMPLE(?nomDisplay) AS ?nom) (SAMPLE(?ageVal) AS ?age) (SAMPLE(?dosVal) AS ?dossier) (SAMPLE(?sangVal) AS ?groupeSanguin) (SAMPLE(?cinVal) AS ?cin) WHERE {
    ?patient rdf:type/rdfs:subClassOf* :PatientAdulte .
    OPTIONAL { ?patient :nom ?nomProp }
    OPTIONAL { ?patient :prenom ?prenomProp }
    OPTIONAL { ?patient rdfs:label ?labelProp }
    OPTIONAL { ?patient :age ?ageVal }
    OPTIONAL { ?patient :numeroDossier ?dosVal }
    OPTIONAL { ?patient :groupeSanguin ?sangVal }
    OPTIONAL { ?patient :numeroCIN ?cinVal }
    BIND(COALESCE(
        IF(BOUND(?prenomProp) && BOUND(?nomProp) && !CONTAINS(LCASE(STR(?nomProp)), LCASE(STR(?prenomProp))), CONCAT(?prenomProp, " ", ?nomProp), ?nomProp),
        ?nomProp,
        ?labelProp,
        REPLACE(REPLACE(STR(?patient), "^.*[#/]", ""), "_", " ")
    ) AS ?nomDisplay)
} GROUP BY ?patient"""
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
        # PRIORITÉ 11 : Stagiaires (100% Dynamique)
        # ============================================================
        if "stagiaire" in q_norm or "stagiaires" in q_norm:
            sparql = PREFIXES + """SELECT ?stagiaire (SAMPLE(?nomClean) AS ?nom) (SAMPLE(?ageVal) AS ?age) (SAMPLE(?cinVal) AS ?cin) (SAMPLE(?telVal) AS ?telephone) WHERE {
    {
        ?stagiaire rdf:type/rdfs:subClassOf* :Stagiaire .
    } UNION {
        ?stagiaire :joueLeRoleDe :Stagiaire .
    } UNION {
        ?stagiaire :role :Stagiaire .
    }
    OPTIONAL { ?stagiaire :nom ?nomProp }
    OPTIONAL { ?stagiaire :prenom ?prenomProp }
    OPTIONAL { ?stagiaire rdfs:label ?labelProp }
    OPTIONAL { ?stagiaire :age ?ageVal }
    OPTIONAL { ?stagiaire :numeroCIN ?cinVal }
    OPTIONAL { ?stagiaire :telephone ?telVal }
    BIND(COALESCE(
        IF(BOUND(?prenomProp) && BOUND(?nomProp) && !CONTAINS(LCASE(STR(?nomProp)), LCASE(STR(?prenomProp))), CONCAT(?prenomProp, " ", ?nomProp), ?nomProp),
        ?labelProp,
        REPLACE(REPLACE(STR(?stagiaire), "^.*[#/]", ""), "_", " ")
    ) AS ?nomClean)
} GROUP BY ?stagiaire"""
            return sparql, "Recherche de tous les Stagiaires", \
                   "L'IA extrait dynamiquement tous les individus typés Stagiaire ou ayant ce rôle depuis l'ontologie."

        # ============================================================
        # PRIORITÉ 12 : Patients en général (SANS filtre âge)
        # ============================================================
        if "patient" in q_norm or "patients" in q_norm:
            sparql = PREFIXES + """SELECT ?patient (SAMPLE(?nomClean) AS ?nom) (SAMPLE(?ageVal) AS ?age) (SAMPLE(?dosVal) AS ?dossier) (SAMPLE(?sangVal) AS ?groupeSanguin) (SAMPLE(?telVal) AS ?telephone) WHERE {
    ?patient rdf:type/rdfs:subClassOf* :Patient .
    OPTIONAL { ?patient :nom ?nomProp }
    OPTIONAL { ?patient :prenom ?prenomProp }
    OPTIONAL { ?patient rdfs:label ?labelProp }
    OPTIONAL { ?patient :age ?ageVal }
    OPTIONAL { ?patient :numeroDossier ?dosVal }
    OPTIONAL { ?patient :groupeSanguin ?sangVal }
    OPTIONAL { ?patient :telephone ?telVal }
    BIND(COALESCE(
        IF(BOUND(?prenomProp) && BOUND(?nomProp) && !CONTAINS(LCASE(STR(?nomProp)), LCASE(STR(?prenomProp))), CONCAT(?prenomProp, " ", ?nomProp), ?nomProp),
        ?labelProp,
        REPLACE(REPLACE(STR(?patient), "^.*[#/]", ""), "_", " ")
    ) AS ?nomClean)
} GROUP BY ?patient"""
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
        q_norm = (question.lower().replace("à", "a").replace("â", "a").replace("é", "e")
                  .replace("è", "e").replace("ê", "e").replace("î", "i").replace("ï", "i")
                  .replace("ô", "o").replace("ù", "u").replace("û", "u").replace("ç", "c"))

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

        bindings = data.get("results", {}).get("bindings", [])
        nb_results = len(bindings)

        # --- Détection du type de résultat (pour aiguiller l'affichage front-end) ---
        result_type = "personnes"
        sq_low = (sparql_query or "").lower()
        int_low = (intention or "").lower()

        if "?sousclasse" in sq_low or "sous-classe" in int_low or "sous classe" in int_low:
            result_type = "subclasses"
        elif ("?classe" in sq_low and ("owl:class" in sq_low or "rdfs:class" in sq_low)) or "classes de l'ontologie" in int_low:
            result_type = "classes"
        elif "?propriete" in sq_low and ("owl:objectproperty" in sq_low or "owl:datatypeproperty" in sq_low):
            result_type = "properties"
        elif nb_results > 0 and "total" in bindings[0]:
            result_type = "count"
        elif nb_results == 1 and (
            "fiche" in int_low or "profil" in int_low or "recherche de l'individu" in int_low
            or int_low.startswith("recherche de '")
            or any(k in q_norm for k in [
                "qui est", "donne-moi le medecin", "donne moi le medecin",
                "donne-moi la patiente", "donne moi la patiente",
                "donne-moi le patient", "donne moi le patient",
                "donne-moi la personne", "donne moi la personne",
                "fiche de", "profil de"
            ])
        ):
            result_type = "personne_single"

        # --- Génération dynamique de la réponse en langage naturel ---
        if result_type == "count":
            total_val = bindings[0]["total"].get("value", "0")
            summary_text = f"{intention} : {total_val} résultat(s) dans l'ontologie."
            return {
                "question": question,
                "intention": intention,
                "explanation": explanation,
                "sparql_query": sparql_query,
                "data": data,
                "count": int(total_val) if total_val.isdigit() else 1,
                "answer_summary": summary_text,
                "result_type": result_type
            }

        if nb_results == 0:
            if "Recherche de tous les " in intention:
                cls_clean = intention.replace("Recherche de tous les ", "").rstrip("s")
                summary_text = f"Aucun individu trouvé dans l'ontologie pour la sous-classe ou le rôle : {cls_clean}."
            else:
                summary_text = f"Aucun résultat trouvé dans l'ontologie pour : « {question} »."
        elif result_type == "subclasses":
            directs = [b.get("nom", {}).get("value", "") for b in bindings if b.get("estDirecte", {}).get("value") == "Oui"]
            others = [b.get("nom", {}).get("value", "") for b in bindings if b.get("estDirecte", {}).get("value") == "Non"]
            all_noms = [b.get("nom", {}).get("value", "") for b in bindings if b.get("nom", {}).get("value")]

            if directs and others:
                summary_text = (
                    f"Hiérarchie trouvée ({len(all_noms)} sous-classes au total). "
                    f"Directes ({len(directs)}) — {', '.join(directs)} | "
                    f"Spécialisations ({len(others)}) — {', '.join(others[:8])}"
                    f"{'…' if len(others) > 8 else ''}."
                )
            elif directs:
                summary_text = f"{len(directs)} sous-classe(s) directe(s) trouvée(s) — {', '.join(directs)}."
            elif all_noms:
                summary_text = f"{len(all_noms)} sous-classe(s) trouvée(s) — {', '.join(all_noms[:10])}."
            else:
                summary_text = f"{nb_results} sous-classe(s) extraite(s) de l'ontologie."

        elif result_type == "classes":
            noms_classes = [b.get("nom", {}).get("value", "") for b in bindings if b.get("nom", {}).get("value")]
            summary_text = f"{nb_results} classes définies dans l'ontologie (owl:Class) — Concepts principaux — {', '.join(noms_classes[:10])}…"

        elif result_type == "properties":
            noms_props = [b.get("nom", {}).get("value", "") for b in bindings if b.get("nom", {}).get("value")]
            summary_text = f"{nb_results} propriété(s) trouvée(s) dans l'ontologie — {', '.join(noms_props[:8])}…"

        elif result_type == "personne_single":
            p_nom = (
                bindings[0].get("nom", {}).get("value") or
                bindings[0].get("nomDisplay", {}).get("value") or
                bindings[0].get("nomClean", {}).get("value") or
                bindings[0].get("personne", {}).get("value", "Individu")
            )
            if "#" in p_nom:
                p_nom = p_nom.split("#")[-1].replace("_", " ")
            summary_text = f"1 résultat trouvé — Fiche complète de {p_nom}."

        else:
            # Extraire les noms trouvés pour construire une réponse humaine
            noms = []
            for b in bindings:
                nom_val = (
                    b.get("nom", {}).get("value") or
                    b.get("nomDisplay", {}).get("value") or
                    b.get("nomClean", {}).get("value") or
                    b.get("personne", {}).get("value") or
                    b.get("medecin", {}).get("value") or
                    b.get("patient", {}).get("value") or
                    b.get("individu", {}).get("value") or
                    b.get("stagiaire", {}).get("value") or ""
                )
                if "#" in nom_val:
                    nom_val = nom_val.split("#")[-1].replace("_", " ")
                if nom_val and nom_val not in noms:
                    noms.append(nom_val)

            if noms:
                if nb_results == 1:
                    summary_text = f"1 résultat trouvé — {intention} : {noms[0]}."
                elif nb_results <= 5:
                    summary_text = f"{nb_results} résultats trouvés — {intention} : {', '.join(noms)}."
                else:
                    apercu = ', '.join(noms[:5])
                    summary_text = f"{nb_results} résultats trouvés — {intention}. Aperçu : {apercu}..."
            else:
                summary_text = f"{nb_results} résultat(s) extrait(s) de l'ontologie pour : « {question} »."

        return {
            "question": question,
            "intention": intention,
            "explanation": explanation,
            "sparql_query": sparql_query,
            "data": data,
            "count": nb_results,
            "answer_summary": summary_text,
            "result_type": result_type
        }
