# -*- coding: utf-8 -*-
"""
Service Back-end : Python + RDFLib
Gère le chargement de l'ontologie OWL (Classe Personne) et l'exécution des requêtes SPARQL.
"""

import os
from typing import Dict, Any, List

# Fix compatibilité universel Python 3.14 + pyparsing 3.3.x AVANT rdflib
try:
    import pyparsing_patch
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import pyparsing_patch

import rdflib
from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef, Literal

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OWL_PATH = os.path.join(BASE_DIR, "ontologie_personne.owl")

TTL_PATH = os.path.join(BASE_DIR, "ontologie_medicale (1).ttl")
ONTO_NS = Namespace("http://example.org/ontologie-medicale#")

class RDFLibService:
    def __init__(self, owl_path: str = OWL_PATH):
        self.owl_path = owl_path
        self.graph = Graph()
        self.load_ontology()

    def load_ontology(self):
        """Charge l'ontologie principale (TTL Protégé + Personne OWL) dans le graphe RDFLib."""
        self.graph = Graph()
        loaded_count = 0
        
        # 1. Charger l'ontologie médicale principale TTL de Protégé en priorité
        if os.path.exists(TTL_PATH):
            try:
                self.graph.parse(TTL_PATH, format="turtle")
                loaded_count += 1
                print(f"[RDFLib] Ontologie Protégé 'ontologie_medicale (1).ttl' chargée ({len(self.graph)} triplets).")
            except Exception as e:
                print(f"[RDFLib] Erreur parsing TTL {TTL_PATH} : {e}")

        # 2. Compléter avec ontologie_personne.owl si présent
        if os.path.exists(self.owl_path):
            try:
                self.graph.parse(self.owl_path, format="xml")
                loaded_count += 1
                print(f"[RDFLib] Ontologie Personne OWL chargée (total : {len(self.graph)} triplets).")
            except Exception as e:
                print(f"[RDFLib] Erreur parsing OWL {self.owl_path} : {e}")

        if loaded_count == 0:
            raise FileNotFoundError(f"Aucune ontologie trouvée ({TTL_PATH} ou {self.owl_path})")

        self.graph.bind("med", ONTO_NS)
        self.graph.bind("", ONTO_NS)
        self.graph.bind("owl", OWL)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("rdf", RDF)
        print(f"[RDFLib] Graph prêt avec {len(self.graph)} triplets.")

    def execute_sparql(self, query_str: str) -> Dict[str, Any]:
        """
        Exécute une requête SPARQL sur le graphe RDFLib
        et retourne le résultat au format standard SPARQL JSON (compatible Apache Jena Fuseki).
        """
        import re

        prefixes = """
PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""
        q = query_str.strip()
        # Supprimer le prefixe vide PREFIX : <...> s'il existe pour éviter le bug rdflib None prefix
        q = re.sub(r'PREFIX\s+:\s+<[^>]+>', '', q, flags=re.IGNORECASE)
        # Remplacer les :Concept isolés par med:Concept
        q = re.sub(r'(?<![A-Za-z0-9_:]):([A-Za-z0-9_]+)', r'med:\1', q)

        if "PREFIX med:" not in q:
            q = prefixes + q

        res = self.graph.query(q)

        # Construction du format Fuseki SPARQL JSON
        vars_list = [str(v) for v in res.vars] if res.vars else []
        bindings = []

        for row in res:
            binding = {}
            for i, var in enumerate(vars_list):
                val = row[i]
                if val is not None:
                    if isinstance(val, URIRef):
                        binding[var] = {
                            "type": "uri",
                            "value": str(val)
                        }
                    elif isinstance(val, Literal):
                        entry = {
                            "type": "literal",
                            "value": str(val)
                        }
                        if val.datatype:
                            entry["datatype"] = str(val.datatype)
                        if val.language:
                            entry["xml:lang"] = str(val.language)
                        binding[var] = entry
                    else:
                        binding[var] = {
                            "type": "literal",
                            "value": str(val)
                        }
            # Déduplication systématique des lignes pour éviter toute répétition
            if binding not in bindings:
                bindings.append(binding)

        return {
            "head": {"vars": vars_list},
            "results": {"bindings": bindings}
        }

    def get_summary(self) -> Dict[str, Any]:
        """Retourne les métadonnées et statistiques de la classe Personne."""
        query_classes = """
        PREFIX : <http://example.org/ontologie-medicale#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?cls (SAMPLE(?lbl) AS ?label) WHERE {
            ?cls rdfs:subClassOf* :Personne .
            OPTIONAL { ?cls rdfs:label ?lbl }
        } GROUP BY ?cls
        """
        classes = self.execute_sparql(query_classes)["results"]["bindings"]

        query_individuals = """
        PREFIX : <http://example.org/ontologie-medicale#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?ind ?type ?nom ?age ?cin ?dossier WHERE {
            ?ind rdf:type ?type .
            ?type rdfs:subClassOf* :Personne .
            OPTIONAL { ?ind :nom ?nom }
            OPTIONAL { ?ind :age ?age }
            OPTIONAL { ?ind :numeroCIN ?cin }
            OPTIONAL { ?ind :numeroDossier ?dossier }
        }
        """
        individuals = self.execute_sparql(query_individuals)["results"]["bindings"]

        return {
            "triples_count": len(self.graph),
            "classes_personne_count": len(classes),
            "individuals_count": len(individuals),
            "file": os.path.basename(self.owl_path)
        }

    def get_all_personnes(self) -> List[Dict[str, Any]]:
        """Extrait tous les détails sur les individus de la classe Personne."""
        q = """
        PREFIX : <http://example.org/ontologie-medicale#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?p ?type ?nom ?prenom ?age ?cin ?telephone ?adresse ?dossier ?groupeSanguin ?specialite ?service WHERE {
            ?p rdf:type ?type .
            ?type rdfs:subClassOf* :Personne .
            OPTIONAL { ?p :nom ?nom }
            OPTIONAL { ?p :prenom ?prenom }
            OPTIONAL { ?p :age ?age }
            OPTIONAL { ?p :numeroCIN ?cin }
            OPTIONAL { ?p :telephone ?telephone }
            OPTIONAL { ?p :adresse ?adresse }
            OPTIONAL { ?p :numeroDossier ?dossier }
            OPTIONAL { ?p :groupeSanguin ?groupeSanguin }
            OPTIONAL { ?p :specialite ?specialite }
            OPTIONAL { ?p :appartientA ?service }
            OPTIONAL { ?p :appartient_à ?service }
        }
        """
        rows = self.execute_sparql(q)["results"]["bindings"]
        personnes_dict = {}
        for r in rows:
            uri = r["p"]["value"]
            if uri not in personnes_dict:
                personnes_dict[uri] = {
                    "uri": uri,
                    "id": uri.split("#")[-1],
                    "types": [],
                    "nom": r.get("nom", {}).get("value", ""),
                    "prenom": r.get("prenom", {}).get("value", ""),
                    "age": r.get("age", {}).get("value", ""),
                    "cin": r.get("cin", {}).get("value", ""),
                    "telephone": r.get("telephone", {}).get("value", ""),
                    "adresse": r.get("adresse", {}).get("value", ""),
                    "numeroDossier": r.get("dossier", {}).get("value", ""),
                    "groupeSanguin": r.get("groupeSanguin", {}).get("value", ""),
                    "specialite": r.get("specialite", {}).get("value", ""),
                    "service": r.get("service", {}).get("value", "").split("#")[-1] if r.get("service") else ""
                }
            type_val = r["type"]["value"].split("#")[-1]
            if type_val not in personnes_dict[uri]["types"] and type_val != "NamedIndividual":
                personnes_dict[uri]["types"].append(type_val)

        return list(personnes_dict.values())

    def get_relations_graph(self) -> Dict[str, Any]:
        """Retourne les nœuds et liens pour la visualisation en graphe interactif."""
        q = """
        PREFIX : <http://example.org/ontologie-medicale#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?s ?p ?o WHERE {
            ?s ?p ?o .
            FILTER(
                ?p IN (:soigne, :estSoignePar, :connait, :presente, :realise, :diagnostique, :appartientA, :appartient_à, :estPrisEnChargePar, :joueLeRoleDe)
            )
        }
        """
        bindings = self.execute_sparql(q)["results"]["bindings"]
        nodes_dict = {}
        edges = []

        for b in bindings:
            s = b["s"]["value"].split("#")[-1]
            p = b["p"]["value"].split("#")[-1]
            o = b["o"]["value"].split("#")[-1]

            if s not in nodes_dict:
                nodes_dict[s] = {"id": s, "label": s}
            if o not in nodes_dict:
                nodes_dict[o] = {"id": o, "label": o}

            edges.append({
                "from": s,
                "to": o,
                "label": p
            })

        return {
            "nodes": list(nodes_dict.values()),
            "edges": edges
        }


# ======================================================================
MALADIE_OWL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ontologie_maladie.owl")

class MaladieService:
    """Service RDFLib pour le module Maladie basé sur ontologie_medicale (1).ttl."""

    def __init__(self):
        self.graph = Graph()
        self.loaded = False
        self._load()

    def _load(self):
        # 1. Charger ontologie_medicale (1).ttl en priorité absolue
        if os.path.exists(TTL_PATH):
            try:
                self.graph.parse(TTL_PATH, format="turtle")
                self.loaded = True
                print(f"[MaladieService] 'ontologie_medicale (1).ttl' chargée ({len(self.graph)} triplets).")
            except Exception as e:
                print(f"[MaladieService] Erreur chargement TTL : {e}")

        # 2. Compléter avec ontologie_maladie.owl si présent
        if os.path.exists(MALADIE_OWL_PATH):
            try:
                self.graph.parse(MALADIE_OWL_PATH, format="xml")
                self.loaded = True
            except Exception:
                pass

        # 3. Ontologie personne pour questions croisées (Sami, Dr Fatima)
        pers_path = os.path.join(BASE_DIR, "ontologie_personne.owl")
        if os.path.exists(pers_path):
            try:
                self.graph.parse(pers_path, format="xml")
            except Exception:
                pass

        self.graph.bind("med", ONTO_NS)
        self.graph.bind("mal", Namespace("http://example.org/ontologie-maladie#"))
        self.graph.bind("", ONTO_NS)
        self.graph.bind("owl", OWL)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("rdf", RDF)
        print(f"[MaladieService] Prêt avec {len(self.graph)} triplets au total.")

    NS = "http://example.org/ontologie-medicale#"

    def execute_sparql(self, query_str: str) -> Dict[str, Any]:
        """Exécute une requête SPARQL sur le graphe Maladie."""
        import re
        prefixes = f"""PREFIX : <http://example.org/ontologie-medicale#>
PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX mal: <http://example.org/ontologie-maladie#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""
        q = query_str.strip()
        q = re.sub(r'PREFIX\s+:\s+<[^>]+>', '', q, flags=re.IGNORECASE)
        # Harmoniser les préfixes : et mal: vers med: si besoin
        q = re.sub(r'(?<![A-Za-z0-9_:]):([A-Za-z0-9_]+)', r'med:\1', q)
        if "PREFIX med:" not in q:
            q = prefixes + q

        res = self.graph.query(q)
        vars_list = [str(v) for v in res.vars] if res.vars else []
        bindings = []
        for row in res:
            binding = {}
            for i, var in enumerate(vars_list):
                val = row[i]
                if val is not None:
                    if isinstance(val, URIRef):
                        binding[var] = {"type": "uri", "value": str(val)}
                    elif isinstance(val, Literal):
                        entry = {"type": "literal", "value": str(val)}
                        if val.datatype: entry["datatype"] = str(val.datatype)
                        binding[var] = entry
                    else:
                        binding[var] = {"type": "literal", "value": str(val)}
            bindings.append(binding)
        return {"head": {"vars": vars_list}, "results": {"bindings": bindings}}

    def get_all_maladies(self) -> List[Dict[str, Any]]:
        """Retourne tous les individus Maladie depuis ontologie_medicale (1).ttl."""
        q = """
        SELECT DISTINCT ?m ?type ?label ?desc ?gravite ?contagieuse WHERE {
            ?m rdf:type owl:NamedIndividual .
            ?m rdf:type ?type .
            ?type rdfs:subClassOf* med:Maladie .
            FILTER(?type NOT IN (med:Maladie, med:Symptome, med:SymptomeGeneral, med:SymptomeDigestif, med:SymptomeRespiratoire, med:Type))
            OPTIONAL { ?m rdfs:label ?label }
            OPTIONAL { ?m med:description ?desc }
            OPTIONAL { ?m med:gravite ?gravite }
            OPTIONAL { ?m med:estContagieuse ?contagieuse }
        }
        """
        rows = self.execute_sparql(q)["results"]["bindings"]
        maladies_dict = {}
        for r in rows:
            uri = r["m"]["value"]
            ind_id = uri.split("#")[-1]
            if uri not in maladies_dict:
                lbl = r.get("label", {}).get("value", "")
                raw_grav = r.get("gravite", {}).get("value", "")
                # Mapper la gravité textuelle / numérique
                grav_norm = "1"
                if "mod" in raw_grav.lower() or raw_grav == "2":
                    grav_norm = "2"
                elif "grav" in raw_grav.lower() or raw_grav == "3" or "sev" in raw_grav.lower():
                    grav_norm = "3"

                is_chronique = "true" if "Chronique" in r["type"]["value"] else "false"

                maladies_dict[uri] = {
                    "id": ind_id,
                    "types": [],
                    "nom": lbl or ind_id.replace("_", " "),
                    "description": r.get("desc", {}).get("value", ""),
                    "codeCIM": "",
                    "gravite": grav_norm,
                    "contagieuse": r.get("contagieuse", {}).get("value", "false"),
                    "chronique": is_chronique,
                    "duree": "",
                    "symptomes": [],
                    "medicaments": []
                }
            type_val = r["type"]["value"].split("#")[-1]
            if type_val not in maladies_dict[uri]["types"] and type_val not in ["NamedIndividual", "Thing"]:
                maladies_dict[uri]["types"].append(type_val)

        # Charger les symptômes liés via aPourSymptome
        q2 = """
        SELECT DISTINCT ?m ?s ?sNom WHERE {
            ?m med:aPourSymptome ?s .
            OPTIONAL { ?s rdfs:label ?sNom }
        }
        """
        for r in self.execute_sparql(q2)["results"]["bindings"]:
            uri = r["m"]["value"]
            if uri in maladies_dict:
                snom = r.get("sNom", {}).get("value") or r.get("s", {}).get("value", "").split("#")[-1]
                if snom and snom not in maladies_dict[uri]["symptomes"]:
                    maladies_dict[uri]["symptomes"].append(snom)

        # Charger les symptômes via inverse estSymptomeDe
        q2_inv = """
        SELECT DISTINCT ?s ?m WHERE {
            ?s med:estSymptomeDe ?m .
        }
        """
        for r in self.execute_sparql(q2_inv)["results"]["bindings"]:
            uri = r["m"]["value"]
            if uri in maladies_dict:
                snom = r.get("s", {}).get("value", "").split("#")[-1]
                if snom and snom not in maladies_dict[uri]["symptomes"]:
                    maladies_dict[uri]["symptomes"].append(snom)

        # Charger les médicaments liés via estTraiteePar
        q3 = """
        SELECT DISTINCT ?m ?med WHERE {
            ?m med:estTraiteePar ?med .
        }
        """
        for r in self.execute_sparql(q3)["results"]["bindings"]:
            uri = r["m"]["value"]
            if uri in maladies_dict:
                mid = r.get("med", {}).get("value", "").split("#")[-1]
                if mid and mid not in maladies_dict[uri]["medicaments"]:
                    maladies_dict[uri]["medicaments"].append(mid)

        # Charger médicaments via inverse traite
        q3_inv = """
        SELECT DISTINCT ?med ?m WHERE {
            ?med med:traite ?m .
        }
        """
        for r in self.execute_sparql(q3_inv)["results"]["bindings"]:
            uri = r["m"]["value"]
            if uri in maladies_dict:
                mid = r.get("med", {}).get("value", "").split("#")[-1]
                if mid and mid not in maladies_dict[uri]["medicaments"]:
                    maladies_dict[uri]["medicaments"].append(mid)

        result = list(maladies_dict.values())
        return result

    def get_graph_maladie(self) -> Dict[str, Any]:
        """Retourne les nœuds et liens du graphe Maladie depuis ontologie_medicale (1).ttl."""
        q = """
        SELECT DISTINCT ?s ?p ?o WHERE {
            ?s ?p ?o .
            FILTER(?p IN (med:aPourSymptome, med:estTraiteePar, med:souffreDe, med:touche,
                          med:estSymptomeDe, med:estContreIndiquePour, med:diagnostique,
                          med:necessite, med:necessiteSuiviPar, med:estPrescritePour))
        }
        """
        bindings = self.execute_sparql(q)["results"]["bindings"]
        nodes_dict = {}
        edges = []
        for b in bindings:
            s = b["s"]["value"].split("#")[-1]
            p = b["p"]["value"].split("#")[-1]
            o = b["o"]["value"].split("#")[-1]
            if s not in nodes_dict: nodes_dict[s] = {"id": s, "label": s}
            if o not in nodes_dict: nodes_dict[o] = {"id": o, "label": o}
            edges.append({"from": s, "to": o, "label": p})
        return {"nodes": list(nodes_dict.values()), "edges": edges}
