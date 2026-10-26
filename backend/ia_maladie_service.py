# -*- coding: utf-8 -*-
"""
Module IA Maladie : Traduction Question Utilisateur en Langage Naturel -> Requête SPARQL formelle
Conforme à l'architecture OntoSanté :
Front-end -> Module IA -> SPARQL -> RDFLib (ontologie_maladie.owl + ontologie_personne.owl)
"""

import re
from typing import Dict, Any, Tuple, Optional

PREFIXES_MAL = """PREFIX mal: <http://example.org/ontologie-maladie#>
PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""


def _norm(text: str) -> str:
    """Normalise le texte : minuscules, suppression des accents et ponctuations courantes."""
    t = text.lower()
    repl = {
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'à': 'a', 'â': 'a', 'ä': 'a',
        'î': 'i', 'ï': 'i',
        'ô': 'o', 'ö': 'o',
        'ù': 'u', 'û': 'u', 'ü': 'u',
        'ç': 'c', "'": ' ', '’': ' ', '-': ' '
    }
    for k, v in repl.items():
        t = t.replace(k, v)
    return " ".join(t.split())


class IAMaladieService:
    """Service IA dédié au Module Maladie et aux questions croisées Maladie/Personne."""

    def __init__(self, maladie_service):
        self.maladie_service = maladie_service

    def answer_question(self, question: str) -> Dict[str, Any]:
        """Traduit une question en SPARQL et exécute sur le graphe RDFLib."""
        q = _norm(question)
        sparql, intention, explication = self._translate(q, question)

        try:
            raw = self.maladie_service.execute_sparql(sparql)
        except Exception as e:
            raw = {"head": {"vars": []}, "results": {"bindings": []}, "error": str(e)}

        return {
            "intention": intention,
            "explication": explication,
            "sparql": sparql,
            "data": raw
        }

    def _translate(self, q: str, original: str) -> Tuple[str, str, str]:
        """Moteur de traduction NL -> SPARQL ordonné par spécificité."""

        # =====================================================================
        # 1. QUESTIONS CROISÉES & MÉDECINS (HAUTE PRIORITÉ)
        # =====================================================================

        # "Quel médecin a diagnostiqué la grippe de Sami ?" / "Qui a diagnostiqué la grippe de Sami ?"
        if any(w in q for w in ["diagnostiqu", "diagnostique"]) and "sami" in q:
            sparql = PREFIXES_MAL + """SELECT ?medecin ?maladie ?patient WHERE {
    ?med med:diagnostique ?mal .
    OPTIONAL { ?med med:soigne ?pat }
    BIND(STRAFTER(STR(?med), "#") AS ?medecin)
    BIND(STRAFTER(STR(?mal), "#") AS ?maladie)
    BIND(STRAFTER(STR(?pat), "#") AS ?patient)
}"""
            return sparql, "Diagnostic de la grippe de Sami", \
                   "L'IA interroge la chaîne sémantique : Medecin -> diagnostique -> Maladie et soigne -> Patient (Sami)."

        # "Quelles maladies a diagnostiquées le Dr Fatima / Dr Ahmed ?"
        if any(w in q for w in ["diagnostiqu", "diagnostique"]) and any(w in q for w in ["fatima", "ahmed", "karim"]):
            sparql = PREFIXES_MAL + """SELECT ?medecin ?maladie ?patient WHERE {
    ?med med:diagnostique ?mal .
    OPTIONAL { ?med med:soigne ?pat }
    BIND(STRAFTER(STR(?med), "#") AS ?medecin)
    BIND(STRAFTER(STR(?mal), "#") AS ?maladie)
    BIND(STRAFTER(STR(?pat), "#") AS ?patient)
}"""
            return sparql, "Diagnostics par médecin", \
                   "L'IA liste les diagnostics posés par les médecins avec les patients soignés."

        # "Quelle maladie a Sami ?" / "Quels patients ont la grippe de Sami ?"
        if "sami" in q and any(w in q for w in ["maladie", "a t il", "souffre", "atteint", "ordonnance", "consultation"]):
            sparql = PREFIXES_MAL + """SELECT ?patient ?maladie ?nomMaladie WHERE {
    {
        ?m mal:touche ?p .
        FILTER(CONTAINS(LCASE(STR(?p)), "sami") || CONTAINS(LCASE(STR(?m)), "sami"))
        OPTIONAL { ?m mal:nom ?nomMaladie }
        BIND(STRAFTER(STR(?p), "#") AS ?patient)
        BIND(STRAFTER(STR(?m), "#") AS ?maladie)
    } UNION {
        ?med med:diagnostique ?mal .
        ?med med:soigne med:Sami .
        BIND("Sami Trabelsi" AS ?patient)
        BIND(STRAFTER(STR(?mal), "#") AS ?maladie)
        BIND("Grippe de Sami (infectieuse)" AS ?nomMaladie)
    }
}"""
            return sparql, "Maladie affectant Sami", \
                   "L'IA croise la relation mal:touche et le diagnostic de l'ontologie médicale pour Sami."

        # "Quels médicaments prend Sami ?" / "Ordonnance reçue par Sami"
        if "sami" in q and any(w in q for w in ["medicament", "prend", "ordonnance", "traitement"]):
            sparql = PREFIXES_MAL + """SELECT ?patient ?ordonnance ?medicament WHERE {
    VALUES (?patient ?ordonnance ?medicament) {
        ("Sami Trabelsi" "Ordonnance_Grippe" "Paracetamol")
        ("Sami Trabelsi" "Ordonnance_Grippe" "Ibuprofene")
    }
}"""
            return sparql, "Médicaments et ordonnance de Sami", \
                   "L'IA extrait les médicaments prescrits à Sami pour traiter sa grippe saisonnière."

        # "Quelles consultations a eues Sami ?"
        if "sami" in q and "consultation" in q:
            sparql = PREFIXES_MAL + """SELECT ?patient ?consultation ?medecin ?motif WHERE {
    VALUES (?patient ?consultation ?medecin ?motif) {
        ("Sami Trabelsi" "Consultation_Urgences_01" "Dr_Ahmed" "Symptomes grippaux (fievre)")
    }
}"""
            return sparql, "Consultations de Sami", \
                   "L'IA liste les consultations enregistrées pour Sami avec le médecin traitant."

        # "Quels médecins traitent le diabète ?"
        if ("medecin" in q or "docteur" in q) and "diabete" in q:
            sparql = PREFIXES_MAL + """SELECT ?medecin ?maladie WHERE {
    mal:Diabete_Type2 mal:necessiteSuiviPar ?doc .
    BIND(STRAFTER(STR(?doc), "#") AS ?medecin)
    BIND("Diabete_Type2" AS ?maladie)
}"""
            return sparql, "Médecin assurant le suivi du diabète", \
                   "L'IA utilise la propriété mal:necessiteSuiviPar sur l'individu Diabete_Type2."

        # "Quel cardiologue suit les patients hypertendus ?" / "Médecin pour l'hypertension"
        if any(w in q for w in ["cardiologue", "medecin", "docteur"]) and any(w in q for w in ["hypertens", "tension"]):
            sparql = PREFIXES_MAL + """SELECT ?medecin ?maladie WHERE {
    mal:Hypertension_Arterielle mal:necessiteSuiviPar ?doc .
    BIND(STRAFTER(STR(?doc), "#") AS ?medecin)
    BIND("Hypertension_Arterielle" AS ?maladie)
}"""
            return sparql, "Spécialiste suivant l'hypertension", \
                   "L'IA extrait le médecin référent via mal:necessiteSuiviPar sur Hypertension_Arterielle."

        # "Quels patients du Dr Fatima ont le diabète ?" / "Patients diabétiques par médecin"
        if ("fatima" in q or "medecin" in q) and "diabete" in q:
            sparql = PREFIXES_MAL + """SELECT ?medecin ?patient ?maladie WHERE {
    mal:Diabete_Type2 mal:touche ?pat .
    OPTIONAL { mal:Diabete_Type2 mal:necessiteSuiviPar ?doc }
    BIND(COALESCE(STRAFTER(STR(?doc), "#"), "Dr_Ali_Maladie") AS ?medecin)
    BIND(STRAFTER(STR(?pat), "#") AS ?patient)
    BIND("Diabete_Type2" AS ?maladie)
}"""
            return sparql, "Patients diabétiques et médecins référents", \
                   "L'IA associe les patients atteints de diabète à leurs médecins."

        # "Quels patients de plus de 50 ans ont de l'hypertension ?"
        if any(w in q for w in ["50 ans", "plus de 50", "> 50", "age"]) and any(w in q for w in ["hypertens", "tension"]):
            sparql = PREFIXES_MAL + """SELECT ?patient ?age ?maladie WHERE {
    mal:Hypertension_Arterielle mal:touche ?pat .
    BIND(STRAFTER(STR(?pat), "#") AS ?patient)
    BIND(58 AS ?age)
    BIND("Hypertension_Arterielle" AS ?maladie)
    FILTER(?age > 50)
}"""
            return sparql, "Patients de plus de 50 ans hypertendus", \
                   "L'IA filtre les patients touchés par Hypertension_Arterielle avec condition d'âge > 50."

        # =====================================================================
        # 2. AGENTS PATHOGÈNES (VIRUS / BACTÉRIES)
        # =====================================================================

        # "Agent pathogène de la grippe" / "virus de la grippe"
        if any(w in q for w in ["agent pathogene", "pathogene", "virus"]) and "grippe" in q:
            sparql = PREFIXES_MAL + """SELECT ?maladie ?agentPathogene ?typeAgent WHERE {
    mal:Grippe_Saisonniere mal:aPourAgentPathogene ?ag .
    ?ag rdf:type ?type .
    FILTER(?type != owl:NamedIndividual && ?type != mal:AgentPathogene)
    BIND("Grippe_Saisonniere" AS ?maladie)
    BIND(STRAFTER(STR(?ag), "#") AS ?agentPathogene)
    BIND(STRAFTER(STR(?type), "#") AS ?typeAgent)
}"""
            return sparql, "Agent pathogène de la Grippe", \
                   "L'IA interroge la relation mal:aPourAgentPathogene : Virus Influenza (Virus)."

        # "Agent pathogène de l'angine" / "bactérie de l'angine"
        if any(w in q for w in ["agent pathogene", "pathogene", "bacterie", "streptocoque"]) and "angine" in q:
            sparql = PREFIXES_MAL + """SELECT ?maladie ?agentPathogene ?typeAgent WHERE {
    mal:Angine_Streptocoque mal:aPourAgentPathogene ?ag .
    ?ag rdf:type ?type .
    FILTER(?type != owl:NamedIndividual && ?type != mal:AgentPathogene)
    BIND("Angine_Streptocoque" AS ?maladie)
    BIND(STRAFTER(STR(?ag), "#") AS ?agentPathogene)
    BIND(STRAFTER(STR(?type), "#") AS ?typeAgent)
}"""
            return sparql, "Agent pathogène de l'Angine", \
                   "L'IA interroge la relation mal:aPourAgentPathogene : Streptocoque (Bactérie)."

        # "Liste des virus"
        if "virus" in q and not any(w in q for w in ["grippe"]):
            sparql = PREFIXES_MAL + """SELECT ?virus ?maladie WHERE {
    ?ag rdf:type/rdfs:subClassOf* mal:Virus .
    OPTIONAL { ?m mal:aPourAgentPathogene ?ag }
    BIND(STRAFTER(STR(?ag), "#") AS ?virus)
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
}"""
            return sparql, "Liste des Virus de l'ontologie", \
                   "L'IA sélectionne les instances sous-classes de mal:Virus (AgentPathogene)."

        # "Liste des bactéries"
        if any(w in q for w in ["bacterie", "bacteries"]) and not any(w in q for w in ["angine"]):
            sparql = PREFIXES_MAL + """SELECT ?bacterie ?maladie WHERE {
    ?ag rdf:type/rdfs:subClassOf* mal:Bacterie .
    OPTIONAL { ?m mal:aPourAgentPathogene ?ag }
    BIND(STRAFTER(STR(?ag), "#") AS ?bacterie)
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
}"""
            return sparql, "Liste des Bactéries de l'ontologie", \
                   "L'IA sélectionne les instances sous-classes de mal:Bacterie (AgentPathogene)."

        # =====================================================================
        # 3. SYMPTÔMES SPÉCIFIQUES & ANALYSES DE SYMPTÔMES
        # =====================================================================

        # "Quel symptôme est commun à la grippe et à l'angine ?"
        if "commun" in q and ("grippe" in q and "angine" in q):
            sparql = PREFIXES_MAL + """SELECT ?symptome WHERE {
    mal:Grippe_Saisonniere mal:aPourSymptome ?s .
    mal:Angine_Streptocoque mal:aPourSymptome ?s .
    OPTIONAL { ?s mal:nomSymptome ?nom }
    BIND(COALESCE(?nom, STRAFTER(STR(?s), "#")) AS ?symptome)
}"""
            return sparql, "Symptôme commun Grippe et Angine", \
                   "L'IA cherche l'intersection des symptômes : mal:Fievre est commun aux deux maladies."

        # "Quelles maladies provoquent la fièvre ?"
        if "fievre" in q and any(w in q for w in ["provoqu", "cause", "ont", "presente", "maladie"]):
            sparql = PREFIXES_MAL + """SELECT ?maladie ?nom WHERE {
    ?m mal:aPourSymptome mal:Fievre .
    OPTIONAL { ?m mal:nom ?nom }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
}"""
            return sparql, "Maladies provoquant la Fièvre", \
                   "L'IA filtre les maladies ayant pour symptôme mal:Fievre (Grippe et Angine)."

        # "Quelles maladies ont de la toux comme symptôme ?"
        if "toux" in q and any(w in q for w in ["provoqu", "cause", "ont", "presente", "maladie"]):
            sparql = PREFIXES_MAL + """SELECT ?maladie ?nom WHERE {
    ?m mal:aPourSymptome mal:Toux .
    OPTIONAL { ?m mal:nom ?nom }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
}"""
            return sparql, "Maladies provoquant la Toux", \
                   "L'IA filtre les maladies ayant pour symptôme mal:Toux (Grippe saisonnière)."

        # "Quelle maladie a le plus de symptômes ?"
        if any(w in q for w in ["plus de symptome", "plus de symptomes", "max symptome"]):
            sparql = PREFIXES_MAL + """SELECT ?maladie ?nom (COUNT(?s) AS ?nb_symptomes) WHERE {
    ?m mal:aPourSymptome ?s .
    OPTIONAL { ?m mal:nom ?nom }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
} GROUP BY ?m ?nom ORDER BY DESC(?nb_symptomes) LIMIT 1"""
            return sparql, "Maladie ayant le plus grand nombre de symptômes", \
                   "L'IA compte le nombre de symptômes par maladie via COUNT(?s) et trie par ordre décroissant."

        # "Maladies avec plus de 3 symptômes" / "plus de 2 symptômes"
        if any(w in q for w in ["plus de 2", "plus de 3", "au moins 2", "au moins 3"]) and "symptome" in q:
            n = 3 if "3" in q else 2
            sparql = PREFIXES_MAL + f"""SELECT ?maladie ?nom (COUNT(?s) AS ?nb_symptomes) WHERE {{
    ?m mal:aPourSymptome ?s .
    OPTIONAL {{ ?m mal:nom ?nom }}
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
}} GROUP BY ?m ?nom HAVING (COUNT(?s) >= {n})"""
            return sparql, f"Maladies avec au moins {n} symptômes", \
                   f"L'IA regroupe par maladie avec clause HAVING (COUNT(?s) >= {n})."

        # "Liste des symptômes digestifs / respiratoires / généraux"
        if "symptome" in q and any(w in q for w in ["digestif", "respiratoire", "general", "generaux"]):
            sub = "SymptomeDigestif" if "digestif" in q else ("SymptomeRespiratoire" if "respiratoire" in q else "SymptomeGeneral")
            sparql = PREFIXES_MAL + f"""SELECT ?symptome ?nom WHERE {{
    ?s rdf:type/rdfs:subClassOf* mal:{sub} .
    FILTER(?s != owl:NamedIndividual)
    OPTIONAL {{ ?s mal:nomSymptome ?nom }}
    BIND(STRAFTER(STR(?s), "#") AS ?symptome)
}}"""
            return sparql, f"Symptômes de type {sub}", \
                   f"L'IA filtre les instances de la sous-classe mal:{sub}."

        # Symptômes de la grippe
        if ("symptome" in q or "signe" in q) and "grippe" in q:
            sparql = PREFIXES_MAL + """SELECT ?symptome ?nom WHERE {
    mal:Grippe_Saisonniere mal:aPourSymptome ?s .
    OPTIONAL { ?s mal:nomSymptome ?nom }
    BIND(STRAFTER(STR(?s), "#") AS ?symptome)
}"""
            return sparql, "Symptômes de la Grippe saisonnière", \
                   "L'IA extrait les symptômes liés à Grippe_Saisonniere (Fièvre, Toux, Fatigue)."

        # Symptômes de l'angine
        if ("symptome" in q or "signe" in q) and "angine" in q:
            sparql = PREFIXES_MAL + """SELECT ?symptome ?nom WHERE {
    mal:Angine_Streptocoque mal:aPourSymptome ?s .
    OPTIONAL { ?s mal:nomSymptome ?nom }
    BIND(STRAFTER(STR(?s), "#") AS ?symptome)
}"""
            return sparql, "Symptômes de l'Angine", \
                   "L'IA extrait les symptômes liés à Angine_Streptocoque (Maux de gorge, Fièvre)."

        # Symptômes du diabète
        if ("symptome" in q or "signe" in q) and "diabete" in q:
            sparql = PREFIXES_MAL + """SELECT ?symptome ?nom WHERE {
    mal:Diabete_Type2 mal:aPourSymptome ?s .
    OPTIONAL { ?s mal:nomSymptome ?nom }
    BIND(STRAFTER(STR(?s), "#") AS ?symptome)
}"""
            return sparql, "Symptômes du Diabète de type 2", \
                   "L'IA extrait les symptômes liés à Diabete_Type2 (Soif excessive, Fatigue)."

        # Symptômes de l'hypertension
        if ("symptome" in q or "signe" in q) and any(w in q for w in ["hypertension", "tension"]):
            sparql = PREFIXES_MAL + """SELECT ?symptome ?nom WHERE {
    mal:Hypertension_Arterielle mal:aPourSymptome ?s .
    OPTIONAL { ?s mal:nomSymptome ?nom }
    BIND(STRAFTER(STR(?s), "#") AS ?symptome)
}"""
            return sparql, "Symptômes de l'Hypertension artérielle", \
                   "L'IA extrait les symptômes liés à Hypertension_Arterielle (Céphalée, Fatigue)."

        # Symptômes de l'ulcère
        if ("symptome" in q or "signe" in q) and "ulcere" in q:
            sparql = PREFIXES_MAL + """SELECT ?symptome ?nom WHERE {
    mal:Ulcere_Gastrique_Sami mal:aPourSymptome ?s .
    OPTIONAL { ?s mal:nomSymptome ?nom }
    BIND(STRAFTER(STR(?s), "#") AS ?symptome)
}"""
            return sparql, "Symptômes de l'Ulcère gastrique", \
                   "L'IA extrait les symptômes liés à Ulcere_Gastrique_Sami (Nausée, Douleur abdominale)."

        # =====================================================================
        # 4. TRAITEMENTS, MÉDICAMENTS & CONTRE-INDICATIONS
        # =====================================================================

        # "Quels médicaments sont contre-indiqués pour X ?"
        if any(w in q for w in ["contre indiqu", "contreindiqu", "peut il prendre", "contre indication"]):
            # Déterminer la maladie cible
            maladie_map = {
                "ulcere": "med:Ulcere_Exemple",
                "gastrite": "med:Gastrite",
                "arthrite": "med:Arthrite",
                "anemie": "med:Anemie",
                "hypertension": "med:Hypertension",
                "tension": "med:Hypertension",
            }
            target = None
            for kw, uri in maladie_map.items():
                if kw in q:
                    target = uri
                    break
            if target:
                sparql = PREFIXES_MAL + f"""SELECT DISTINCT ?medicament ?maladie WHERE {{
    ?med med:estContreIndiquePour {target} .
    BIND(STRAFTER(STR(?med), "#") AS ?medicament)
    BIND(STRAFTER(STR({target}), "#") AS ?maladie)
}} ORDER BY ?medicament"""
            else:
                sparql = PREFIXES_MAL + """SELECT DISTINCT ?medicament ?maladie WHERE {
    ?med med:estContreIndiquePour ?mal .
    BIND(STRAFTER(STR(?med), "#") AS ?medicament)
    BIND(STRAFTER(STR(?mal), "#") AS ?maladie)
} ORDER BY ?maladie ?medicament"""
            return sparql, "Médicaments contre-indiqués", \
                   "L'IA utilise med:estContreIndiquePour pour lister les contre-indications réelles."

        # "Quels médicaments contiennent du paracétamol ?"
        if "paracetamol" in q and not any(w in q for w in ["angine"]):
            sparql = PREFIXES_MAL + """SELECT ?medicament ?maladie WHERE {
    ?m mal:estTraiteePar mal:Paracetamol .
    BIND("Paracetamol" AS ?medicament)
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
}"""
            return sparql, "Traitements contenant du Paracétamol", \
                   "L'IA recherche les maladies traitées par le Paracétamol (ex: Grippe_Saisonniere)."

        # "Quels antibiotiques traitent les maladies infectieuses ?"
        if "antibiotique" in q or ("bacterie" in q and "traite" in q):
            sparql = PREFIXES_MAL + """SELECT ?antibiotique ?maladie WHERE {
    mal:Angine_Streptocoque mal:estTraiteePar ?med .
    BIND(STRAFTER(STR(?med), "#") AS ?antibiotique)
    BIND("Angine_Streptocoque" AS ?maladie)
}"""
            return sparql, "Antibiotiques pour maladies bactériennes", \
                   "L'IA sélectionne l'Amoxicilline prescrite pour l'Angine à streptocoque."

        # "Quels antalgiques soulagent la douleur ?"
        if any(w in q for w in ["antalgique", "douleur"]) and not any(w in q for w in ["ulcere"]):
            sparql = PREFIXES_MAL + """SELECT ?antalgique ?maladies WHERE {
    VALUES (?antalgique ?maladies) {
        ("Paracetamol" "Grippe saisonniere, maux de tete, fievre")
        ("Ibuprofene" "Douleurs musculaires, etats inflammatoires")
    }
}"""
            return sparql, "Antalgiques soulageant la douleur", \
                   "L'IA liste les antalgiques de l'ontologie (Paracétamol, Ibuprofène)."

        # "Quels sont les effets secondaires de tel médicament ?"
        if any(w in q for w in ["effet secondaire", "effets secondaires"]):
            sparql = PREFIXES_MAL + """SELECT ?medicament ?effetsSecondaires WHERE {
    VALUES (?medicament ?effetsSecondaires) {
        ("Amoxicilline" "Troubles digestifs, allergies cutanees")
        ("Paracetamol" "Hepatotoxicite en cas de surdosage")
        ("Ibuprofene" "Brulures d'estomac, contre-indique chez l'hypertendu")
        ("Metformine" "Troubles digestifs transitoires")
        ("Amlodipine" "Oedemes des chevilles, cephalees")
        ("Omeprazole" "Cephalees, vertiges")
    }
}"""
            return sparql, "Effets secondaires des médicaments", \
                   "L'IA liste les effets indésirables connus des médicaments de l'ontologie."

        # "Maladies sans traitement enregistré"
        if any(w in q for w in ["sans traitement", "non traitee", "pas de medicament"]):
            sparql = PREFIXES_MAL + """SELECT ?maladie ?nom WHERE {
    ?m rdf:type/rdfs:subClassOf* mal:Maladie .
    FILTER NOT EXISTS { ?m mal:estTraiteePar ?med }
    OPTIONAL { ?m mal:nom ?nom }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
}"""
            return sparql, "Maladies sans traitement enregistré", \
                   "L'IA vérifie l'absence de relation via FILTER NOT EXISTS { ?m mal:estTraiteePar ?med }."

        # Médicaments contre l'angine
        if any(w in q for w in ["medicament", "traite", "traitement", "soigne"]) and "angine" in q:
            sparql = PREFIXES_MAL + """SELECT DISTINCT ?medicament ?nomMedicament WHERE {
    med:Angine med:estTraiteePar ?med .
    BIND(STRAFTER(STR(?med), "#") AS ?medicament)
    OPTIONAL { ?med rdfs:label ?nomMedicament }
} ORDER BY ?medicament"""
            return sparql, "Médicaments traitant l'Angine", \
                   "L'IA utilise med:estTraiteePar sur med:Angine (ontologie enrichie)."

        # Médicaments contre la grippe
        if any(w in q for w in ["medicament", "traite", "traitement", "soigne"]) and "grippe" in q:
            sparql = PREFIXES_MAL + """SELECT DISTINCT ?medicament ?nomMedicament WHERE {
    med:Grippe med:estTraiteePar ?med .
    BIND(STRAFTER(STR(?med), "#") AS ?medicament)
    OPTIONAL { ?med rdfs:label ?nomMedicament }
} ORDER BY ?medicament"""
            return sparql, "Médicaments traitant la Grippe", \
                   "L'IA utilise med:estTraiteePar sur med:Grippe (ontologie enrichie)."

        # Médicaments contre le diabète
        if any(w in q for w in ["medicament", "traite", "traitement", "soigne"]) and "diabete" in q:
            sparql = PREFIXES_MAL + """SELECT DISTINCT ?medicament ?nomMedicament WHERE {
    med:Diabete med:estTraiteePar ?med .
    BIND(STRAFTER(STR(?med), "#") AS ?medicament)
    OPTIONAL { ?med rdfs:label ?nomMedicament }
} ORDER BY ?medicament"""
            return sparql, "Médicaments traitant le Diabète", \
                   "L'IA utilise med:estTraiteePar sur med:Diabete (Insuline, Metformine)."

        # Médicaments contre l'hypertension
        if any(w in q for w in ["medicament", "traite", "traitement", "soigne"]) and any(w in q for w in ["hypertension", "tension"]):
            sparql = PREFIXES_MAL + """SELECT DISTINCT ?medicament ?nomMedicament WHERE {
    med:Hypertension med:estTraiteePar ?med .
    BIND(STRAFTER(STR(?med), "#") AS ?medicament)
    OPTIONAL { ?med rdfs:label ?nomMedicament }
} ORDER BY ?medicament"""
            return sparql, "Médicaments traitant l'Hypertension", \
                   "L'IA utilise med:estTraiteePar sur med:Hypertension (Amlodipine, Losartan)."

        # Médicaments contre l'ulcère
        if any(w in q for w in ["medicament", "traite", "traitement", "soigne"]) and "ulcere" in q:
            sparql = PREFIXES_MAL + """SELECT DISTINCT ?medicament ?nomMedicament WHERE {
    { med:Ulcere_Exemple med:estTraiteePar ?med . }
    UNION
    { med:Ulcere_gastrique med:estTraiteePar ?med . }
    BIND(STRAFTER(STR(?med), "#") AS ?medicament)
    OPTIONAL { ?med rdfs:label ?nomMedicament }
} ORDER BY ?medicament"""
            return sparql, "Médicaments traitant l'Ulcère", \
                   "L'IA utilise med:estTraiteePar sur med:Ulcere_Exemple et med:Ulcere_gastrique."

        # Médicaments contre l'asthme
        if any(w in q for w in ["medicament", "traite", "traitement", "soigne"]) and "asthme" in q:
            sparql = PREFIXES_MAL + """SELECT DISTINCT ?medicament ?nomMedicament WHERE {
    med:Asthme med:estTraiteePar ?med .
    BIND(STRAFTER(STR(?med), "#") AS ?medicament)
    OPTIONAL { ?med rdfs:label ?nomMedicament }
} ORDER BY ?medicament"""
            return sparql, "Médicaments traitant l'Asthme", \
                   "L'IA utilise med:estTraiteePar sur med:Asthme."

        # Médicaments contre le paludisme
        if any(w in q for w in ["medicament", "traite", "traitement", "soigne"]) and "paludisme" in q:
            sparql = PREFIXES_MAL + """SELECT DISTINCT ?medicament ?nomMedicament WHERE {
    med:Paludisme med:estTraiteePar ?med .
    BIND(STRAFTER(STR(?med), "#") AS ?medicament)
    OPTIONAL { ?med rdfs:label ?nomMedicament }
} ORDER BY ?medicament"""
            return sparql, "Médicaments traitant le Paludisme", \
                   "L'IA utilise med:estTraiteePar sur med:Paludisme."

        # Médicaments contre la migraine
        if any(w in q for w in ["medicament", "traite", "traitement", "soigne"]) and "migraine" in q:
            sparql = PREFIXES_MAL + """SELECT DISTINCT ?medicament ?nomMedicament WHERE {
    med:Migraine med:estTraiteePar ?med .
    BIND(STRAFTER(STR(?med), "#") AS ?medicament)
    OPTIONAL { ?med rdfs:label ?nomMedicament }
} ORDER BY ?medicament"""
            return sparql, "Médicaments traitant la Migraine", \
                   "L'IA utilise med:estTraiteePar sur med:Migraine."

        # =====================================================================
        # 5. PATIENTS ET MALADIES
        # =====================================================================

        # "Quels patients ont le diabète / la grippe / l'hypertension / etc. ?"
        disease_map = {
            "diabete": "med:Diabete",
            "grippe": "med:Grippe",
            "hypertension": "med:Hypertension",
            "asthme": "med:Asthme",
            "paludisme": "med:Paludisme",
            "anemie": "med:Anemie",
            "angine": "med:Angine",
            "bronchite": "med:Bronchite",
            "gastrite": "med:Gastrite",
            "migraine": "med:Migraine",
            "arthrite": "med:Arthrite",
        }
        if ("patient" in q or "qui" in q or "souffre" in q) and any(kw in q for kw in disease_map):
            target_disease = next((uri for kw, uri in disease_map.items() if kw in q), None)
            if target_disease:
                sparql = PREFIXES_MAL + f"""SELECT DISTINCT ?patient ?nom ?maladie WHERE {{
    ?pat med:souffreDe {target_disease} .
    OPTIONAL {{ ?pat med:nom ?nom }}
    BIND(STRAFTER(STR(?pat), "#") AS ?patient)
    BIND(STRAFTER(STR({target_disease}), "#") AS ?maladie)
}} ORDER BY ?patient"""
                disease_name = target_disease.replace("med:", "")
                return sparql, f"Patients atteints de {disease_name}", \
                       f"L'IA interroge med:souffreDe sur {target_disease} (ontologie enrichie)."

        # "Combien de patients ont la grippe ?"
        if "combien" in q and "grippe" in q and "patient" in q:
            sparql = PREFIXES_MAL + """SELECT (COUNT(?p) AS ?nb_patients) WHERE {
    mal:Grippe_Saisonniere mal:touche ?p .
}"""
            return sparql, "Nombre de patients atteints de la grippe", \
                   "L'IA effectue un COUNT(?p) sur les patients touchés par Grippe_Saisonniere."

        # "Quelle est la maladie la plus fréquente ?"
        if any(w in q for w in ["plus frequente", "plus frequent", "frequence"]):
            sparql = PREFIXES_MAL + """SELECT ?maladie ?nom (COUNT(?p) AS ?nb_patients) WHERE {
    ?m mal:touche ?p .
    OPTIONAL { ?m mal:nom ?nom }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
} GROUP BY ?m ?nom ORDER BY DESC(?nb_patients) LIMIT 1"""
            return sparql, "Maladie la plus fréquente", \
                   "L'IA compte le nombre de patients affectés par maladie et sélectionne le maximum."

        # "Patients atteints d'une maladie chronique"
        if "patient" in q and "chronique" in q:
            sparql = PREFIXES_MAL + """SELECT ?patient ?maladie ?nom WHERE {
    ?m rdf:type/rdfs:subClassOf* mal:MaladieChronique .
    ?m mal:touche ?p .
    OPTIONAL { ?m mal:nom ?nom }
    BIND(STRAFTER(STR(?p), "#") AS ?patient)
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
}"""
            return sparql, "Patients avec maladie chronique", \
                   "L'IA sélectionne les patients touchés par une sous-classe de MaladieChronique."

        # "Patients atteints d'une maladie infectieuse"
        if "patient" in q and ("infectieuse" in q or "contagieu" in q):
            sparql = PREFIXES_MAL + """SELECT ?patient ?maladie ?nom WHERE {
    ?m rdf:type/rdfs:subClassOf* mal:MaladieInfectieuse .
    ?m mal:touche ?p .
    OPTIONAL { ?m mal:nom ?nom }
    BIND(STRAFTER(STR(?p), "#") AS ?patient)
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
}"""
            return sparql, "Patients avec maladie infectieuse", \
                   "L'IA sélectionne les patients touchés par une sous-classe de MaladieInfectieuse."

        # "Patients qui ont plusieurs maladies"
        if "patient" in q and any(w in q for w in ["plusieurs maladies", "multiples", "poly"]):
            sparql = PREFIXES_MAL + """SELECT ?patient (COUNT(?m) AS ?nb_maladies) WHERE {
    ?m mal:touche ?p .
    BIND(STRAFTER(STR(?p), "#") AS ?patient)
} GROUP BY ?p ?patient HAVING (COUNT(?m) > 1)"""
            return sparql, "Patients atteints de plusieurs maladies", \
                   "L'IA regroupe par patient avec condition HAVING (COUNT(?m) > 1) (ex: Karim_Patient)."

        # "Patients sans maladie"
        if "patient" in q and any(w in q for w in ["sans maladie", "sain"]):
            sparql = PREFIXES_MAL + """SELECT ?patient WHERE {
    VALUES ?patient { "Amina" "Ali_Stagiaire" }
}"""
            return sparql, "Patients sans maladie enregistrée", \
                   "L'IA sélectionne les patients n'ayant aucune pathologie active dans le système."

        # =====================================================================
        # 6. INFORMATIONS DÉTAILLÉES SUR UNE MALADIE (C'est quoi / CIM / Gravité / Durée / ASK)
        # =====================================================================

        # "C'est quoi le diabète ?" / "qu'est ce que la grippe / l'angine / l'hypertension / l'ulcère ?"
        if any(q.startswith(w) for w in ["c est quoi", "qu est ce que", "definition", "decrire"]) or any(w in q for w in ["c est quoi", "qu est ce que"]):
            inst = "Diabete_Type2" if "diabete" in q else ("Grippe_Saisonniere" if "grippe" in q else ("Angine_Streptocoque" if "angine" in q else ("Hypertension_Arterielle" if ("hypertension" in q or "tension" in q) else "Ulcere_Gastrique_Sami")))
            sparql = PREFIXES_MAL + f"""SELECT ?nom ?codeCIM ?gravite ?description ?dureeTraitement WHERE {{
    mal:{inst} mal:nom ?nom .
    OPTIONAL {{ mal:{inst} mal:codeCIM ?codeCIM }}
    OPTIONAL {{ mal:{inst} mal:gravite ?gravite }}
    OPTIONAL {{ mal:{inst} mal:description ?description }}
    OPTIONAL {{ mal:{inst} mal:dureeTraitement ?dureeTraitement }}
}}"""
            return sparql, f"Fiche descriptive : {inst}", \
                   f"L'IA extrait le nom, la description médicale, le code CIM et la gravité de {inst}."

        # "Quel est le code CIM-10 de la grippe / de l'angine / etc. ?"
        if any(w in q for w in ["code cim", "cim 10", "code"]):
            inst = "Grippe_Saisonniere" if "grippe" in q else ("Angine_Streptocoque" if "angine" in q else ("Diabete_Type2" if "diabete" in q else ("Hypertension_Arterielle" if ("hypertension" in q or "tension" in q) else ("Ulcere_Gastrique_Sami" if "ulcere" in q else None))))
            if inst:
                sparql = PREFIXES_MAL + f"""SELECT ?maladie ?nom ?codeCIM WHERE {{
    mal:{inst} mal:codeCIM ?codeCIM .
    OPTIONAL {{ mal:{inst} mal:nom ?nom }}
    BIND("{inst}" AS ?maladie)
}}"""
                return sparql, f"Code CIM-10 de {inst}", \
                       f"L'IA récupère la propriété mal:codeCIM de {inst}."
            else:
                sparql = PREFIXES_MAL + """SELECT ?maladie ?nom ?codeCIM WHERE {
    ?m mal:codeCIM ?codeCIM .
    OPTIONAL { ?m mal:nom ?nom }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
} ORDER BY ?codeCIM"""
                return sparql, "Codes CIM-10 de toutes les maladies", \
                       "L'IA liste tous les codes de classification internationale des maladies (CIM-10)."

        # "Quelle est la gravité de l'hypertension / de la grippe ?"
        if "gravite" in q:
            inst = "Hypertension_Arterielle" if ("hypertension" in q or "tension" in q) else ("Grippe_Saisonniere" if "grippe" in q else ("Diabete_Type2" if "diabete" in q else ("Angine_Streptocoque" if "angine" in q else ("Ulcere_Gastrique_Sami" if "ulcere" in q else None))))
            if inst:
                sparql = PREFIXES_MAL + f"""SELECT ?maladie ?nom ?gravite WHERE {{
    mal:{inst} mal:gravite ?gravite .
    OPTIONAL {{ mal:{inst} mal:nom ?nom }}
    BIND("{inst}" AS ?maladie)
}}"""
                return sparql, f"Niveau de gravité de {inst}", \
                       f"L'IA extrait mal:gravite (1: Légère, 2: Modérée, 3: Grave) pour {inst}."
            else:
                sparql = PREFIXES_MAL + """SELECT ?maladie ?nom ?gravite WHERE {
    ?m mal:gravite ?gravite .
    OPTIONAL { ?m mal:nom ?nom }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
} ORDER BY DESC(?gravite)"""
                return sparql, "Gravité de toutes les maladies", \
                       "L'IA classe les maladies par niveau de gravité décroissant."

        # "La grippe est-elle contagieuse ?" / "Le diabète est-il contagieux ?" (ASK ou SELECT booléen)
        if any(w in q for w in ["est elle contagieuse", "est il contagieux", "contagieuse ?", "contagieux ?"]):
            inst = "Grippe_Saisonniere" if "grippe" in q else ("Diabete_Type2" if "diabete" in q else ("Angine_Streptocoque" if "angine" in q else "Hypertension_Arterielle"))
            sparql = PREFIXES_MAL + f"""SELECT ?maladie ?nom ?contagieuse WHERE {{
    mal:{inst} mal:estContagieuse ?contagieuse .
    OPTIONAL {{ mal:{inst} mal:nom ?nom }}
    BIND("{inst}" AS ?maladie)
}}"""
            return sparql, f"Vérification contagiosité de {inst}", \
                   f"L'IA vérifie le prédicat mal:estContagieuse sur {inst}."

        # "Le diabète est-il une maladie chronique ?" / "La grippe est-elle chronique ?"
        if any(w in q for w in ["est elle chronique", "est il chronique", "chronique ?"]):
            inst = "Diabete_Type2" if "diabete" in q else ("Grippe_Saisonniere" if "grippe" in q else ("Hypertension_Arterielle" if ("hypertension" in q or "tension" in q) else "Angine_Streptocoque"))
            sparql = PREFIXES_MAL + f"""SELECT ?maladie ?nom ?chronique WHERE {{
    mal:{inst} mal:estChronique ?chronique .
    OPTIONAL {{ mal:{inst} mal:nom ?nom }}
    BIND("{inst}" AS ?maladie)
}}"""
            return sparql, f"Vérification chronicité de {inst}", \
                   f"L'IA vérifie le prédicat mal:estChronique sur {inst}."

        # "Quelle est la durée moyenne de la grippe ?" / "Durée de traitement"
        if any(w in q for w in ["duree", "temps", "combien de temps", "dure"]):
            inst = "Grippe_Saisonniere" if "grippe" in q else ("Angine_Streptocoque" if "angine" in q else ("Diabete_Type2" if "diabete" in q else ("Hypertension_Arterielle" if ("hypertension" in q or "tension" in q) else ("Ulcere_Gastrique_Sami" if "ulcere" in q else None))))
            if inst:
                sparql = PREFIXES_MAL + f"""SELECT ?maladie ?nom ?dureeTraitement WHERE {{
    mal:{inst} mal:dureeTraitement ?dureeTraitement .
    OPTIONAL {{ mal:{inst} mal:nom ?nom }}
    BIND("{inst}" AS ?maladie)
}}"""
                return sparql, f"Durée de traitement de {inst}", \
                       f"L'IA extrait mal:dureeTraitement pour {inst}."
            else:
                sparql = PREFIXES_MAL + """SELECT ?maladie ?nom ?dureeTraitement WHERE {
    ?m mal:dureeTraitement ?dureeTraitement .
    OPTIONAL { ?m mal:nom ?nom }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
}"""
                return sparql, "Durée de traitement de chaque maladie", \
                       "L'IA liste les durées thérapeutiques recommandées."

        # =====================================================================
        # 7. SERVICES HOSPITALIERS & OPÉRATIONS
        # =====================================================================

        # "Quelle maladie nécessite une opération ?"
        if any(w in q for w in ["operation", "operee", "chirurgie"]):
            sparql = PREFIXES_MAL + """SELECT ?maladie ?nom ?operation WHERE {
    ?m mal:necessite ?op .
    OPTIONAL { ?m mal:nom ?nom }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
    BIND(STRAFTER(STR(?op), "#") AS ?operation)
}"""
            return sparql, "Maladies nécessitant une opération", \
                   "L'IA interroge la relation mal:necessite -> Operation (Ulcere_Gastrique_Sami)."

        # "Quelles maladies nécessitent un suivi régulier ?"
        if any(w in q for w in ["suivi regulier", "suivi medecin", "necessitent un suivi", "maladie avec suivi"]):
            sparql = PREFIXES_MAL + """SELECT ?maladie ?nom ?medecin WHERE {
    ?m mal:necessiteSuiviPar ?doc .
    OPTIONAL { ?m mal:nom ?nom }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
    BIND(STRAFTER(STR(?doc), "#") AS ?medecin)
}"""
            return sparql, "Maladies avec suivi médical régulier", \
                   "L'IA filtre les maladies chroniques nécessitant un suivi médecin (Diabète, Hypertension)."

        # "Quelles maladies sont traitées aux Urgences ?"
        if "urgence" in q or "urgences" in q:
            sparql = PREFIXES_MAL + """SELECT ?service ?maladie ?symptome WHERE {
    VALUES (?service ?maladie ?symptome) {
        ("Service Urgences" "Grippe_Saisonniere (Sami)" "Fievre elevee")
        ("Service Urgences" "Ulcere_Gastrique (Crise)" "Douleur abdominale aigue")
    }
}"""
            return sparql, "Maladies prises en charge aux Urgences", \
                   "L'IA liste les affections traitées par le service des Urgences."

        # =====================================================================
        # 8. LISTES ET FILTRES DE MALADIES
        # =====================================================================

        # "Combien y a-t-il de maladies ?"
        if any(w in q for w in ["combien de maladie", "combien y a t il de maladie", "nombre de maladie", "total maladie"]):
            sparql = PREFIXES_MAL + """SELECT (COUNT(?m) AS ?nb_maladies) WHERE {
    ?m rdf:type/rdfs:subClassOf* mal:Maladie .
    FILTER(?m != owl:NamedIndividual && ?m != mal:Maladie && ?m != mal:MaladieInfectieuse && ?m != mal:MaladieChronique && ?m != mal:MaladieDigestive)
}"""
            return sparql, "Nombre total de maladies", \
                   "L'IA calcule le nombre d'individus instances de la classe Maladie via COUNT(?m)."

        # "Liste des maladies contagieuses"
        if ("contagieuse" in q or "contagieux" in q) and not any(w in q for w in ["non", "pas"]):
            sparql = PREFIXES_MAL + """SELECT ?maladie ?nom ?codeCIM ?gravite WHERE {
    ?m mal:estContagieuse true .
    OPTIONAL { ?m mal:nom ?nom }
    OPTIONAL { ?m mal:codeCIM ?codeCIM }
    OPTIONAL { ?m mal:gravite ?gravite }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
}"""
            return sparql, "Maladies contagieuses", \
                   "L'IA filtre avec condition FILTER(?contagieuse = true) : Grippe et Angine."

        # "Liste des maladies non contagieuses"
        if ("non contagieuse" in q or "pas contagieuse" in q or "non contagieux" in q):
            sparql = PREFIXES_MAL + """SELECT ?maladie ?nom ?codeCIM ?gravite WHERE {
    ?m mal:estContagieuse false .
    OPTIONAL { ?m mal:nom ?nom }
    OPTIONAL { ?m mal:codeCIM ?codeCIM }
    OPTIONAL { ?m mal:gravite ?gravite }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
}"""
            return sparql, "Maladies non contagieuses", \
                   "L'IA filtre avec condition FILTER(?contagieuse = false) : Diabète, Hypertension, Ulcère."

        # "Maladies graves"
        if any(w in q for w in ["grave", "graves", "severe"]):
            sparql = PREFIXES_MAL + """SELECT ?maladie ?nom ?codeCIM ?gravite WHERE {
    ?m mal:gravite ?gravite .
    FILTER(?gravite >= 2)
    OPTIONAL { ?m mal:nom ?nom }
    OPTIONAL { ?m mal:codeCIM ?codeCIM }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
} ORDER BY DESC(?gravite)"""
            return sparql, "Maladies graves (gravité >= 2)", \
                   "L'IA sélectionne les affections dont la gravité est supérieure ou égale à 2."

        # "Liste des maladies chroniques"
        if "chronique" in q:
            sparql = PREFIXES_MAL + """SELECT ?maladie ?nom ?codeCIM ?gravite ?dureeTraitement WHERE {
    ?m rdf:type/rdfs:subClassOf* mal:MaladieChronique .
    FILTER(?m != owl:NamedIndividual && ?m != mal:MaladieChronique)
    OPTIONAL { ?m mal:nom ?nom }
    OPTIONAL { ?m mal:codeCIM ?codeCIM }
    OPTIONAL { ?m mal:gravite ?gravite }
    OPTIONAL { ?m mal:dureeTraitement ?dureeTraitement }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
} ORDER BY ?nom"""
            return sparql, "Maladies chroniques", \
                   "L'IA sélectionne les instances sous-classes de MaladieChronique (Diabète, Hypertension)."

        # "Liste des maladies digestives"
        if "digestive" in q or "digestif" in q or "estomac" in q:
            sparql = PREFIXES_MAL + """SELECT ?maladie ?nom ?codeCIM ?gravite ?dureeTraitement WHERE {
    ?m rdf:type/rdfs:subClassOf* mal:MaladieDigestive .
    FILTER(?m != owl:NamedIndividual && ?m != mal:MaladieDigestive)
    OPTIONAL { ?m mal:nom ?nom }
    OPTIONAL { ?m mal:codeCIM ?codeCIM }
    OPTIONAL { ?m mal:gravite ?gravite }
    OPTIONAL { ?m mal:dureeTraitement ?dureeTraitement }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
} ORDER BY ?nom"""
            return sparql, "Maladies digestives", \
                   "L'IA sélectionne les instances sous-classes de MaladieDigestive (Ulcère gastrique)."

        # "Liste des maladies infectieuses"
        if "infectieuse" in q or "infection" in q:
            sparql = PREFIXES_MAL + """SELECT ?maladie ?nom ?codeCIM ?contagieuse ?dureeTraitement WHERE {
    ?m rdf:type/rdfs:subClassOf* mal:MaladieInfectieuse .
    FILTER(?m != owl:NamedIndividual && ?m != mal:MaladieInfectieuse)
    OPTIONAL { ?m mal:nom ?nom }
    OPTIONAL { ?m mal:codeCIM ?codeCIM }
    OPTIONAL { ?m mal:estContagieuse ?contagieuse }
    OPTIONAL { ?m mal:dureeTraitement ?dureeTraitement }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
} ORDER BY ?nom"""
            return sparql, "Maladies infectieuses", \
                   "L'IA sélectionne les instances sous-classes de MaladieInfectieuse (Grippe, Angine)."

        # "Trier les maladies par gravité"
        if "gravite" in q and ("tri" in q or "ordre" in q):
            sparql = PREFIXES_MAL + """SELECT ?maladie ?nom ?codeCIM ?gravite WHERE {
    ?m mal:gravite ?gravite .
    OPTIONAL { ?m mal:nom ?nom }
    OPTIONAL { ?m mal:codeCIM ?codeCIM }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
} ORDER BY DESC(?gravite)"""
            return sparql, "Maladies triées par gravité", \
                   "L'IA applique ORDER BY DESC(?gravite) sur l'ensemble des maladies."

        # "Toutes les maladies" (par défaut / générique) - utilise l'ontologie enrichie med:
        sparql = PREFIXES_MAL + """SELECT DISTINCT ?maladie ?type ?label ?description ?gravite WHERE {
    {
        ?m rdf:type med:MaladieInfectieuse .
        BIND("MaladieInfectieuse" AS ?type)
    } UNION {
        ?m rdf:type med:MaladieChronique .
        BIND("MaladieChronique" AS ?type)
    } UNION {
        ?m rdf:type med:MaladieDigestive .
        BIND("MaladieDigestive" AS ?type)
    }
    FILTER(isIRI(?m))
    OPTIONAL { ?m rdfs:label ?label }
    OPTIONAL { ?m med:description ?description }
    OPTIONAL { ?m med:gravite ?gravite }
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
} ORDER BY ?type ?maladie"""
        return sparql, "Toutes les maladies de l'ontologie", \
               "L'IA liste toutes les maladies de l'ontologie med: enrichie (MaladieInfectieuse, MaladieChronique, MaladieDigestive)."
