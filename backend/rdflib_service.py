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
            (os.path.join(BASE_DIR, "ontologie_maladie.owl"), "xml"),
            (os.path.join(BASE_DIR, "ontologie_medicament.owl"), "xml"),
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
        self.graph.bind("mal", Namespace("http://example.org/ontologie-maladie#"))
        self.graph.bind("", ONTO_NS)
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
PREFIX mal: <http://example.org/ontologie-maladie#>
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
            OPTIONAL { ?m med:codeCIM ?cim }
            OPTIONAL { ?m med:dureeTraitement ?duree }
        }
        """
        CIM_DEFAULTS = {
            "Grippe": "J11", "Angine": "J03", "Diabete": "E11", "Hypertension": "I10",
            "Ulcere_Exemple": "K25", "Ulcere_gastrique": "K25", "Asthme": "J45",
            "Bronchite": "J20", "Paludisme": "B54", "Anemie": "D64", "Gastrite": "K29",
            "Migraine": "G43", "Arthrite": "M13"
        }
        DUREE_DEFAULTS = {
            "Grippe": "7 jours", "Angine": "10 jours", "Diabete": "Traitement a vie",
            "Hypertension": "Traitement a vie", "Ulcere_Exemple": "4 a 8 semaines",
            "Asthme": "Traitement continu", "Bronchite": "10 jours", "Paludisme": "3 a 7 jours",
            "Anemie": "3 a 6 mois", "Gastrite": "2 a 4 semaines", "Migraine": "Traitement de crise",
            "Arthrite": "Traitement continu"
        }
        rows = self.execute_sparql(q)["results"]["bindings"]
        maladies_dict = {}
        for r in rows:
            uri = r["m"]["value"]
            ind_id = uri.split("#")[-1]
            if ind_id in ["Fievre_Sami", "Grippe_Sami"]:
                continue
            if uri not in maladies_dict:
                lbl = r.get("label", {}).get("value", "")
                raw_grav = r.get("gravite", {}).get("value", "")
                # Mapper la gravité textuelle / numérique
                grav_norm = "1"
                if "mod" in raw_grav.lower() or raw_grav == "2":
                    grav_norm = "2"
                elif "grav" in raw_grav.lower() or raw_grav == "3" or "sev" in raw_grav.lower():
                    grav_norm = "3"

                is_chronique = "true" if any(k in r["type"]["value"] for k in ["Chronique", "Diabete", "Hypertension", "Asthme", "Anemie", "Arthrite", "Migraine"]) else "false"
                cim_val = r.get("cim", {}).get("value", "") or CIM_DEFAULTS.get(ind_id, "")
                duree_val = r.get("duree", {}).get("value", "") or DUREE_DEFAULTS.get(ind_id, "")

                maladies_dict[uri] = {
                    "id": ind_id,
                    "types": [],
                    "nom": lbl or ind_id.replace("_", " "),
                    "description": r.get("desc", {}).get("value", ""),
                    "codeCIM": cim_val,
                    "gravite": grav_norm,
                    "contagieuse": r.get("contagieuse", {}).get("value", "false"),
                    "chronique": is_chronique,
                    "duree": duree_val,
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

    def get_maladie_ontology_structure(self) -> Dict[str, Any]:
        """Retourne la définition formelle complète de l'ontologie de la classe Maladie."""
        all_maladies = self.get_all_maladies()

        # Répartition dynamique des individus dans les sous-classes
        infectieuses_ind = []
        chroniques_ind = []
        digestives_ind = []
        grippe_ind = []
        angine_ind = []
        diabete_ind = []
        hypertension_ind = []
        ulcere_ind = []

        for m in all_maladies:
            mid = m.get("id", "")
            mnom = m.get("nom", mid)
            mtypes = " ".join(m.get("types", []))
            item = {"id": mid, "nom": mnom, "gravite": m.get("gravite", "2"), "codeCIM": m.get("codeCIM", "")}

            if "Grippe" in mtypes or "grippe" in mid.lower():
                grippe_ind.append(item)
            elif "Angine" in mtypes or "angine" in mid.lower():
                angine_ind.append(item)
            
            if "Infectieuse" in mtypes or "grippe" in mid.lower() or "angine" in mid.lower() or "bronchite" in mid.lower() or "covid" in mid.lower():
                infectieuses_ind.append(item)
            elif "Diabete" in mtypes or "diabete" in mid.lower():
                diabete_ind.append(item)
                chroniques_ind.append(item)
            elif "Hypertension" in mtypes or "hypertension" in mid.lower():
                hypertension_ind.append(item)
                chroniques_ind.append(item)
            elif "Chronique" in mtypes or m.get("chronique") == "true" or "asthme" in mid.lower():
                chroniques_ind.append(item)
            elif "Digestive" in mtypes or "ulcere" in mid.lower() or "gastrite" in mid.lower():
                if "ulcere" in mid.lower():
                    ulcere_ind.append(item)
                digestives_ind.append(item)
            else:
                infectieuses_ind.append(item)

        return {
            "iri": "http://example.org/ontologie-maladie#",
            "class_info": {
                "uri": "http://example.org/ontologie-maladie#Maladie",
                "name": "Maladie",
                "label": "Maladie",
                "comment": "Toute affection pathologique dans le système médical.",
                "superclass": "owl:Thing",
                "total_instances": len(all_maladies)
            },
            "subclasses": [
                {
                    "id": "MaladieInfectieuse",
                    "name": "Maladie infectieuse",
                    "uri": "http://example.org/ontologie-maladie#MaladieInfectieuse",
                    "icon": "🦠",
                    "color": "#ec4899",
                    "description": "Affection provoquée par la transmission d'un agent pathogène biologique (virus, bactérie).",
                    "disjointWith": ["MaladieChronique", "MaladieDigestive"],
                    "children": [
                        {
                            "id": "Grippe",
                            "name": "Grippe",
                            "uri": "http://example.org/ontologie-maladie#Grippe",
                            "icon": "🌡️",
                            "disjointWith": ["Angine"],
                            "description": "Infection virale respiratoire aiguë et contagieuse causée par le virus Influenza.",
                            "individuals": grippe_ind
                        },
                        {
                            "id": "Angine",
                            "name": "Angine",
                            "uri": "http://example.org/ontologie-maladie#Angine",
                            "icon": "🗣️",
                            "disjointWith": ["Grippe"],
                            "description": "Inflammation aiguë pharyngo-amygdalienne bactérienne ou virale.",
                            "individuals": angine_ind
                        }
                    ],
                    "individuals": infectieuses_ind
                },
                {
                    "id": "MaladieChronique",
                    "name": "Maladie chronique",
                    "uri": "http://example.org/ontologie-maladie#MaladieChronique",
                    "icon": "🗓️",
                    "color": "#3b82f6",
                    "description": "Affection de longue durée évoluant lentement et nécessitant une prise en charge médicale suivie.",
                    "disjointWith": ["MaladieInfectieuse", "MaladieDigestive"],
                    "children": [
                        {
                            "id": "Diabete",
                            "name": "Diabète",
                            "uri": "http://example.org/ontologie-maladie#Diabete",
                            "icon": "🩸",
                            "disjointWith": ["Hypertension"],
                            "description": "Trouble métabolique caractérisé par une anomalie de régulation de la glycémie.",
                            "individuals": diabete_ind
                        },
                        {
                            "id": "Hypertension",
                            "name": "Hypertension Artérielle",
                            "uri": "http://example.org/ontologie-maladie#Hypertension",
                            "icon": "💓",
                            "disjointWith": ["Diabete"],
                            "description": "Élévation anormale et prolongée de la pression sanguine artérielle.",
                            "individuals": hypertension_ind
                        }
                    ],
                    "individuals": chroniques_ind
                },
                {
                    "id": "MaladieDigestive",
                    "name": "Maladie digestive",
                    "uri": "http://example.org/ontologie-maladie#MaladieDigestive",
                    "icon": "🫀",
                    "color": "#8b5cf6",
                    "description": "Trouble ou lésion pathologique touchant le tube digestif ou les organes annexes.",
                    "disjointWith": ["MaladieInfectieuse", "MaladieChronique"],
                    "children": [
                        {
                            "id": "UlcereGastrique",
                            "name": "Ulcère gastrique",
                            "uri": "http://example.org/ontologie-maladie#UlcereGastrique",
                            "icon": "🫧",
                            "disjointWith": [],
                            "description": "Lésion érosive de la muqueuse de l'estomac souvent induite par Helicobacter pylori.",
                            "individuals": ulcere_ind
                        }
                    ],
                    "individuals": digestives_ind
                }
            ],
            "defined_classes": [
                {
                    "name": "MaladieGrave",
                    "label": "Maladie grave",
                    "axiom": "Maladie ⊓ ∃ necessite.Operation",
                    "description": "Toute maladie requérant une intervention chirurgicale obligatoire.",
                    "type": "owl:equivalentClass"
                },
                {
                    "name": "MaladieAvecSuivi",
                    "label": "Maladie avec suivi",
                    "axiom": "MaladieChronique ⊓ ∃ necessiteSuiviPar.Medecin",
                    "description": "Toute maladie chronique impliquant une surveillance médicale continue par un médecin.",
                    "type": "owl:equivalentClass"
                },
                {
                    "name": "MaladieTraitee",
                    "label": "Maladie traitée",
                    "axiom": "Maladie ⊓ ∃ estTraiteePar.Medicament",
                    "description": "Toute pathologie faisant l'objet d'un protocole thérapeutique médicamenteux.",
                    "type": "owl:equivalentClass"
                }
            ],
            "object_properties": [
                {
                    "name": "aPourSymptome",
                    "label": "a pour symptôme",
                    "domain": "Maladie",
                    "range": "Symptome",
                    "inverse": "estSymptomeDe",
                    "description": "Relie la pathologie aux signes cliniques et symptômes observés.",
                    "characteristics": []
                },
                {
                    "name": "estTraiteePar",
                    "label": "est traitée par",
                    "domain": "Maladie",
                    "range": "Medicament",
                    "inverse": "traite",
                    "description": "Associe la maladie aux médicaments actifs indiqués.",
                    "characteristics": []
                },
                {
                    "name": "touche",
                    "label": "touche",
                    "domain": "Maladie",
                    "range": "Patient",
                    "inverse": "souffreDe",
                    "description": "Spécifie le patient atteint par l'affection.",
                    "characteristics": []
                },
                {
                    "name": "necessite",
                    "label": "nécessite",
                    "domain": "Maladie",
                    "range": "Operation",
                    "inverse": "estNecessairePour",
                    "description": "Définit les interventions chirurgicales indispensables.",
                    "characteristics": []
                },
                {
                    "name": "concerneMaladie",
                    "label": "concerne maladie",
                    "domain": "Maladie",
                    "range": "Ordonnance",
                    "inverse": "estPrescritePour",
                    "description": "Lie la prescription médicale ordonnancée à la pathologie.",
                    "characteristics": []
                },
                {
                    "name": "necessiteSuiviPar",
                    "label": "nécessite suivi par",
                    "domain": "MaladieChronique",
                    "range": "Medecin",
                    "inverse": "suit",
                    "description": "Assure la traçabilité du suivi médical spécialisé.",
                    "characteristics": []
                },
                {
                    "name": "aPourAgentPathogene",
                    "label": "a pour agent pathogène",
                    "domain": "MaladieInfectieuse",
                    "range": "AgentPathogene (Virus, Bactérie)",
                    "inverse": "causeMaladie",
                    "description": "Désigne l'agent microbiologique causal de l'infection.",
                    "characteristics": []
                },
                {
                    "name": "provoque",
                    "label": "provoque",
                    "domain": "Maladie",
                    "range": "Symptome",
                    "inverse": "—",
                    "description": "Relation causale transitive entre maladie et symptômes secondaires.",
                    "characteristics": ["owl:TransitiveProperty"]
                }
            ],
            "datatype_properties": [
                {
                    "name": "nom",
                    "type": "xsd:string",
                    "characteristics": ["owl:FunctionalProperty"],
                    "domain": "Maladie",
                    "description": "Nom usuel ou officiel de la maladie."
                },
                {
                    "name": "description",
                    "type": "xsd:string",
                    "characteristics": ["owl:FunctionalProperty"],
                    "domain": "Maladie",
                    "description": "Descriptif médical clinique approfondi."
                },
                {
                    "name": "codeCIM",
                    "type": "xsd:string",
                    "characteristics": ["owl:FunctionalProperty"],
                    "domain": "Maladie",
                    "description": "Code international de classification OMS (CIM-10)."
                },
                {
                    "name": "gravite",
                    "type": "xsd:integer",
                    "characteristics": ["owl:FunctionalProperty"],
                    "domain": "Maladie",
                    "description": "Niveau de sévérité médicale codé de 1 (légère) à 4 (critique)."
                },
                {
                    "name": "estContagieuse",
                    "type": "xsd:boolean",
                    "characteristics": ["owl:FunctionalProperty"],
                    "domain": "Maladie",
                    "description": "Indicateur binaire de transmissibilité épidémique."
                },
                {
                    "name": "estChronique",
                    "type": "xsd:boolean",
                    "characteristics": ["owl:FunctionalProperty"],
                    "domain": "Maladie",
                    "description": "Indicateur binaire d'évolution chronique dans le temps."
                },
                {
                    "name": "dureeTraitement",
                    "type": "xsd:string",
                    "characteristics": [],
                    "domain": "Maladie",
                    "description": "Période standard observée pour le traitement curatif."
                }
            ],
            "axioms": [
                {
                    "type": "owl:AllDisjointClasses",
                    "elements": ["MaladieInfectieuse", "MaladieChronique", "MaladieDigestive"],
                    "description": "Disjonction mutuelle stricte : aucune maladie ne peut appartenir à deux catégories principales à la fois."
                },
                {
                    "type": "owl:disjointWith",
                    "elements": ["Grippe", "Angine"],
                    "description": "Une instance de Grippe ne peut en aucun cas être une instance d'Angine."
                },
                {
                    "type": "owl:disjointWith",
                    "elements": ["Diabete", "Hypertension"],
                    "description": "Une instance de Diabète est disjointe d'une instance d'Hypertension."
                },
                {
                    "type": "owl:disjointWith",
                    "elements": ["Virus", "Bacterie"],
                    "description": "Un agent pathogène viral est disjoint d'un agent pathogène bactérien."
                }
            ],
            "stats": {
                "total": len(all_maladies),
                "infectieuses": len(infectieuses_ind),
                "chroniques": len(chroniques_ind),
                "digestives": len(digestives_ind)
            }
        }

