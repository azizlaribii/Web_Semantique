# -*- coding: utf-8 -*-
"""
Module IA Médicament : question en langage naturel -> requête SPARQL exécutable.

Architecture OntoSanté :
Front-end -> Module IA (NLP spaCy + scikit-learn) -> SPARQL -> RDFLib (ontologie_medicament.owl)

1. nlp_medicament.NLPMedicamentPipeline analyse la question (spaCy) :
   tokens, lemmes, entités de l'ontologie, intention (classifieur scikit-learn), paramètres.
2. Ce module choisit le gabarit SPARQL correspondant à l'intention et le remplit
   avec les entités reconnues (slot filling), puis l'exécute sur le graphe RDFLib.
"""

from typing import Dict, Any, Tuple, List, Optional

from medicament_service import PREFIXES_MDC, CLASSES_THERAPEUTIQUES
from nlp_medicament import NLPMedicamentPipeline

CLASSES_IN = ", ".join(f"mdc:{c}" for c in CLASSES_THERAPEUTIQUES)

# Paramètres obligatoires pour qu'une intention soit retenue
REQUIRED = {
    "fiche_medicament": lambda e: bool(e["meds"]),
    "classe_therapeutique": lambda e: bool(e["classe"]),
    "traitement": lambda e: bool(e["meds"] or e["maladie"]),
}

LIBELLES_CLASSES = {
    "Antibiotique": "antibiotiques", "AntiInflammatoire": "anti-inflammatoires", "Antalgique": "antalgiques",
    "Antidiabetique": "antidiabétiques", "Antihypertenseur": "antihypertenseurs",
    "AntiUlcereux": "anti-ulcéreux", "Anticoagulant": "anticoagulants",
}
LIBELLES_FAMILLES = {
    "EffetDigestif": "digestifs", "EffetNeurologique": "neurologiques", "EffetCutane": "cutanés",
    "EffetCardiovasculaire": "cardiovasculaires", "EffetHepatique": "hépatiques",
    "EffetHematologique": "hématologiques", "EffetMetabolique": "métaboliques",
}


class IAMedicamentService:
    """Traducteur NL -> SPARQL pour le module Médicament."""

    def __init__(self, medicament_service):
        self.service = medicament_service
        self.nlp = NLPMedicamentPipeline(medicament_service)

    def refresh(self):
        """Recharge le vocabulaire d'entités (après un ajout / une suppression)."""
        self.nlp.refresh_entities()

    # ------------------------------------------------------------------
    def answer_question(self, question: str) -> Dict[str, Any]:
        analyse = self.nlp.analyse(question)
        entites = self._resoudre(analyse)
        intent, confiance = self._choisir_intention(analyse, entites)
        sparql, intention, explication = self._generer(intent, entites, analyse["slots"])
        try:
            raw = self.service.execute_sparql(sparql)
        except Exception as e:
            raw = {"head": {"vars": []}, "results": {"bindings": []}, "error": str(e)}
        analyse["intention_retenue"] = {"intention": intent, "confiance": confiance}
        analyse["outils"] = self.nlp.outils()
        return {"intention": intention, "explication": explication, "sparql": sparql,
                "data": raw, "nlp": analyse}

    def translate(self, question: str) -> Tuple[str, str, str]:
        """Utilisé par les tests : retourne (sparql, intention, explication)."""
        r = self.answer_question(question)
        return r["sparql"], r["intention"], r["explication"]

    # ------------------------------------------------------------------
    def _resoudre(self, analyse) -> Dict[str, Any]:
        """Regroupe les entités reconnues par type (ids OWL)."""
        def ids(t):
            out = []
            for e in analyse["entites"]:
                if e["type"] == t:
                    out += [i for i in e["ids"] if i not in out]
            return out

        meds_explicites = ids("MEDICAMENT")
        mols = ids("MOLECULE")
        meds = list(meds_explicites)
        for mol in mols:                         # une molécule désigne les médicaments qui la contiennent
            for r in self.service._rows(f"SELECT ?m WHERE {{ ?m mdc:contientMolecule mdc:{mol} }}"):
                mid = r["m"].split("#")[-1]
                if mid not in meds:
                    meds.append(mid)
        first = lambda l: l[0] if l else None
        return {
            "meds": meds, "meds_explicites": meds_explicites, "mol": first(mols),
            "maladie": first(ids("MALADIE")), "condition": first(ids("CONDITION")),
            "effets": ids("EFFET"), "famille": first(ids("FAMILLE_EFFET")), "classe": first(ids("CLASSE")),
        }

    @staticmethod
    def _choisir_intention(analyse, entites) -> Tuple[str, float]:
        """Intention la plus probable dont les paramètres obligatoires sont présents."""
        for cand in analyse["intentions"]:
            check = REQUIRED.get(cand["intention"])
            if check is None or check(entites):
                return cand["intention"], cand["confiance"]
        return "lister_medicaments", 0.0

    # ------------------------------------------------------------------
    # Gabarits SPARQL par intention
    # ------------------------------------------------------------------
    def _generer(self, intent: str, e: Dict[str, Any], s: Dict[str, Any]) -> Tuple[str, str, str]:
        gen = getattr(self, f"_q_{intent}", self._q_lister_medicaments)
        return gen(e, s)

    P = PREFIXES_MDC

    def _q_lister_medicaments(self, e, s):
        return self.P + """SELECT ?medicament ?molecule ?dosage ?prixTND ?ordonnance WHERE {
    ?m mdc:nomCommercial ?medicament .
    OPTIONAL { ?m mdc:contientMolecule/mdc:nomMolecule ?molecule }
    OPTIONAL { ?m mdc:dosage ?dosage }
    OPTIONAL { ?m mdc:prixTND ?prixTND }
    OPTIONAL { ?m mdc:necessiteOrdonnance ?ordonnance }
} ORDER BY ?medicament""", "Tous les médicaments de l'ontologie", \
            "Liste de l'ensemble des médicaments avec leur molécule, dosage, prix et statut d'ordonnance."

    def _q_effets_secondaires(self, e, s):
        P = self.P
        if not e["famille"] and e["condition"] == "Insuffisance_Hepatique_Severe":
            e = {**e, "famille": "EffetHepatique"}      # « effets sur le foie »
        if s["grave"] and not e["meds"]:
            return P + """SELECT ?effet ?frequence ?medicament WHERE {
    ?e rdf:type mdc:EffetGrave ;
       mdc:nomEffet ?effet ;
       mdc:frequence ?frequence .
    ?m mdc:peutProvoquer ?e ; mdc:nomCommercial ?medicament .
} ORDER BY ?effet""", "Effets secondaires graves", \
                "mdc:EffetGrave est une classe définie (EffetSecondaire ⊓ graviteEffet = 3) inférée par le raisonneur."
        if e["meds"]:
            med = e["meds"][0]
            return P + f"""SELECT ?effet ?famille ?frequence ?gravite WHERE {{
    mdc:{med} mdc:peutProvoquer ?e .
    ?e mdc:nomEffet ?effet ; rdf:type ?t .
    ?t rdfs:subClassOf mdc:EffetSecondaire .
    FILTER(?t != mdc:EffetGrave)
    OPTIONAL {{ ?e mdc:frequence ?frequence }}
    OPTIONAL {{ ?e mdc:graviteEffet ?gravite }}
    BIND(STRAFTER(STR(?t), "#") AS ?famille)
}} ORDER BY DESC(?gravite)""", f"Effets secondaires de {med}", \
                f"Relation mdc:peutProvoquer suivie depuis mdc:{med}, triée par gravité."
        if e["effets"]:
            values = " ".join(f"mdc:{x}" for x in e["effets"])
            return P + f"""SELECT ?medicament ?effet ?frequence WHERE {{
    VALUES ?e {{ {values} }}
    ?m mdc:peutProvoquer ?e ; mdc:nomCommercial ?medicament .
    ?e mdc:nomEffet ?effet .
    OPTIONAL {{ ?e mdc:frequence ?frequence }}
}} ORDER BY ?medicament""", "Médicaments provoquant cet effet", \
                f"Médicaments liés à {values} par mdc:peutProvoquer."
        if e["famille"]:
            cls = e["famille"]
            return P + f"""SELECT ?effet ?medicament ?frequence ?gravite WHERE {{
    ?e rdf:type mdc:{cls} ; mdc:nomEffet ?effet .
    ?m mdc:peutProvoquer ?e ; mdc:nomCommercial ?medicament .
    OPTIONAL {{ ?e mdc:frequence ?frequence }}
    OPTIONAL {{ ?e mdc:graviteEffet ?gravite }}
}} ORDER BY ?effet""", f"Effets secondaires {LIBELLES_FAMILLES.get(cls, cls)}", \
                f"Instances de la sous-classe mdc:{cls}."
        return P + """SELECT ?medicament ?effet ?frequence ?gravite WHERE {
    ?m mdc:peutProvoquer ?e ; mdc:nomCommercial ?medicament .
    ?e mdc:nomEffet ?effet .
    OPTIONAL { ?e mdc:frequence ?frequence }
    OPTIONAL { ?e mdc:graviteEffet ?gravite }
} ORDER BY ?medicament DESC(?gravite)""", "Effets secondaires de tous les médicaments", \
            "Parcours de toutes les relations mdc:peutProvoquer."

    def _q_medicaments_a_risque(self, e, s):
        if e["meds"]:                                     # « risques de l'Amlor » -> effets de ce médicament
            return self._q_effets_secondaires(e, s)
        return self.P + """SELECT ?medicament ?effetGrave WHERE {
    ?m rdf:type mdc:MedicamentARisque ;
       mdc:nomCommercial ?medicament ;
       mdc:peutProvoquer ?e .
    ?e mdc:graviteEffet 3 ; mdc:nomEffet ?effetGrave .
} ORDER BY ?medicament""", "Médicaments à risque (classe inférée)", \
            "mdc:MedicamentARisque est une classe définie (Medicament ⊓ ∃peutProvoquer.EffetGrave) remplie par le raisonneur."

    def _q_contre_indications(self, e, s):
        P = self.P
        if e["meds"]:
            med = e["meds"][0]
            return P + f"""SELECT ?contreIndication ?type WHERE {{
    {{
        mdc:{med} mdc:estContreIndiqueEn ?c .
        ?c mdc:nomCondition ?contreIndication .
        BIND("Condition clinique" AS ?type)
    }} UNION {{
        mdc:{med} mdc:estContreIndiquePour ?mal .
        OPTIONAL {{ ?mal mal:nom ?nomMal }}
        BIND(COALESCE(?nomMal, STRAFTER(STR(?mal), "#")) AS ?contreIndication)
        BIND("Maladie (module Maladie)" AS ?type)
    }}
}}""", f"Contre-indications de {med}", \
                f"UNION des conditions cliniques et des maladies (module Maladie) contre-indiquées pour mdc:{med}."
        if e["maladie"]:
            mal = e["maladie"]
            return P + f"""SELECT ?medicament (GROUP_CONCAT(DISTINCT ?cl; separator=", ") AS ?classe) WHERE {{
    ?m mdc:estContreIndiquePour mal:{mal} ;
       mdc:nomCommercial ?medicament ;
       rdf:type ?c .
    FILTER(?c IN ({CLASSES_IN}))
    BIND(STRAFTER(STR(?c), "#") AS ?cl)
}} GROUP BY ?medicament""", f"Médicaments contre-indiqués : {mal.replace('_', ' ')}", \
                f"Requête croisée Médicament ↔ Maladie : ?m mdc:estContreIndiquePour mal:{mal}."
        if e["condition"]:
            c = e["condition"]
            return P + f"""SELECT ?medicament ?condition WHERE {{
    ?m mdc:estContreIndiqueEn mdc:{c} ;
       mdc:nomCommercial ?medicament .
    mdc:{c} mdc:nomCondition ?condition .
}}""", f"Médicaments contre-indiqués : {c.replace('_', ' ')}", \
                f"Médicaments liés à mdc:{c} par mdc:estContreIndiqueEn."
        if s["negation"]:
            return P + """SELECT ?medicament WHERE {
    ?m mdc:nomCommercial ?medicament .
    FILTER NOT EXISTS { ?m mdc:estContreIndiqueEn ?c }
    FILTER NOT EXISTS { ?m mdc:estContreIndiquePour ?mal }
}""", "Médicaments sans contre-indication enregistrée", \
                "Négation détectée : FILTER NOT EXISTS sur mdc:estContreIndiqueEn et mdc:estContreIndiquePour."
        return P + """SELECT ?medicament ?contreIndication ?type WHERE {
    ?m mdc:nomCommercial ?medicament .
    {
        ?m mdc:estContreIndiqueEn ?c . ?c mdc:nomCondition ?contreIndication .
        BIND("Condition clinique" AS ?type)
    } UNION {
        ?m mdc:estContreIndiquePour ?mal .
        OPTIONAL { ?mal mal:nom ?nomMal }
        BIND(COALESCE(?nomMal, STRAFTER(STR(?mal), "#")) AS ?contreIndication)
        BIND("Maladie" AS ?type)
    }
} ORDER BY ?medicament""", "Toutes les contre-indications", \
            "Chaque médicament avec ses contre-indications (conditions cliniques et maladies)."

    def _q_interactions(self, e, s):
        P = self.P
        meds = e["meds"]
        if len(meds) >= 2:
            a, b = meds[0], meds[1]
            return P + f"""SELECT ?medicament1 ?medicament2 ?niveauRisque ?description WHERE {{
    ?i mdc:impliqueMedicament mdc:{a} , mdc:{b} .
    OPTIONAL {{ ?i mdc:niveauRisque ?niveauRisque }}
    OPTIONAL {{ ?i mdc:descriptionInteraction ?description }}
    BIND("{a}" AS ?medicament1)
    BIND("{b}" AS ?medicament2)
}}""", f"Interaction entre {a} et {b}", \
                f"Recherche d'une InteractionMedicamenteuse impliquant mdc:{a} et mdc:{b}. " \
                "Aucun résultat signifie qu'aucune interaction n'est enregistrée."
        if meds:
            med = meds[0]
            return P + f"""SELECT ?autreMedicament ?niveauRisque ?description WHERE {{
    ?i mdc:impliqueMedicament mdc:{med} , ?autre .
    FILTER(?autre != mdc:{med})
    OPTIONAL {{ ?i mdc:niveauRisque ?niveauRisque }}
    OPTIONAL {{ ?i mdc:descriptionInteraction ?description }}
    BIND(STRAFTER(STR(?autre), "#") AS ?autreMedicament)
}}""", f"Interactions de {med}", \
                f"Interactions réifiées où mdc:{med} est impliqué (mdc:impliqueMedicament)."
        return P + """SELECT ?medicament1 ?medicament2 ?niveauRisque ?description WHERE {
    ?i a mdc:InteractionMedicamenteuse ;
       mdc:impliqueMedicament ?m1 , ?m2 .
    FILTER(STR(?m1) < STR(?m2))
    OPTIONAL { ?i mdc:niveauRisque ?niveauRisque }
    OPTIONAL { ?i mdc:descriptionInteraction ?description }
    BIND(STRAFTER(STR(?m1), "#") AS ?medicament1)
    BIND(STRAFTER(STR(?m2), "#") AS ?medicament2)
    BIND(IF(?niveauRisque = "Eleve", 3, IF(?niveauRisque = "Modere", 2, 1)) AS ?ordre)
} ORDER BY DESC(?ordre)""", "Toutes les interactions médicamenteuses", \
            "Individus de mdc:InteractionMedicamenteuse, du risque le plus élevé au plus faible."

    def _q_molecule(self, e, s):
        P = self.P
        if e["mol"] and not e["meds_explicites"]:
            mol = e["mol"]
            return P + f"""SELECT ?medicament ?dosage ?forme WHERE {{
    ?m mdc:contientMolecule mdc:{mol} ;
       mdc:nomCommercial ?medicament .
    OPTIONAL {{ ?m mdc:dosage ?dosage }}
    OPTIONAL {{ ?m mdc:formeGalenique ?forme }}
}}""", f"Médicaments contenant {mol.replace('Mol_', '').replace('_', ' ')}", \
                f"Relation parcourue dans l'autre sens : ?m mdc:contientMolecule mdc:{mol}."
        med = e["meds"][0] if e["meds"] else None
        filtre = f"FILTER(?m = mdc:{med})" if med else ""
        return P + f"""SELECT ?medicament ?molecule ?formuleBrute ?masseMolaire WHERE {{
    ?m mdc:contientMolecule ?mol ; mdc:nomCommercial ?medicament .
    {filtre}
    ?mol mdc:nomMolecule ?molecule .
    OPTIONAL {{ ?mol mdc:formuleBrute ?formuleBrute }}
    OPTIONAL {{ ?mol mdc:masseMolaire ?masseMolaire }}
}} ORDER BY ?medicament""", f"Molécule(s){' de ' + med if med else ' des médicaments'}", \
            "mdc:contientMolecule, puis formule brute et masse molaire."

    def _q_traitement(self, e, s):
        P = self.P
        if e["maladie"] and not e["meds"]:
            mal = e["maladie"]
            return P + f"""SELECT ?medicament (GROUP_CONCAT(DISTINCT ?cl; separator=", ") AS ?classe) ?posologie WHERE {{
    ?m mdc:traite mal:{mal} ;
       mdc:nomCommercial ?medicament ;
       rdf:type ?c .
    FILTER(?c IN ({CLASSES_IN}))
    OPTIONAL {{ ?m mdc:posologie ?posologie }}
    BIND(STRAFTER(STR(?c), "#") AS ?cl)
}} GROUP BY ?medicament ?posologie""", f"Médicaments qui traitent : {mal.replace('_', ' ')}", \
                f"Requête croisée Médicament ↔ Maladie : ?m mdc:traite mal:{mal}."
        med = e["meds"][0]
        return P + f"""SELECT ?maladie ?codeCIM WHERE {{
    mdc:{med} mdc:traite ?mal .
    OPTIONAL {{ ?mal mal:nom ?nom }}
    OPTIONAL {{ ?mal mal:codeCIM ?codeCIM }}
    BIND(COALESCE(?nom, STRAFTER(STR(?mal), "#")) AS ?maladie)
}}""", f"Maladies traitées par {med}", \
            f"mdc:traite suivi depuis mdc:{med} vers les individus du module Maladie (nom, code CIM-10)."

    def _q_essais_cliniques(self, e, s):
        P = self.P
        med = e["meds"][0] if e["meds"] else None
        if s["negation"] and not med:
            return P + """SELECT ?medicament WHERE {
    ?m mdc:nomCommercial ?medicament .
    FILTER NOT EXISTS { ?m rdf:type mdc:MedicamentEvalueCliniquement }
}""", "Médicaments sans essai clinique", \
                "Négation détectée : exclusion de la classe inférée mdc:MedicamentEvalueCliniquement."
        if s["superlatif"] and not med:
            return P + """SELECT ?medicament ?tauxEfficacite ?nombrePatients ?objectif WHERE {
    ?essai mdc:evalue ?m ; mdc:tauxEfficacite ?tauxEfficacite .
    ?m mdc:nomCommercial ?medicament .
    OPTIONAL { ?essai mdc:nombrePatients ?nombrePatients }
    OPTIONAL { ?essai mdc:objectifEssai ?objectif }
} ORDER BY DESC(?tauxEfficacite) LIMIT 3""", "Médicaments les plus efficaces (essais cliniques)", \
                "Superlatif détecté : tri par mdc:tauxEfficacite décroissant (ORDER BY DESC, LIMIT 3)."
        filtre = f"FILTER(?m = mdc:{med})" if med else ""
        return P + f"""SELECT ?essai ?medicament ?phase ?nombrePatients ?tauxEfficacite ?annee ?objectif WHERE {{
    ?e mdc:evalue ?m ; mdc:phase ?phase ; mdc:nombrePatients ?nombrePatients ;
       mdc:tauxEfficacite ?tauxEfficacite ; mdc:anneeEssai ?annee .
    {filtre}
    ?m mdc:nomCommercial ?medicament .
    OPTIONAL {{ ?e mdc:objectifEssai ?objectif }}
    BIND(STRAFTER(STR(?e), "#") AS ?essai)
}} ORDER BY DESC(?tauxEfficacite)""", f"Essais cliniques{' de ' + med if med else ''}", \
            "Données cliniques (phase, patients, efficacité, année) via mdc:evalue."

    def _q_ordonnance(self, e, s):
        P = self.P
        if e["meds"]:
            med = e["meds"][0]
            return P + f"""SELECT ?medicament ?ordonnance WHERE {{
    mdc:{med} mdc:nomCommercial ?medicament ; mdc:necessiteOrdonnance ?ordonnance .
}}""", f"{med} nécessite-t-il une ordonnance ?", f"Lecture de mdc:necessiteOrdonnance de mdc:{med}."
        if s["negation"] or s["libre"]:
            return P + """SELECT ?medicament ?prixTND WHERE {
    ?m mdc:nomCommercial ?medicament ; mdc:necessiteOrdonnance false .
    OPTIONAL { ?m mdc:prixTND ?prixTND }
} ORDER BY ?medicament""", "Médicaments sans ordonnance", \
                "Filtre sur mdc:necessiteOrdonnance false."
        return P + """SELECT ?medicament ?prixTND WHERE {
    ?m rdf:type mdc:MedicamentSurOrdonnance ; mdc:nomCommercial ?medicament .
    OPTIONAL { ?m mdc:prixTND ?prixTND }
} ORDER BY ?medicament""", "Médicaments sur ordonnance (classe inférée)", \
            "mdc:MedicamentSurOrdonnance est une classe définie (necessiteOrdonnance = true) remplie par le raisonneur."

    def _q_prix(self, e, s):
        P = self.P
        if e["meds"]:
            med = e["meds"][0]
            return P + f"""SELECT ?medicament ?prixTND ?dosage WHERE {{
    mdc:{med} mdc:nomCommercial ?medicament ; mdc:prixTND ?prixTND .
    OPTIONAL {{ mdc:{med} mdc:dosage ?dosage }}
}}""", f"Prix de {med}", f"Lecture de mdc:prixTND de mdc:{med}."
        ordre = s["ordre"] or "ASC"
        return P + f"""SELECT ?medicament ?prixTND ?dosage WHERE {{
    ?m mdc:nomCommercial ?medicament ; mdc:prixTND ?prixTND .
    OPTIONAL {{ ?m mdc:dosage ?dosage }}
}} ORDER BY {ordre}(?prixTND)""", "Médicaments triés par prix", \
            f"Tri par mdc:prixTND ({'décroissant' if ordre == 'DESC' else 'croissant'})."

    def _q_posologie(self, e, s):
        med = e["meds"][0] if e["meds"] else None
        filtre = f"FILTER(?m = mdc:{med})" if med else ""
        return self.P + f"""SELECT ?medicament ?dosage ?forme ?posologie WHERE {{
    ?m mdc:nomCommercial ?medicament .
    {filtre}
    OPTIONAL {{ ?m mdc:dosage ?dosage }}
    OPTIONAL {{ ?m mdc:formeGalenique ?forme }}
    OPTIONAL {{ ?m mdc:posologie ?posologie }}
}} ORDER BY ?medicament""", f"Posologie{' de ' + med if med else ' des médicaments'}", \
            "Lecture de mdc:dosage, mdc:formeGalenique et mdc:posologie."

    def _q_classe_therapeutique(self, e, s):
        cls = e["classe"]
        return self.P + f"""SELECT ?medicament ?molecule ?dosage ?codeATC WHERE {{
    ?m rdf:type/rdfs:subClassOf* mdc:{cls} ;
       mdc:nomCommercial ?medicament .
    OPTIONAL {{ ?m mdc:contientMolecule/mdc:nomMolecule ?molecule }}
    OPTIONAL {{ ?m mdc:dosage ?dosage }}
    OPTIONAL {{ ?m mdc:codeATC ?codeATC }}
}} ORDER BY ?medicament""", f"Liste des {LIBELLES_CLASSES.get(cls, cls)}", \
            f"Instances de mdc:{cls} (rdf:type/rdfs:subClassOf*)."

    def _q_comptage(self, e, s):
        return self.P + """SELECT ?classe (COUNT(?m) AS ?nombre) WHERE {
    ?m mdc:nomCommercial ?n ; rdf:type ?c .
    FILTER(?c IN (""" + CLASSES_IN + """))
    BIND(STRAFTER(STR(?c), "#") AS ?classe)
} GROUP BY ?classe ORDER BY DESC(?nombre)""", "Nombre de médicaments par classe thérapeutique", \
            "Regroupement (GROUP BY) par classe et comptage (COUNT)."

    def _q_code_atc(self, e, s):
        med = e["meds"][0] if e["meds"] else None
        filtre = f"FILTER(?m = mdc:{med})" if med else ""
        return self.P + f"""SELECT ?medicament ?codeATC WHERE {{
    ?m mdc:nomCommercial ?medicament ; mdc:codeATC ?codeATC .
    {filtre}
}} ORDER BY ?codeATC""", "Codes ATC des médicaments", \
            "Lecture de mdc:codeATC (classification anatomique, thérapeutique et chimique de l'OMS)."

    def _q_fiche_medicament(self, e, s):
        med = e["meds"][0]
        return self.P + f"""SELECT ?propriete ?valeur WHERE {{
    mdc:{med} ?p ?v .
    FILTER(isLiteral(?v))
    BIND(STRAFTER(STR(?p), "#") AS ?propriete)
    BIND(STR(?v) AS ?valeur)
}}""", f"Fiche du médicament {med}", \
            f"Toutes les propriétés de données (littéraux) de mdc:{med}."
