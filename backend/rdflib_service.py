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

ONTO_NS = Namespace("http://example.org/ontologie-medicale#")

class RDFLibService:
    def __init__(self, owl_path: str = OWL_PATH):
        self.owl_path = owl_path
        self.graph = Graph()
        self.load_ontology()

    def load_ontology(self):
        """Charge l'ontologie OWL dans le graphe RDFLib."""
        if not os.path.exists(self.owl_path):
            raise FileNotFoundError(f"Ontologie introuvable : {self.owl_path}")
        self.graph = Graph()
        self.graph.parse(self.owl_path, format="xml")
        self.graph.bind("med", ONTO_NS)
        self.graph.bind("owl", OWL)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("rdf", RDF)
        print(f"[RDFLib] Ontologie chargée avec succès ({len(self.graph)} triplets).")

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
