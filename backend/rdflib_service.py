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
        """
        Charge et fusionne dynamiquement toutes les ontologies médicales du projet.
        Supporte à la fois Turtle (.ttl) et RDF/XML (.owl).
        Permet la prise en compte immédiate de tout ajout dans Protégé,
        que l'utilisateur enregistre dans ontologie_medicale (1).ttl ou ontologie_personne.owl.
        """
        self.graph = Graph()
        self.loaded_sources = []

        sources = [
            (os.path.join(BASE_DIR, "ontologie_personne.owl"), "xml"),
            (os.path.join(BASE_DIR, "ontologie_medicale (1).ttl"), "turtle"),
            (os.path.join(BASE_DIR, "ontologie_medicale.owl"), "xml"),
        ]

        for path, fmt in sources:
            if os.path.exists(path):
                try:
                    self.graph.parse(path, format=fmt)
                    self.loaded_sources.append(os.path.basename(path))
                except Exception as e:
                    print(f"[RDFLib] Avertissement parsing {os.path.basename(path)}: {e}")

        if len(self.graph) == 0:
            raise FileNotFoundError("Aucun fichier d'ontologie n'a pu être chargé.")

        self.graph.bind("med", ONTO_NS)
        self.graph.bind("owl", OWL)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("rdf", RDF)
        print(f"[RDFLib] Ontologies chargées dynamiquement ({', '.join(self.loaded_sources)}) - Total : {len(self.graph)} triplets.")

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

        # Déduplication intelligente des résultats basée sur la valeur textuelle
        unique_bindings = []
        seen_keys = set()
        for b in bindings:
            key = tuple((var, b.get(var, {}).get("value")) for var in vars_list)
            if key not in seen_keys:
                seen_keys.add(key)
                unique_bindings.append(b)

        return {
            "head": {"vars": vars_list},
            "results": {"bindings": unique_bindings}
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
            "file": " + ".join(getattr(self, "loaded_sources", [os.path.basename(self.owl_path)]))
        }

    def get_all_personnes(self) -> List[Dict[str, Any]]:
        """Extrait tous les détails sur les individus de la classe Personne avec fallback sur nom/label/id."""
        q = """
        PREFIX : <http://example.org/ontologie-medicale#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?p ?type ?nom ?prenom ?label ?email ?age ?cin ?telephone ?adresse ?dossier ?groupeSanguin ?specialite ?service WHERE {
            ?p rdf:type ?type .
            ?type rdfs:subClassOf* :Personne .
            OPTIONAL { ?p :nom ?nom }
            OPTIONAL { ?p :prenom ?prenom }
            OPTIONAL { ?p rdfs:label ?label }
            OPTIONAL { ?p :email ?email }
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
                nom_val = r.get("nom", {}).get("value", "")
                prenom_val = r.get("prenom", {}).get("value", "")
                label_val = r.get("label", {}).get("value", "")
                id_clean = uri.split("#")[-1].replace("_", " ")

                if prenom_val and nom_val:
                    if prenom_val.lower() in nom_val.lower():
                        computed_nom = nom_val
                    else:
                        computed_nom = f"{prenom_val} {nom_val}"
                elif nom_val:
                    computed_nom = nom_val
                elif label_val:
                    computed_nom = label_val
                else:
                    computed_nom = id_clean

                personnes_dict[uri] = {
                    "uri": uri,
                    "id": uri.split("#")[-1],
                    "types": [],
                    "nom": computed_nom,
                    "prenom": prenom_val,
                    "email": r.get("email", {}).get("value", ""),
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

    def add_personne(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ajoute un nouvel individu dans l'ontologie de manière dynamique et bidirectionnelle.
        Met à jour le graphe RDFLib et enregistre dans ontologie_medicale (1).ttl et ontologie_personne.owl.
        """
        nom = data.get("nom", "").strip()
        if not nom:
            raise ValueError("Le nom est obligatoire.")

        import re
        id_suffix = re.sub(r'[^a-zA-Z0-9_]', '_', nom.replace(' ', '_'))
        cls_name = data.get("type", "MedecinGeneraliste")
        if not id_suffix.startswith(('Dr_', 'Pat_', 'Stag_')):
            prefix = "Dr_" if "Medecin" in cls_name or cls_name == "Cardiologue" else ("Pat_" if "Patient" in cls_name else "Ind_")
            id_suffix = f"{prefix}{id_suffix}"

        ind_uri = ONTO_NS[id_suffix]
        cls_uri = ONTO_NS[cls_name]

        self.graph.add((ind_uri, RDF.type, OWL.NamedIndividual))
        self.graph.add((ind_uri, RDF.type, cls_uri))
        self.graph.add((ind_uri, RDFS.label, Literal(nom, datatype=rdflib.XSD.string)))
        self.graph.add((ind_uri, ONTO_NS.nom, Literal(nom, datatype=rdflib.XSD.string)))

        if data.get("age"):
            try:
                self.graph.add((ind_uri, ONTO_NS.age, Literal(int(data["age"]), datatype=rdflib.XSD.integer)))
            except (ValueError, TypeError):
                pass

        if data.get("telephone"):
            self.graph.add((ind_uri, ONTO_NS.telephone, Literal(str(data["telephone"]), datatype=rdflib.XSD.string)))

        if data.get("cin"):
            self.graph.add((ind_uri, ONTO_NS.numeroCIN, Literal(str(data["cin"]), datatype=rdflib.XSD.string)))

        if data.get("specialite"):
            self.graph.add((ind_uri, ONTO_NS.specialite, Literal(str(data["specialite"]), datatype=rdflib.XSD.string)))

        if data.get("dossier"):
            self.graph.add((ind_uri, ONTO_NS.numeroDossier, Literal(str(data["dossier"]), datatype=rdflib.XSD.string)))

        if data.get("groupeSanguin"):
            self.graph.add((ind_uri, ONTO_NS.groupeSanguin, Literal(str(data["groupeSanguin"]), datatype=rdflib.XSD.string)))

        # Synchronisation dans le fichier Turtle actif de Protégé
        ttl_path = os.path.join(BASE_DIR, "ontologie_medicale (1).ttl")
        if os.path.exists(ttl_path):
            try:
                with open(ttl_path, "a", encoding="utf-8") as f:
                    f.write(f"\n\n###  http://example.org/ontologie-medicale#{id_suffix}\n")
                    f.write(f":{id_suffix} rdf:type owl:NamedIndividual ,\n")
                    f.write(f"                     :{cls_name} ;\n")
                    f.write(f'            rdfs:label "{nom}" ;\n')
                    f.write(f'            :nom "{nom}"')
                    if data.get("age"):
                        f.write(f" ;\n            :age {data['age']}")
                    if data.get("telephone"):
                        f.write(f' ;\n            :telephone "{data["telephone"]}"')
                    if data.get("cin"):
                        f.write(f' ;\n            :numeroCIN "{data["cin"]}"')
                    if data.get("specialite"):
                        f.write(f' ;\n            :specialite "{data["specialite"]}"')
                    if data.get("dossier"):
                        f.write(f' ;\n            :numeroDossier "{data["dossier"]}"')
                    if data.get("groupeSanguin"):
                        f.write(f' ;\n            :groupeSanguin "{data["groupeSanguin"]}"')
                    f.write(" .\n")
            except Exception as e:
                print(f"[RDFLib] Erreur append TTL : {e}")

        # Synchronisation dans ontologie_personne.owl
        owl_p = os.path.join(BASE_DIR, "ontologie_personne.owl")
        if os.path.exists(owl_p):
            try:
                self.graph.serialize(destination=owl_p, format="xml")
            except Exception as e:
                print(f"[RDFLib] Erreur save OWL : {e}")

        return {
            "success": True,
            "id": id_suffix,
            "uri": str(ind_uri),
            "nom": nom,
            "type": cls_name,
            "triples_count": len(self.graph)
        }

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
# Service Maladie — Module dédié aux maladies (ontologie_maladie.owl)
# ======================================================================
MALADIE_OWL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ontologie_maladie.owl")

class MaladieService:
    """Service RDFLib pour le module Maladie."""

    def __init__(self):
        self.graph = Graph()
        self.loaded = False
        self._load()

    def _load(self):
        if os.path.exists(MALADIE_OWL_PATH):
            try:
                self.graph.parse(MALADIE_OWL_PATH, format="xml")
                self.graph.bind("mal", Namespace("http://example.org/ontologie-maladie#"))
                self.loaded = True

                # Chargement des ontologies pour les questions croisées (Sami, Dr Fatima, diagnostics)
                pers_path = os.path.join(BASE_DIR, "ontologie_personne.owl")
                if os.path.exists(pers_path):
                    try:
                        self.graph.parse(pers_path, format="xml")
                    except Exception:
                        pass

                med_path = os.path.join(BASE_DIR, "ontologie_medicale.owl")
                if os.path.exists(med_path):
                    try:
                        self.graph.parse(med_path, format="xml")
                    except Exception:
                        pass

                self.graph.bind("med", Namespace("http://example.org/ontologie-medicale#"))
                print(f"[MaladieService] ontologies chargées ({len(self.graph)} triplets).")
            except Exception as e:
                print(f"[MaladieService] Erreur chargement OWL : {e}")
        else:
            print(f"[MaladieService] ontologie_maladie.owl introuvable — module désactivé.")

    NS = "http://example.org/ontologie-maladie#"

    def execute_sparql(self, query_str: str) -> Dict[str, Any]:
        """Exécute une requête SPARQL sur le graphe Maladie."""
        import re
        prefixes = f"""PREFIX mal: <{self.NS}>
PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""
        q = query_str.strip()
        q = re.sub(r'PREFIX\s+:\s+<[^>]+>', '', q, flags=re.IGNORECASE)
        if "PREFIX mal:" not in q:
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
        """Retourne tous les individus Maladie avec leurs propriétés."""
        q = """
        SELECT ?m ?type ?nom ?codeCIM ?gravite ?contagieuse ?chronique ?duree WHERE {
            ?m rdf:type ?type .
            ?type rdfs:subClassOf* mal:Maladie .
            OPTIONAL { ?m mal:nom ?nom }
            OPTIONAL { ?m mal:codeCIM ?codeCIM }
            OPTIONAL { ?m mal:gravite ?gravite }
            OPTIONAL { ?m mal:estContagieuse ?contagieuse }
            OPTIONAL { ?m mal:estChronique ?chronique }
            OPTIONAL { ?m mal:dureeTraitement ?duree }
        }
        """
        rows = self.execute_sparql(q)["results"]["bindings"]
        maladies_dict = {}
        for r in rows:
            uri = r["m"]["value"]
            if uri not in maladies_dict:
                maladies_dict[uri] = {
                    "id": uri.split("#")[-1],
                    "types": [],
                    "nom": r.get("nom", {}).get("value", uri.split("#")[-1]),
                    "codeCIM": r.get("codeCIM", {}).get("value", ""),
                    "gravite": r.get("gravite", {}).get("value", "1"),
                    "contagieuse": r.get("contagieuse", {}).get("value", "false"),
                    "chronique": r.get("chronique", {}).get("value", "false"),
                    "duree": r.get("duree", {}).get("value", ""),
                    "symptomes": [],
                    "medicaments": []
                }
            type_val = r["type"]["value"].split("#")[-1]
            if type_val not in maladies_dict[uri]["types"] and type_val not in ["NamedIndividual", "Thing"]:
                maladies_dict[uri]["types"].append(type_val)

        # Charger les symptômes liés
        q2 = """
        SELECT ?m ?sNom WHERE {
            ?m mal:aPourSymptome ?s .
            OPTIONAL { ?s mal:nomSymptome ?sNom }
        }
        """
        for r in self.execute_sparql(q2)["results"]["bindings"]:
            uri = r["m"]["value"]
            if uri in maladies_dict:
                snom = r.get("sNom", {}).get("value", r.get("s", {}).get("value", "").split("#")[-1])
                if snom and snom not in maladies_dict[uri]["symptomes"]:
                    maladies_dict[uri]["symptomes"].append(snom)

        # Charger les médicaments liés
        q3 = """
        SELECT ?m ?medId WHERE {
            ?m mal:estTraiteePar ?med .
            BIND(STRAFTER(STR(?med), "#") AS ?medId)
        }
        """
        for r in self.execute_sparql(q3)["results"]["bindings"]:
            uri = r["m"]["value"]
            if uri in maladies_dict:
                mid = r.get("medId", {}).get("value", "")
                if mid and mid not in maladies_dict[uri]["medicaments"]:
                    maladies_dict[uri]["medicaments"].append(mid)

        result = [v for v in maladies_dict.values() if "Maladie" not in v["types"] or len(v["types"]) > 0]
        # Garder seulement les individus (pas les classes)
        filtered = [v for v in result if any(t in ["Grippe","Angine","Diabete","Hypertension","UlcereGastrique",
                                                   "MaladieInfectieuse","MaladieChronique","MaladieDigestive"] for t in v["types"])]

        # S'assurer que les sous-classes héritent des super-classes pour les filtres UI
        for m in filtered:
            if any(t in ["Grippe", "Angine"] for t in m["types"]) and "MaladieInfectieuse" not in m["types"]:
                m["types"].append("MaladieInfectieuse")
            if any(t in ["Diabete", "Hypertension"] for t in m["types"]) and "MaladieChronique" not in m["types"]:
                m["types"].append("MaladieChronique")
            if any(t in ["UlcereGastrique"] for t in m["types"]) and "MaladieDigestive" not in m["types"]:
                m["types"].append("MaladieDigestive")

        return filtered

    def get_graph_maladie(self) -> Dict[str, Any]:
        """Retourne les nœuds et liens du graphe Maladie."""
        q = """
        SELECT ?s ?p ?o WHERE {
            ?s ?p ?o .
            FILTER(?p IN (mal:aPourSymptome, mal:estTraiteePar, mal:touche,
                          mal:necessite, mal:necessiteSuiviPar, mal:estPrescritePour))
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
