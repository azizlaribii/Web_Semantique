# -*- coding: utf-8 -*-
"""
Module IA Médicament : Question en langage naturel -> Requête SPARQL formelle
Architecture OntoSanté :
Front-end -> Module IA -> SPARQL -> RDFLib (ontologie_medicament.owl + ontologie_maladie.owl)

Les entités (médicaments, molécules, maladies) sont lues directement dans le graphe
au démarrage : si on ajoute un médicament dans l'ontologie, l'IA le reconnaît
sans modifier ce fichier.
"""

import re
from typing import Dict, Any, Tuple, Optional, List

from medicament_service import PREFIXES_MDC, CLASSES_THERAPEUTIQUES

CLASSES_IN = ", ".join(f"mdc:{c}" for c in CLASSES_THERAPEUTIQUES)


def _norm(text: str) -> str:
    """Minuscules, sans accents ni ponctuation courante."""
    t = text.lower()
    repl = {
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'à': 'a', 'â': 'a', 'ä': 'a',
        'î': 'i', 'ï': 'i',
        'ô': 'o', 'ö': 'o',
        'ù': 'u', 'û': 'u', 'ü': 'u',
        'ç': 'c', "'": ' ', '’': ' ', '-': ' ', '?': ' ', '!': ' ', ',': ' ', '.': ' '
    }
    for k, v in repl.items():
        t = t.replace(k, v)
    return " ".join(t.split())


def _has(q: str, *stems: str) -> bool:
    """Vrai si un des radicaux apparaît. Les mots courts (<= 4 lettres) doivent être
    des mots entiers, pour éviter par ex. que « ains » (AINS) corresponde à « certains »."""
    for s in stems:
        if len(s) <= 4:
            if re.search(rf"\b{re.escape(s)}\b", q):
                return True
        elif s in q:
            return True
    return False


# Classes thérapeutiques : mots-clés -> classe OWL
CLASSES_KW = [
    (("antibiotique",), "Antibiotique", "antibiotiques"),
    (("anti inflammatoire", "antiinflammatoire", "ains"), "AntiInflammatoire", "anti-inflammatoires"),
    (("antalgique", "antidouleur", "anti douleur", "analgesique"), "Antalgique", "antalgiques"),
    (("antidiabetique", "anti diabetique"), "Antidiabetique", "antidiabétiques"),
    (("antihypertenseur", "anti hypertenseur"), "Antihypertenseur", "antihypertenseurs"),
    (("anti ulcereux", "antiulcereux", "anti acide", "ipp"), "AntiUlcereux", "anti-ulcéreux"),
    (("anticoagulant", "anti coagulant"), "Anticoagulant", "anticoagulants"),
]

# Familles d'effets secondaires
EFFETS_KW = [
    (("digestif", "digestive", "estomac"), "EffetDigestif", "digestifs"),
    (("neurologique",), "EffetNeurologique", "neurologiques"),
    (("cutane", "peau"), "EffetCutane", "cutanés"),
    (("cardio",), "EffetCardiovasculaire", "cardiovasculaires"),
    (("hepatique", "foie"), "EffetHepatique", "hépatiques"),
    (("hematologique", "sang"), "EffetHematologique", "hématologiques"),
    (("metabolique",), "EffetMetabolique", "métaboliques"),
]

# Effets précis -> individu OWL
EFFET_PRECIS_KW = [
    (("saignement", "hemorragie"), ["Saignement", "Hemorragie_Digestive"]),
    (("diarrhee",), ["Diarrhee"]),
    (("nausee", "vomi"), ["Nausee_Effet"]),
    (("vertige",), ["Vertige_Effet"]),
    (("maux de tete", "mal de tete", "cephalee"), ["Cephalee_Effet"]),
    (("oedeme", "gonfle"), ["Oedeme_Chevilles"]),
    (("eruption", "urticaire", "bouton"), ["Eruption_Cutanee"]),
    (("acidose",), ["Acidose_Lactique"]),
    (("hepatotox",), ["Hepatotoxicite"]),
]

# Conditions cliniques -> individu OWL
CONDITIONS_KW = [
    (("enceinte", "grossesse"), "Grossesse"),
    (("insuffisance hepatique", "foie"), "Insuffisance_Hepatique_Severe"),
    (("insuffisance renale", "rein", "renal"), "Insuffisance_Renale_Severe"),
    (("allergi", "penicilline"), "Allergie_Penicilline"),
    (("enfant", "reye"), "Enfant_Infection_Virale"),
    (("hypotension",), "Hypotension_Severe"),
]

# Alias simples pour les maladies du module Maladie
MALADIES_ALIAS = [
    (("grippe",), "Grippe_Saisonniere"),
    (("angine",), "Angine_Streptocoque"),
    (("diabete", "diabetique"), "Diabete_Type2"),
    (("hypertension", "hypertendu", "tension arterielle"), "Hypertension_Arterielle"),
    (("ulcere",), "Ulcere_Gastrique_Sami"),
]

MOLECULES_ALIAS = {"aspirine": "Mol_Acide_Acetylsalicylique"}


class IAMedicamentService:
    """Traducteur NL -> SPARQL pour le module Médicament."""

    def __init__(self, medicament_service):
        self.service = medicament_service
        self.med_index: Dict[str, str] = {}   # nom normalisé -> id médicament
        self.mol_index: Dict[str, str] = {}   # nom de molécule normalisé -> id molécule
        self._build_index()

    # ------------------------------------------------------------------
    def _build_index(self):
        if not getattr(self.service, "loaded", False):
            return
        for r in self.service._rows("SELECT ?m ?n WHERE { ?m mdc:nomCommercial ?n }"):
            self.med_index[_norm(r["n"])] = r["m"].split("#")[-1]
        for r in self.service._rows("SELECT ?mol ?n WHERE { ?mol mdc:nomMolecule ?n }"):
            self.mol_index[_norm(r["n"])] = r["mol"].split("#")[-1]
        for alias, mol in MOLECULES_ALIAS.items():
            self.mol_index[alias] = mol

    def _meds_in(self, q: str) -> List[str]:
        """Médicaments cités (par nom commercial ou par molécule), dans l'ordre d'apparition."""
        found = []
        for name, mid in self.med_index.items():
            pos = q.find(name)
            if pos >= 0:
                found.append((pos, mid))
        for name, mol in self.mol_index.items():
            pos = q.find(name)
            if pos >= 0:
                for r in self.service._rows(f"SELECT ?m WHERE {{ ?m mdc:contientMolecule mdc:{mol} }}"):
                    found.append((pos, r["m"].split("#")[-1]))
        out = []
        for _, mid in sorted(found):
            if mid not in out:
                out.append(mid)
        return out

    def _molecule_in(self, q: str) -> Optional[str]:
        for name, mol in self.mol_index.items():
            if name in q:
                return mol
        return None

    @staticmethod
    def _first(q: str, table):
        for row in table:
            if _has(q, *row[0]):
                return row[1:] if len(row) > 2 else row[1]
        return None

    # ------------------------------------------------------------------
    def answer_question(self, question: str) -> Dict[str, Any]:
        q = _norm(question)
        sparql, intention, explication = self._translate(q)
        try:
            raw = self.service.execute_sparql(sparql)
        except Exception as e:
            raw = {"head": {"vars": []}, "results": {"bindings": []}, "error": str(e)}
        return {"intention": intention, "explication": explication, "sparql": sparql, "data": raw}

    def translate(self, question: str) -> Tuple[str, str, str]:
        """Utilisé par les tests : retourne (sparql, intention, explication)."""
        return self._translate(_norm(question))

    # ------------------------------------------------------------------
    def _translate(self, q: str) -> Tuple[str, str, str]:
        P = PREFIXES_MDC
        meds = self._meds_in(q)
        med = meds[0] if meds else None
        maladie = self._first(q, MALADIES_ALIAS)
        condition = self._first(q, CONDITIONS_KW)
        classe = self._first(q, CLASSES_KW)          # (classe, libellé) ou None

        # ==============================================================
        # 1. INTERACTIONS MÉDICAMENTEUSES
        # ==============================================================
        if _has(q, "interaction", "interagi", "associer", "ensemble", "en meme temps", "combiner"):
            if len(meds) >= 2:
                a, b = meds[0], meds[1]
                sparql = P + f"""SELECT ?medicament1 ?medicament2 ?niveauRisque ?description WHERE {{
    ?i mdc:impliqueMedicament mdc:{a} , mdc:{b} .
    OPTIONAL {{ ?i mdc:niveauRisque ?niveauRisque }}
    OPTIONAL {{ ?i mdc:descriptionInteraction ?description }}
    BIND("{a}" AS ?medicament1)
    BIND("{b}" AS ?medicament2)
}}"""
                return sparql, f"Interaction entre {a} et {b}", \
                    f"L'IA cherche une InteractionMedicamenteuse qui implique à la fois mdc:{a} et mdc:{b}. " \
                    "Aucun résultat signifie qu'aucune interaction n'est enregistrée."
            if med:
                sparql = P + f"""SELECT ?autreMedicament ?niveauRisque ?description WHERE {{
    ?i mdc:impliqueMedicament mdc:{med} , ?autre .
    FILTER(?autre != mdc:{med})
    OPTIONAL {{ ?i mdc:niveauRisque ?niveauRisque }}
    OPTIONAL {{ ?i mdc:descriptionInteraction ?description }}
    BIND(STRAFTER(STR(?autre), "#") AS ?autreMedicament)
}}"""
                return sparql, f"Interactions de {med}", \
                    f"L'IA parcourt les interactions réifiées où mdc:{med} est impliqué (mdc:impliqueMedicament)."
            sparql = P + """SELECT ?medicament1 ?medicament2 ?niveauRisque ?description WHERE {
    ?i a mdc:InteractionMedicamenteuse ;
       mdc:impliqueMedicament ?m1 , ?m2 .
    FILTER(STR(?m1) < STR(?m2))
    OPTIONAL { ?i mdc:niveauRisque ?niveauRisque }
    OPTIONAL { ?i mdc:descriptionInteraction ?description }
    BIND(STRAFTER(STR(?m1), "#") AS ?medicament1)
    BIND(STRAFTER(STR(?m2), "#") AS ?medicament2)
    BIND(IF(?niveauRisque = "Eleve", 3, IF(?niveauRisque = "Modere", 2, 1)) AS ?ordre)
} ORDER BY DESC(?ordre)"""
            return sparql, "Toutes les interactions médicamenteuses", \
                "L'IA liste les individus de mdc:InteractionMedicamenteuse, triés du risque le plus élevé au plus faible."

        # ==============================================================
        # 2. CONTRE-INDICATIONS
        # ==============================================================
        if _has(q, "contre indi", "contreindi", "eviter", "deconseill", "peut il prendre",
                "peut elle prendre", "puis je prendre", "enceinte", "dangereux pour", "interdit"):
            if _has(q, "sans contre", "aucune contre", "pas de contre"):
                sparql = P + """SELECT ?medicament WHERE {
    ?m mdc:nomCommercial ?medicament .
    FILTER NOT EXISTS { ?m mdc:estContreIndiqueEn ?c }
    FILTER NOT EXISTS { ?m mdc:estContreIndiquePour ?mal }
}"""
                return sparql, "Médicaments sans contre-indication enregistrée", \
                    "L'IA utilise FILTER NOT EXISTS sur mdc:estContreIndiqueEn et mdc:estContreIndiquePour."
            if med:
                sparql = P + f"""SELECT ?contreIndication ?type WHERE {{
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
}}"""
                return sparql, f"Contre-indications de {med}", \
                    f"L'IA réunit (UNION) les conditions cliniques et les maladies du module Maladie contre-indiquées pour mdc:{med}."
            if maladie:
                sparql = P + f"""SELECT ?medicament (GROUP_CONCAT(DISTINCT ?cl; separator=", ") AS ?classe) WHERE {{
    ?m mdc:estContreIndiquePour mal:{maladie} ;
       mdc:nomCommercial ?medicament ;
       rdf:type ?c .
    FILTER(?c IN ({CLASSES_IN}))
    BIND(STRAFTER(STR(?c), "#") AS ?cl)
}} GROUP BY ?medicament"""
                return sparql, f"Médicaments contre-indiqués : {maladie}", \
                    f"Requête croisée Médicament ↔ Maladie : ?m mdc:estContreIndiquePour mal:{maladie}."
            if condition:
                sparql = P + f"""SELECT ?medicament ?condition WHERE {{
    ?m mdc:estContreIndiqueEn mdc:{condition} ;
       mdc:nomCommercial ?medicament .
    mdc:{condition} mdc:nomCondition ?condition .
}}"""
                return sparql, f"Médicaments contre-indiqués : {condition.replace('_', ' ')}", \
                    f"L'IA sélectionne les médicaments liés à mdc:{condition} par mdc:estContreIndiqueEn."
            sparql = P + """SELECT ?medicament ?contreIndication ?type WHERE {
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
} ORDER BY ?medicament"""
            return sparql, "Toutes les contre-indications", \
                "L'IA liste chaque médicament avec ses contre-indications (conditions cliniques et maladies)."

        # ==============================================================
        # 3. EFFETS SECONDAIRES
        # ==============================================================
        if _has(q, "a risque", "dangereux", "risque grave"):
            sparql = P + """SELECT ?medicament ?effetGrave WHERE {
    ?m rdf:type mdc:MedicamentARisque ;
       mdc:nomCommercial ?medicament ;
       mdc:peutProvoquer ?e .
    ?e mdc:graviteEffet 3 ; mdc:nomEffet ?effetGrave .
} ORDER BY ?medicament"""
            return sparql, "Médicaments à risque (classe inférée)", \
                "mdc:MedicamentARisque est une classe définie (Medicament ⊓ ∃peutProvoquer.EffetGrave) remplie par le raisonneur HermiT."

        if _has(q, "effet", "indesirable", "secondaire", "provoqu", "cause"):
            precis = self._first(q, EFFET_PRECIS_KW)
            famille = self._first(q, EFFETS_KW)
            if _has(q, "grave", "severe", "serieux"):
                sparql = P + """SELECT ?effet ?frequence ?medicament WHERE {
    ?e rdf:type mdc:EffetGrave ;
       mdc:nomEffet ?effet ;
       mdc:frequence ?frequence .
    ?m mdc:peutProvoquer ?e ; mdc:nomCommercial ?medicament .
} ORDER BY ?effet"""
                return sparql, "Effets secondaires graves", \
                    "mdc:EffetGrave est une classe définie (EffetSecondaire ⊓ graviteEffet = 3) inférée par HermiT."
            if med:
                sparql = P + f"""SELECT ?effet ?famille ?frequence ?gravite WHERE {{
    mdc:{med} mdc:peutProvoquer ?e .
    ?e mdc:nomEffet ?effet ; rdf:type ?t .
    ?t rdfs:subClassOf mdc:EffetSecondaire .
    FILTER(?t != mdc:EffetGrave)
    OPTIONAL {{ ?e mdc:frequence ?frequence }}
    OPTIONAL {{ ?e mdc:graviteEffet ?gravite }}
    BIND(STRAFTER(STR(?t), "#") AS ?famille)
}} ORDER BY DESC(?gravite)"""
                return sparql, f"Effets secondaires de {med}", \
                    f"L'IA suit la relation mdc:peutProvoquer depuis mdc:{med} et trie par gravité."
            if precis:
                values = " ".join(f"mdc:{e}" for e in precis)
                sparql = P + f"""SELECT ?medicament ?effet ?frequence WHERE {{
    VALUES ?e {{ {values} }}
    ?m mdc:peutProvoquer ?e ; mdc:nomCommercial ?medicament .
    ?e mdc:nomEffet ?effet .
    OPTIONAL {{ ?e mdc:frequence ?frequence }}
}} ORDER BY ?medicament"""
                return sparql, "Médicaments provoquant cet effet", \
                    f"L'IA cherche les médicaments liés à {values} par mdc:peutProvoquer."
            if famille:
                cls, label = famille
                sparql = P + f"""SELECT ?effet ?medicament ?frequence ?gravite WHERE {{
    ?e rdf:type mdc:{cls} ; mdc:nomEffet ?effet .
    ?m mdc:peutProvoquer ?e ; mdc:nomCommercial ?medicament .
    OPTIONAL {{ ?e mdc:frequence ?frequence }}
    OPTIONAL {{ ?e mdc:graviteEffet ?gravite }}
}} ORDER BY ?effet"""
                return sparql, f"Effets secondaires {label}", \
                    f"L'IA sélectionne les instances de la sous-classe mdc:{cls}."
            sparql = P + """SELECT ?medicament ?effet ?frequence ?gravite WHERE {
    ?m mdc:peutProvoquer ?e ; mdc:nomCommercial ?medicament .
    ?e mdc:nomEffet ?effet .
    OPTIONAL { ?e mdc:frequence ?frequence }
    OPTIONAL { ?e mdc:graviteEffet ?gravite }
} ORDER BY ?medicament DESC(?gravite)"""
            return sparql, "Effets secondaires de tous les médicaments", \
                "L'IA parcourt toutes les relations mdc:peutProvoquer."

        # ==============================================================
        # 4. DONNÉES CLINIQUES (ESSAIS)
        # ==============================================================
        if _has(q, "essai", "clinique", "efficac", "etude", "phase"):
            if _has(q, "sans essai", "pas d essai", "non evalue", "aucun essai"):
                sparql = P + """SELECT ?medicament WHERE {
    ?m mdc:nomCommercial ?medicament .
    FILTER NOT EXISTS { ?m rdf:type mdc:MedicamentEvalueCliniquement }
}"""
                return sparql, "Médicaments sans essai clinique", \
                    "L'IA exclut les individus de la classe inférée mdc:MedicamentEvalueCliniquement."
            if _has(q, "plus efficace", "meilleur", "le mieux"):
                sparql = P + """SELECT ?medicament ?tauxEfficacite ?nombrePatients ?objectif WHERE {
    ?essai mdc:evalue ?m ; mdc:tauxEfficacite ?tauxEfficacite .
    ?m mdc:nomCommercial ?medicament .
    OPTIONAL { ?essai mdc:nombrePatients ?nombrePatients }
    OPTIONAL { ?essai mdc:objectifEssai ?objectif }
} ORDER BY DESC(?tauxEfficacite) LIMIT 3"""
                return sparql, "Médicaments les plus efficaces (essais cliniques)", \
                    "L'IA trie les essais par mdc:tauxEfficacite décroissant (ORDER BY DESC, LIMIT 3)."
            filtre = f"FILTER(?m = mdc:{med})" if med else ""
            sparql = P + f"""SELECT ?essai ?medicament ?phase ?nombrePatients ?tauxEfficacite ?annee ?objectif WHERE {{
    ?e mdc:evalue ?m ; mdc:phase ?phase ; mdc:nombrePatients ?nombrePatients ;
       mdc:tauxEfficacite ?tauxEfficacite ; mdc:anneeEssai ?annee .
    {filtre}
    ?m mdc:nomCommercial ?medicament .
    OPTIONAL {{ ?e mdc:objectifEssai ?objectif }}
    BIND(STRAFTER(STR(?e), "#") AS ?essai)
}} ORDER BY DESC(?tauxEfficacite)"""
            return sparql, f"Essais cliniques{' de ' + med if med else ''}", \
                "L'IA lit les données cliniques (phase, patients, efficacité, année) via mdc:evalue."

        # ==============================================================
        # 5. MOLÉCULES / PRINCIPES ACTIFS
        # ==============================================================
        if _has(q, "molecule", "principe actif", "substance", "formule", "masse molaire", "contien", "compos"):
            mol = self._molecule_in(q)
            if mol and not any(_norm(n) in q for n in self.med_index):
                sparql = P + f"""SELECT ?medicament ?dosage ?forme WHERE {{
    ?m mdc:contientMolecule mdc:{mol} ;
       mdc:nomCommercial ?medicament .
    OPTIONAL {{ ?m mdc:dosage ?dosage }}
    OPTIONAL {{ ?m mdc:formeGalenique ?forme }}
}}"""
                return sparql, f"Médicaments contenant {mol.replace('Mol_', '').replace('_', ' ')}", \
                    f"L'IA utilise la relation inverse : ?m mdc:contientMolecule mdc:{mol}."
            filtre = f"FILTER(?m = mdc:{med})" if med else ""
            sparql = P + f"""SELECT ?medicament ?molecule ?formuleBrute ?masseMolaire WHERE {{
    ?m mdc:contientMolecule ?mol ; mdc:nomCommercial ?medicament .
    {filtre}
    ?mol mdc:nomMolecule ?molecule .
    OPTIONAL {{ ?mol mdc:formuleBrute ?formuleBrute }}
    OPTIONAL {{ ?mol mdc:masseMolaire ?masseMolaire }}
}} ORDER BY ?medicament"""
            return sparql, f"Molécule(s){' de ' + med if med else ' des médicaments'}", \
                "L'IA suit mdc:contientMolecule puis lit la formule brute et la masse molaire."

        # ==============================================================
        # 6. TRAITEMENTS (lien avec le module Maladie)
        # ==============================================================
        if maladie and not med:
            sparql = P + f"""SELECT ?medicament (GROUP_CONCAT(DISTINCT ?cl; separator=", ") AS ?classe) ?posologie WHERE {{
    ?m mdc:traite mal:{maladie} ;
       mdc:nomCommercial ?medicament ;
       rdf:type ?c .
    FILTER(?c IN ({CLASSES_IN}))
    OPTIONAL {{ ?m mdc:posologie ?posologie }}
    BIND(STRAFTER(STR(?c), "#") AS ?cl)
}} GROUP BY ?medicament ?posologie"""
            return sparql, f"Médicaments qui traitent : {maladie.replace('_', ' ')}", \
                f"Requête croisée Médicament ↔ Maladie : ?m mdc:traite mal:{maladie}."
        if med and _has(q, "traite", "soigne", "sert", "indication", "pour quoi", "pourquoi", "utilise"):
            sparql = P + f"""SELECT ?maladie ?codeCIM WHERE {{
    mdc:{med} mdc:traite ?mal .
    OPTIONAL {{ ?mal mal:nom ?nom }}
    OPTIONAL {{ ?mal mal:codeCIM ?codeCIM }}
    BIND(COALESCE(?nom, STRAFTER(STR(?mal), "#")) AS ?maladie)
}}"""
            return sparql, f"Maladies traitées par {med}", \
                f"L'IA suit mdc:traite depuis mdc:{med} vers les individus du module Maladie (nom, code CIM-10)."

        # ==============================================================
        # 7. ORDONNANCE / PRIX / POSOLOGIE
        # ==============================================================
        if _has(q, "ordonnance", "prescription", "libre", "sans prescri"):
            if _has(q, "sans", "libre", "pas besoin"):
                sparql = P + """SELECT ?medicament ?prixTND WHERE {
    ?m mdc:nomCommercial ?medicament ; mdc:necessiteOrdonnance false .
    OPTIONAL { ?m mdc:prixTND ?prixTND }
} ORDER BY ?medicament"""
                return sparql, "Médicaments sans ordonnance", \
                    "L'IA filtre sur mdc:necessiteOrdonnance false."
            sparql = P + """SELECT ?medicament ?prixTND WHERE {
    ?m rdf:type mdc:MedicamentSurOrdonnance ; mdc:nomCommercial ?medicament .
    OPTIONAL { ?m mdc:prixTND ?prixTND }
} ORDER BY ?medicament"""
            return sparql, "Médicaments sur ordonnance (classe inférée)", \
                "mdc:MedicamentSurOrdonnance est une classe définie (necessiteOrdonnance = true) remplie par le raisonneur."

        if _has(q, "prix", "cout", "coute", "couts", "cher", "chers", "chere", "tarif", "dinar", "tnd"):
            if med:
                sparql = P + f"""SELECT ?medicament ?prixTND ?dosage WHERE {{
    mdc:{med} mdc:nomCommercial ?medicament ; mdc:prixTND ?prixTND .
    OPTIONAL {{ mdc:{med} mdc:dosage ?dosage }}
}}"""
                return sparql, f"Prix de {med}", f"L'IA lit mdc:prixTND de mdc:{med}."
            ordre = "DESC" if _has(q, "plus cher", "cher", "chers", "chere") and not _has(q, "moins cher", "pas cher") else "ASC"
            sparql = P + f"""SELECT ?medicament ?prixTND ?dosage WHERE {{
    ?m mdc:nomCommercial ?medicament ; mdc:prixTND ?prixTND .
    OPTIONAL {{ ?m mdc:dosage ?dosage }}
}} ORDER BY {ordre}(?prixTND)"""
            return sparql, "Médicaments triés par prix", \
                f"L'IA trie les médicaments par mdc:prixTND ({'décroissant' if ordre == 'DESC' else 'croissant'})."

        if _has(q, "posologie", "dose", "dosage", "combien de fois", "comment prendre"):
            filtre = f"FILTER(?m = mdc:{med})" if med else ""
            sparql = P + f"""SELECT ?medicament ?dosage ?forme ?posologie WHERE {{
    ?m mdc:nomCommercial ?medicament .
    {filtre}
    OPTIONAL {{ ?m mdc:dosage ?dosage }}
    OPTIONAL {{ ?m mdc:formeGalenique ?forme }}
    OPTIONAL {{ ?m mdc:posologie ?posologie }}
}} ORDER BY ?medicament"""
            return sparql, f"Posologie{' de ' + med if med else ' des médicaments'}", \
                "L'IA lit mdc:dosage, mdc:formeGalenique et mdc:posologie."

        # ==============================================================
        # 8. CLASSES THÉRAPEUTIQUES
        # ==============================================================
        if classe:
            cls, label = classe
            sparql = P + f"""SELECT ?medicament ?molecule ?dosage ?codeATC WHERE {{
    ?m rdf:type/rdfs:subClassOf* mdc:{cls} ;
       mdc:nomCommercial ?medicament .
    OPTIONAL {{ ?m mdc:contientMolecule/mdc:nomMolecule ?molecule }}
    OPTIONAL {{ ?m mdc:dosage ?dosage }}
    OPTIONAL {{ ?m mdc:codeATC ?codeATC }}
}} ORDER BY ?medicament"""
            return sparql, f"Liste des {label}", \
                f"L'IA sélectionne les instances de mdc:{cls} (rdf:type/rdfs:subClassOf*)."

        if _has(q, "combien", "nombre"):
            sparql = P + """SELECT ?classe (COUNT(?m) AS ?nombre) WHERE {
    ?m mdc:nomCommercial ?n ; rdf:type ?c .
    ?c rdfs:subClassOf mdc:Medicament .
    FILTER(?c IN (""" + CLASSES_IN + """))
    BIND(STRAFTER(STR(?c), "#") AS ?classe)
} GROUP BY ?classe ORDER BY DESC(?nombre)"""
            return sparql, "Nombre de médicaments par classe thérapeutique", \
                "L'IA regroupe (GROUP BY) les médicaments par classe et les compte (COUNT)."

        if _has(q, "code atc", "atc"):
            sparql = P + """SELECT ?medicament ?codeATC WHERE {
    ?m mdc:nomCommercial ?medicament ; mdc:codeATC ?codeATC .
} ORDER BY ?codeATC"""
            return sparql, "Codes ATC des médicaments", \
                "L'IA lit mdc:codeATC (classification anatomique, thérapeutique et chimique de l'OMS)."

        # ==============================================================
        # 9. FICHE D'UN MÉDICAMENT
        # ==============================================================
        if med:
            sparql = P + f"""SELECT ?propriete ?valeur WHERE {{
    mdc:{med} ?p ?v .
    FILTER(isLiteral(?v))
    BIND(STRAFTER(STR(?p), "#") AS ?propriete)
    BIND(STR(?v) AS ?valeur)
}}"""
            return sparql, f"Fiche du médicament {med}", \
                f"L'IA récupère toutes les propriétés de données (littéraux) de mdc:{med}."

        # ==============================================================
        # 10. PAR DÉFAUT : TOUS LES MÉDICAMENTS
        # ==============================================================
        sparql = P + """SELECT ?medicament ?molecule ?dosage ?prixTND ?ordonnance WHERE {
    ?m mdc:nomCommercial ?medicament .
    OPTIONAL { ?m mdc:contientMolecule/mdc:nomMolecule ?molecule }
    OPTIONAL { ?m mdc:dosage ?dosage }
    OPTIONAL { ?m mdc:prixTND ?prixTND }
    OPTIONAL { ?m mdc:necessiteOrdonnance ?ordonnance }
} ORDER BY ?medicament"""
        return sparql, "Tous les médicaments de l'ontologie", \
            "L'IA liste l'ensemble des médicaments avec leur molécule, dosage, prix et statut d'ordonnance."
