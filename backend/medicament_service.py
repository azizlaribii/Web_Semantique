# -*- coding: utf-8 -*-
"""
Service Back-end : Module Médicament (Python + RDFLib)
Charge ontologie_medicament.owl (+ ontologie_maladie.owl pour les liens croisés)
et expose les données des médicaments, molécules, effets secondaires,
contre-indications, interactions et essais cliniques.
"""

import os
from typing import Dict, Any, List

try:
    import pyparsing_patch  # noqa: F401  (compatibilité Python 3.14 + pyparsing)
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import pyparsing_patch  # noqa: F401

from rdflib import Graph, Namespace, URIRef, Literal

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDICAMENT_OWL_PATH = os.path.join(BASE_DIR, "ontologie_medicament.owl")
MALADIE_OWL_PATH = os.path.join(BASE_DIR, "ontologie_maladie.owl")

MDC_NS = "http://example.org/ontologie-medicament#"
MAL_NS = "http://example.org/ontologie-maladie#"

PREFIXES_MDC = f"""PREFIX mdc: <{MDC_NS}>
PREFIX mal: <{MAL_NS}>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""

# Classes thérapeutiques affichées dans l'interface (ordre de priorité)
CLASSES_THERAPEUTIQUES = [
    "Antibiotique", "Antidiabetique", "Antihypertenseur", "AntiUlcereux",
    "Anticoagulant", "AntiInflammatoire", "Antalgique",
]
# Classes définies, inférées par le raisonneur HermiT
CLASSES_INFEREES = [
    "MedicamentARisque", "MedicamentSurOrdonnance", "MedicamentEvalueCliniquement",
]


def _local(uri: str) -> str:
    return uri.split("#")[-1]


class MedicamentService:
    """Service RDFLib pour le module Médicament."""

    NS = MDC_NS

    def __init__(self, owl_path: str = MEDICAMENT_OWL_PATH):
        self.owl_path = owl_path
        self.graph = Graph()
        self.loaded = False
        self._load()

    def _load(self):
        if not os.path.exists(self.owl_path):
            print("[MedicamentService] ontologie_medicament.owl introuvable — "
                  "lancez medicament_owlready2.py. Module désactivé.")
            return
        try:
            self.graph.parse(self.owl_path, format="xml")
            # Module Maladie chargé pour les questions croisées (noms des maladies traitées)
            if os.path.exists(MALADIE_OWL_PATH):
                try:
                    self.graph.parse(MALADIE_OWL_PATH, format="xml")
                except Exception as e:
                    print(f"[MedicamentService] Maladie non chargée : {e}")
            self.graph.bind("mdc", Namespace(MDC_NS))
            self.graph.bind("mal", Namespace(MAL_NS))
            self.loaded = True
            print(f"[MedicamentService] ontologies chargées ({len(self.graph)} triplets).")
        except Exception as e:
            print(f"[MedicamentService] Erreur chargement OWL : {e}")

    # ------------------------------------------------------------------
    # SPARQL
    # ------------------------------------------------------------------
    def execute_sparql(self, query_str: str) -> Dict[str, Any]:
        """Exécute une requête SPARQL et retourne le format JSON Fuseki standard."""
        import re
        q = query_str.strip()
        q = re.sub(r'PREFIX\s+:\s+<[^>]+>', '', q, flags=re.IGNORECASE)
        if "PREFIX mdc:" not in q:
            q = PREFIXES_MDC + q

        res = self.graph.query(q)
        if res.type == "ASK":
            return {"head": {}, "boolean": bool(res.askAnswer)}

        vars_list = [str(v) for v in res.vars] if res.vars else []
        bindings = []
        for row in res:
            binding = {}
            for i, var in enumerate(vars_list):
                val = row[i]
                if val is None:
                    continue
                if isinstance(val, URIRef):
                    binding[var] = {"type": "uri", "value": str(val)}
                elif isinstance(val, Literal):
                    entry = {"type": "literal", "value": str(val)}
                    if val.datatype:
                        entry["datatype"] = str(val.datatype)
                    binding[var] = entry
                else:
                    binding[var] = {"type": "literal", "value": str(val)}
            if binding not in bindings:
                bindings.append(binding)
        return {"head": {"vars": vars_list}, "results": {"bindings": bindings}}

    def _rows(self, query: str) -> List[Dict[str, str]]:
        """Raccourci : bindings sous forme {var: valeur}."""
        out = []
        for b in self.execute_sparql(query)["results"]["bindings"]:
            out.append({k: v["value"] for k, v in b.items()})
        return out

    # ------------------------------------------------------------------
    # Données métier
    # ------------------------------------------------------------------
    def get_all_medicaments(self) -> List[Dict[str, Any]]:
        """Retourne chaque médicament avec toutes ses relations."""
        if not self.loaded:
            return []

        meds: Dict[str, Dict[str, Any]] = {}
        for r in self._rows("""
        SELECT ?m ?nom ?dosage ?forme ?voie ?poso ?atc ?prix ?ordo WHERE {
            ?m rdf:type/rdfs:subClassOf* mdc:Medicament .
            OPTIONAL { ?m mdc:nomCommercial ?nom }
            OPTIONAL { ?m mdc:dosage ?dosage }
            OPTIONAL { ?m mdc:formeGalenique ?forme }
            OPTIONAL { ?m mdc:voieAdministration ?voie }
            OPTIONAL { ?m mdc:posologie ?poso }
            OPTIONAL { ?m mdc:codeATC ?atc }
            OPTIONAL { ?m mdc:prixTND ?prix }
            OPTIONAL { ?m mdc:necessiteOrdonnance ?ordo }
        }"""):
            uri = r["m"]
            if uri in meds:
                continue
            meds[uri] = {
                "id": _local(uri),
                "nom": r.get("nom", _local(uri)),
                "dosage": r.get("dosage", ""),
                "forme": r.get("forme", ""),
                "voie": r.get("voie", ""),
                "posologie": r.get("poso", ""),
                "codeATC": r.get("atc", ""),
                "prix": r.get("prix", ""),
                "ordonnance": r.get("ordo", "false") == "true",
                "classes": [],
                "inferences": [],
                "molecules": [],
                "effets": [],
                "contreIndications": [],
                "maladiesTraitees": [],
                "interactions": [],
                "essais": [],
            }

        # Types (classes thérapeutiques + classes inférées)
        for r in self._rows("SELECT ?m ?t WHERE { ?m mdc:nomCommercial ?n ; rdf:type ?t . }"):
            m = meds.get(r["m"])
            if not m:
                continue
            t = _local(r["t"])
            if t in CLASSES_THERAPEUTIQUES and t not in m["classes"]:
                m["classes"].append(t)
            elif t in CLASSES_INFEREES and t not in m["inferences"]:
                m["inferences"].append(t)
        for m in meds.values():
            m["classes"].sort(key=CLASSES_THERAPEUTIQUES.index)

        # Molécules
        for r in self._rows("""
        SELECT ?m ?nom ?formule ?masse WHERE {
            ?m mdc:contientMolecule ?mol .
            OPTIONAL { ?mol mdc:nomMolecule ?nom }
            OPTIONAL { ?mol mdc:formuleBrute ?formule }
            OPTIONAL { ?mol mdc:masseMolaire ?masse }
        }"""):
            if r["m"] in meds:
                meds[r["m"]]["molecules"].append({
                    "nom": r.get("nom", ""), "formule": r.get("formule", ""), "masse": r.get("masse", "")
                })

        # Effets secondaires
        for r in self._rows("""
        SELECT ?m ?nom ?freq ?grav ?type WHERE {
            ?m mdc:peutProvoquer ?e .
            ?e rdf:type ?type . ?type rdfs:subClassOf mdc:EffetSecondaire .
            FILTER(?type != mdc:EffetGrave)
            OPTIONAL { ?e mdc:nomEffet ?nom }
            OPTIONAL { ?e mdc:frequence ?freq }
            OPTIONAL { ?e mdc:graviteEffet ?grav }
        } ORDER BY DESC(?grav)"""):
            if r["m"] in meds:
                meds[r["m"]]["effets"].append({
                    "nom": r.get("nom", ""), "frequence": r.get("freq", ""),
                    "gravite": r.get("grav", "1"), "type": _local(r.get("type", ""))
                })

        # Contre-indications : conditions cliniques + maladies (module Maladie)
        for r in self._rows("""
        SELECT ?m ?label ?source WHERE {
            {
                ?m mdc:estContreIndiqueEn ?c .
                OPTIONAL { ?c mdc:nomCondition ?n }
                BIND(COALESCE(?n, STRAFTER(STR(?c), "#")) AS ?label)
                BIND("condition" AS ?source)
            } UNION {
                ?m mdc:estContreIndiquePour ?mal .
                OPTIONAL { ?mal mal:nom ?n2 }
                BIND(COALESCE(?n2, STRAFTER(STR(?mal), "#")) AS ?label)
                BIND("maladie" AS ?source)
            }
        }"""):
            if r["m"] in meds:
                meds[r["m"]]["contreIndications"].append({"label": r["label"], "source": r["source"]})

        # Maladies traitées
        for r in self._rows("""
        SELECT ?m ?label WHERE {
            ?m mdc:traite ?mal .
            OPTIONAL { ?mal mal:nom ?n }
            BIND(COALESCE(?n, STRAFTER(STR(?mal), "#")) AS ?label)
        }"""):
            if r["m"] in meds:
                meds[r["m"]]["maladiesTraitees"].append(r["label"])

        # Interactions (relation réifiée, dans les deux sens)
        for r in self._rows("""
        SELECT ?m ?autre ?risque ?desc WHERE {
            ?i mdc:impliqueMedicament ?m , ?autre .
            FILTER(?m != ?autre)
            OPTIONAL { ?i mdc:niveauRisque ?risque }
            OPTIONAL { ?i mdc:descriptionInteraction ?desc }
        }"""):
            if r["m"] in meds:
                meds[r["m"]]["interactions"].append({
                    "avec": _local(r["autre"]), "risque": r.get("risque", ""), "description": r.get("desc", "")
                })

        # Essais cliniques
        for r in self._rows("""
        SELECT ?m ?essai ?phase ?nb ?taux ?annee ?obj WHERE {
            ?essai mdc:evalue ?m .
            OPTIONAL { ?essai mdc:phase ?phase }
            OPTIONAL { ?essai mdc:nombrePatients ?nb }
            OPTIONAL { ?essai mdc:tauxEfficacite ?taux }
            OPTIONAL { ?essai mdc:anneeEssai ?annee }
            OPTIONAL { ?essai mdc:objectifEssai ?obj }
        }"""):
            if r["m"] in meds:
                meds[r["m"]]["essais"].append({
                    "id": _local(r["essai"]), "phase": r.get("phase", ""), "patients": r.get("nb", ""),
                    "efficacite": r.get("taux", ""), "annee": r.get("annee", ""), "objectif": r.get("obj", "")
                })

        return sorted(meds.values(), key=lambda m: m["nom"])

    def get_graph_medicament(self) -> Dict[str, Any]:
        """Nœuds et liens du graphe Médicament (avec un groupe par type de nœud)."""
        if not self.loaded:
            return {"nodes": [], "edges": []}

        rows = self._rows("""
        SELECT ?s ?p ?o WHERE {
            ?s ?p ?o .
            FILTER(?p IN (mdc:contientMolecule, mdc:peutProvoquer, mdc:traite,
                          mdc:estContreIndiquePour, mdc:estContreIndiqueEn, mdc:interagitAvec))
        }""")

        groups = {}
        for r in self._rows("""
        SELECT ?x ?g WHERE {
            {
                ?x rdf:type/rdfs:subClassOf* mdc:Medicament . BIND("medicament" AS ?g)
            } UNION {
                ?x rdf:type mdc:Molecule . BIND("molecule" AS ?g)
            } UNION {
                ?x rdf:type/rdfs:subClassOf* mdc:EffetSecondaire . BIND("effet" AS ?g)
            } UNION {
                ?x rdf:type mdc:ConditionClinique . BIND("condition" AS ?g)
            } UNION {
                ?x mal:nom ?n . BIND("maladie" AS ?g)
            }
        }"""):
            groups.setdefault(r["x"], r["g"])

        nodes, edges, seen_sym = {}, [], set()
        for r in rows:
            s, p, o = r["s"], _local(r["p"]), r["o"]
            if p == "interagitAvec":
                key = tuple(sorted((s, o)))
                if key in seen_sym:
                    continue
                seen_sym.add(key)
            for uri in (s, o):
                nid = _local(uri)
                if nid not in nodes:
                    nodes[nid] = {"id": nid, "label": nid.replace("_", " "),
                                  "group": groups.get(uri, "autre")}
            edges.append({"from": _local(s), "to": _local(o), "label": p})
        return {"nodes": list(nodes.values()), "edges": edges}

    def get_summary(self) -> Dict[str, Any]:
        if not self.loaded:
            return {"loaded": False}
        counts = self._rows("""
        SELECT
          (COUNT(DISTINCT ?m) AS ?medicaments)
          (COUNT(DISTINCT ?mol) AS ?molecules)
          (COUNT(DISTINCT ?e) AS ?effets)
          (COUNT(DISTINCT ?ess) AS ?essais)
        WHERE {
          { ?m mdc:nomCommercial ?x } UNION { ?mol mdc:nomMolecule ?y }
          UNION { ?e mdc:nomEffet ?z } UNION { ?ess mdc:evalue ?w }
        }""")[0]
        return {
            "loaded": True,
            "triples_count": len(self.graph),
            "file": os.path.basename(self.owl_path),
            **{k: int(v) for k, v in counts.items()},
        }
