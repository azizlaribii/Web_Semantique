# -*- coding: utf-8 -*-
"""
Service Back-end : Module Médicament (Python + RDFLib)
Charge ontologie_medicament.owl (+ ontologie_maladie.owl pour les liens croisés)
et expose les données des médicaments, molécules, effets secondaires,
contre-indications, interactions et essais cliniques.
"""

import os
import re
import shutil
import threading
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, List, Optional

try:
    import pyparsing_patch  # noqa: F401  (compatibilité Python 3.14 + pyparsing)
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import pyparsing_patch  # noqa: F401

from rdflib import Graph, Namespace, URIRef, Literal, RDF

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDICAMENT_OWL_PATH = os.path.join(BASE_DIR, "ontologie_medicament.owl")
MALADIE_OWL_PATH = os.path.join(BASE_DIR, "ontologie_maladie.owl")
# Copie de l'ontologie d'origine, créée au premier démarrage, pour pouvoir réinitialiser après des tests CRUD
BACKUP_OWL_PATH = os.path.join(BASE_DIR, "ontologie_medicament.original.owl")

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
        self.graph_maladie = Graph()     # triplets du module Maladie (exclus à la sauvegarde)
        self.loaded = False
        self.lock = threading.Lock()
        self._load()

    def _load(self):
        self.graph = Graph()
        self.graph_maladie = Graph()
        if not os.path.exists(self.owl_path):
            print("[MedicamentService] ontologie_medicament.owl introuvable — "
                  "lancez medicament_owlready2.py. Module désactivé.")
            return
        try:
            if self.owl_path == MEDICAMENT_OWL_PATH and not os.path.exists(BACKUP_OWL_PATH):
                shutil.copyfile(self.owl_path, BACKUP_OWL_PATH)
            self.graph.parse(self.owl_path, format="xml")
            # Module Maladie chargé pour les questions croisées (noms des maladies traitées)
            if os.path.exists(MALADIE_OWL_PATH):
                try:
                    self.graph_maladie.parse(MALADIE_OWL_PATH, format="xml")
                    self.graph += self.graph_maladie
                except Exception as e:
                    print(f"[MedicamentService] Maladie non chargée : {e}")
            # Intégrer les médicaments et molécules définis dans ontologie_medicale (1).ttl
            ttl_path = os.path.join(BASE_DIR, "ontologie_medicale (1).ttl")
            if os.path.exists(ttl_path):
                try:
                    ttl_g = Graph()
                    ttl_g.parse(ttl_path, format="turtle")
                    self.graph += ttl_g
                except Exception as e:
                    print(f"[MedicamentService] TTL non chargé : {e}")
            self.graph.bind("mdc", Namespace(MDC_NS))
            self.graph.bind("med", Namespace("http://example.org/ontologie-medicale#"))
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
                "maladiesTraiteesIds": [],
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
        SELECT ?m ?mol ?nom ?formule ?masse WHERE {
            ?m mdc:contientMolecule ?mol .
            OPTIONAL { ?mol mdc:nomMolecule ?nom }
            OPTIONAL { ?mol mdc:formuleBrute ?formule }
            OPTIONAL { ?mol mdc:masseMolaire ?masse }
        }"""):
            if r["m"] in meds:
                meds[r["m"]]["molecules"].append({
                    "id": _local(r["mol"]), "nom": r.get("nom", ""), "formule": r.get("formule", ""), "masse": r.get("masse", "")
                })

        # Effets secondaires
        for r in self._rows("""
        SELECT ?m ?e ?nom ?freq ?grav ?type WHERE {
            ?m mdc:peutProvoquer ?e .
            ?e rdf:type ?type . ?type rdfs:subClassOf mdc:EffetSecondaire .
            FILTER(?type != mdc:EffetGrave)
            OPTIONAL { ?e mdc:nomEffet ?nom }
            OPTIONAL { ?e mdc:frequence ?freq }
            OPTIONAL { ?e mdc:graviteEffet ?grav }
        } ORDER BY DESC(?grav)"""):
            if r["m"] in meds:
                meds[r["m"]]["effets"].append({
                    "id": _local(r["e"]), "nom": r.get("nom", ""), "frequence": r.get("freq", ""),
                    "gravite": r.get("grav", "1"), "type": _local(r.get("type", ""))
                })

        # Contre-indications : conditions cliniques + maladies (module Maladie)
        for r in self._rows("""
        SELECT ?m ?cible ?label ?source WHERE {
            {
                ?m mdc:estContreIndiqueEn ?cible .
                OPTIONAL { ?cible mdc:nomCondition ?n }
                BIND(COALESCE(?n, STRAFTER(STR(?cible), "#")) AS ?label)
                BIND("condition" AS ?source)
            } UNION {
                ?m mdc:estContreIndiquePour ?cible .
                OPTIONAL { ?cible mal:nom ?n2 }
                BIND(COALESCE(?n2, STRAFTER(STR(?cible), "#")) AS ?label)
                BIND("maladie" AS ?source)
            }
        }"""):
            if r["m"] in meds:
                meds[r["m"]]["contreIndications"].append(
                    {"id": _local(r["cible"]), "label": r["label"], "source": r["source"]})

        # Maladies traitées
        for r in self._rows("""
        SELECT ?m ?mal ?label WHERE {
            ?m mdc:traite ?mal .
            OPTIONAL { ?mal mal:nom ?n }
            BIND(COALESCE(?n, STRAFTER(STR(?mal), "#")) AS ?label)
        }"""):
            if r["m"] in meds:
                meds[r["m"]]["maladiesTraitees"].append(r["label"])
                meds[r["m"]]["maladiesTraiteesIds"].append(_local(r["mal"]))

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

    # ==================================================================
    # CRUD — SPARQL Update (INSERT DATA / DELETE-INSERT-WHERE / DELETE WHERE)
    # ==================================================================
    # Propriétés de données modifiables : clé JSON -> (propriété OWL, type)
    CHAMPS = {
        "nom":               ("nomCommercial", "str"),
        "dosage":            ("dosage", "str"),
        "forme":             ("formeGalenique", "str"),
        "voie":              ("voieAdministration", "str"),
        "posologie":         ("posologie", "str"),
        "codeATC":           ("codeATC", "str"),
        "prix":              ("prixTND", "decimal"),
        "ordonnance":        ("necessiteOrdonnance", "bool"),
    }
    # Relations modifiables : clé JSON -> (propriété OWL, namespace de la cible, classe attendue)
    RELATIONS = {
        "effets":            ("peutProvoquer", MDC_NS, "mdc:EffetSecondaire"),
        "conditions":        ("estContreIndiqueEn", MDC_NS, "mdc:ConditionClinique"),
        "maladiesTraitees":  ("traite", MAL_NS, "mal:Maladie"),
        "maladiesContreIndiquees": ("estContreIndiquePour", MAL_NS, "mal:Maladie"),
    }

    # Règles d'inférence exécutées après chaque écriture (équivalent SPARQL des classes définies OWL,
    # pour que les nouveaux individus soient classés sans relancer HermiT)
    REGLES_INFERENCE = """
DELETE { ?x rdf:type mdc:EffetGrave } WHERE { ?x rdf:type mdc:EffetGrave } ;
INSERT { ?x rdf:type mdc:EffetGrave } WHERE { ?x mdc:graviteEffet 3 } ;
DELETE { ?m rdf:type mdc:MedicamentARisque } WHERE { ?m rdf:type mdc:MedicamentARisque } ;
INSERT { ?m rdf:type mdc:MedicamentARisque } WHERE { ?m mdc:peutProvoquer ?e . ?e rdf:type mdc:EffetGrave } ;
DELETE { ?m rdf:type mdc:MedicamentSurOrdonnance } WHERE { ?m rdf:type mdc:MedicamentSurOrdonnance } ;
INSERT { ?m rdf:type mdc:MedicamentSurOrdonnance } WHERE { ?m mdc:necessiteOrdonnance true } ;
DELETE { ?m rdf:type mdc:MedicamentEvalueCliniquement } WHERE { ?m rdf:type mdc:MedicamentEvalueCliniquement } ;
INSERT { ?m rdf:type mdc:MedicamentEvalueCliniquement } WHERE { ?essai mdc:evalue ?m }"""

    class ErreurValidation(ValueError):
        pass

    # ------------------------------------------------------------------
    def execute_update(self, update_str: str):
        """Exécute une requête SPARQL Update sur le graphe."""
        q = update_str.strip()
        if "PREFIX mdc:" not in q:
            q = PREFIXES_MDC + q
        self.graph.update(q)

    def _save(self):
        """Écrit ontologie_medicament.owl (RDF/XML, ouvrable dans Protégé) sans les triplets Maladie."""
        g = Graph()
        for prefix, ns in self.graph.namespaces():
            g.bind(prefix, ns, override=True)
        for t in self.graph:
            if t not in self.graph_maladie:
                g.add(t)
        g.bind("", Namespace(MDC_NS), override=True)
        g.serialize(destination=self.owl_path, format="xml")

    def _commit(self, update: str) -> str:
        """Exécute la mise à jour + les règles d'inférence, puis sauvegarde. Retourne le SPARQL exécuté."""
        self.execute_update(update)
        self.execute_update(self.REGLES_INFERENCE)
        self._save()
        return update.strip()

    def reset(self):
        """Restaure l'ontologie d'origine (copie faite au premier démarrage)."""
        with self.lock:
            if not os.path.exists(BACKUP_OWL_PATH):
                raise self.ErreurValidation("Aucune sauvegarde d'origine trouvée.")
            shutil.copyfile(BACKUP_OWL_PATH, self.owl_path)
            self._load()

    # ------------------------------------------------------------------
    # Validation et construction des littéraux
    # ------------------------------------------------------------------
    @staticmethod
    def _identifiant(texte: str) -> str:
        t = unicodedata.normalize("NFD", texte)
        t = "".join(c for c in t if unicodedata.category(c) != "Mn")
        t = re.sub(r"[^A-Za-z0-9]+", "_", t).strip("_")
        if not t:
            raise MedicamentService.ErreurValidation("Nom invalide.")
        if t[0].isdigit():
            t = "M_" + t
        return t[0].upper() + t[1:]

    def _existe(self, uri: str, classe: Optional[str] = None) -> bool:
        cond = f"<{uri}> rdf:type/rdfs:subClassOf* {classe}" if classe else f"<{uri}> ?p ?o"
        return bool(self.graph.query(PREFIXES_MDC + f"ASK {{ {cond} }}").askAnswer)

    def _est_medicament(self, mid: str) -> bool:
        return self._existe(MDC_NS + mid, "mdc:Medicament")

    def _litteral(self, valeur, typ: str) -> str:
        if typ == "bool":
            if isinstance(valeur, str):
                valeur = valeur.strip().lower() in ("true", "1", "oui", "on")
            return Literal(bool(valeur)).n3(self.graph.namespace_manager)
        if typ == "decimal":
            try:
                d = Decimal(str(valeur).replace(",", "."))
            except InvalidOperation:
                raise self.ErreurValidation(f"Nombre invalide : {valeur}")
            if d < 0:
                raise self.ErreurValidation("Le prix ne peut pas être négatif.")
            return Literal(d).n3(self.graph.namespace_manager)
        texte = str(valeur).strip()
        if len(texte) > 300:
            raise self.ErreurValidation("Texte trop long (300 caractères maximum).")
        return Literal(texte).n3(self.graph.namespace_manager)

    def _cibles(self, cle: str, ids) -> List[str]:
        """Vérifie que chaque id de relation existe et a la bonne classe ; retourne les URI en N3."""
        prop, ns, classe = self.RELATIONS[cle]
        out = []
        for i in ids or []:
            if not re.fullmatch(r"[A-Za-z0-9_]+", str(i)) or not self._existe(ns + i, classe):
                raise self.ErreurValidation(f"Valeur inconnue pour {cle} : {i}")
            out.append(f"{'mal' if ns == MAL_NS else 'mdc'}:{i}")
        return out

    def _molecule(self, data, mid: str):
        """Retourne (URI N3 de la molécule, triplets à insérer si elle est nouvelle)."""
        mol_id = data.get("moleculeId")
        if mol_id:
            if not self._existe(MDC_NS + mol_id, "mdc:Molecule"):
                raise self.ErreurValidation(f"Molécule inconnue : {mol_id}")
            return f"mdc:{mol_id}", ""
        nom = (data.get("moleculeNom") or "").strip()
        if not nom:
            raise self.ErreurValidation("Choisissez une molécule existante ou saisissez-en une nouvelle "
                                        "(axiome : tout Medicament contient au moins une Molecule).")
        nid = "Mol_" + self._identifiant(nom)
        if self._existe(MDC_NS + nid):
            return f"mdc:{nid}", ""
        triplets = f"    mdc:{nid} rdf:type owl:NamedIndividual , mdc:Molecule ;\n" \
                   f"        mdc:nomMolecule {self._litteral(nom, 'str')}"
        if data.get("moleculeFormule"):
            triplets += f" ;\n        mdc:formuleBrute {self._litteral(data['moleculeFormule'], 'str')}"
        triplets += " .\n"
        return f"mdc:{nid}", triplets

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------
    def create_medicament(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            nom = (data.get("nom") or "").strip()
            if not nom:
                raise self.ErreurValidation("Le nom commercial est obligatoire.")
            mid = self._identifiant(nom)
            if self._existe(MDC_NS + mid):
                raise self.ErreurValidation(f"Un individu « {mid} » existe déjà.")
            classes = data.get("classes") or []
            if not classes or any(c not in CLASSES_THERAPEUTIQUES for c in classes):
                raise self.ErreurValidation("Choisissez au moins une classe thérapeutique valide.")

            mol_uri, mol_triplets = self._molecule(data, mid)
            types = " , ".join(["owl:NamedIndividual"] + [f"mdc:{c}" for c in classes])
            lignes = [f"mdc:{mid} rdf:type {types}", f"mdc:contientMolecule {mol_uri}"]
            for cle, (prop, typ) in self.CHAMPS.items():
                if cle == "ordonnance":
                    lignes.append(f"mdc:{prop} {self._litteral(data.get(cle, False), typ)}")
                elif data.get(cle) not in (None, ""):
                    lignes.append(f"mdc:{prop} {self._litteral(data[cle], typ)}")
            for cle, (prop, _, _) in self.RELATIONS.items():
                cibles = self._cibles(cle, data.get(cle))
                if cibles:
                    lignes.append(f"mdc:{prop} {' , '.join(cibles)}")

            update = "INSERT DATA {\n" + mol_triplets + "    " + " ;\n        ".join(lignes) + " .\n}"
            sparql = self._commit(update)
            return {"ok": True, "id": mid, "operation": "CREATE", "sparql_update": sparql}

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------
    def update_medicament(self, mid: str, data: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            if not re.fullmatch(r"[A-Za-z0-9_]+", mid) or not self._est_medicament(mid):
                raise KeyError(mid)
            ops = []
            s = f"mdc:{mid}"
            for cle, (prop, typ) in self.CHAMPS.items():
                if cle not in data:
                    continue
                if cle == "nom" and not str(data[cle]).strip():
                    raise self.ErreurValidation("Le nom commercial ne peut pas être vide.")
                if data[cle] in (None, "") and cle != "ordonnance":
                    ops.append(f"DELETE WHERE {{ {s} mdc:{prop} ?ancien }}")
                    continue
                ops.append(f"DELETE {{ {s} mdc:{prop} ?ancien }}\n"
                           f"INSERT {{ {s} mdc:{prop} {self._litteral(data[cle], typ)} }}\n"
                           f"WHERE {{ OPTIONAL {{ {s} mdc:{prop} ?ancien }} }}")
            if "classes" in data:
                classes = data["classes"] or []
                if not classes or any(c not in CLASSES_THERAPEUTIQUES for c in classes):
                    raise self.ErreurValidation("Choisissez au moins une classe thérapeutique valide.")
                liste = ", ".join(f"mdc:{c}" for c in CLASSES_THERAPEUTIQUES)
                nouvelles = " . ".join(f"{s} rdf:type mdc:{c}" for c in classes)
                ops.append(f"DELETE {{ {s} rdf:type ?c }}\nINSERT {{ {nouvelles} }}\n"
                           f"WHERE {{ OPTIONAL {{ {s} rdf:type ?c FILTER(?c IN ({liste})) }} }}")
            if "moleculeId" in data or "moleculeNom" in data:
                mol_uri, mol_triplets = self._molecule(data, mid)
                if mol_triplets:
                    ops.append("INSERT DATA {\n" + mol_triplets + "}")
                ops.append(f"DELETE {{ {s} mdc:contientMolecule ?m }}\nINSERT {{ {s} mdc:contientMolecule {mol_uri} }}\n"
                           f"WHERE {{ OPTIONAL {{ {s} mdc:contientMolecule ?m }} }}")
            for cle, (prop, _, _) in self.RELATIONS.items():
                if cle not in data:
                    continue
                cibles = self._cibles(cle, data[cle])
                ops.append(f"DELETE WHERE {{ {s} mdc:{prop} ?x }}")
                if cibles:
                    ops.append(f"INSERT DATA {{ {s} mdc:{prop} {' , '.join(cibles)} }}")
            if not ops:
                raise self.ErreurValidation("Aucune modification envoyée.")
            sparql = self._commit(" ;\n".join(ops))
            return {"ok": True, "id": mid, "operation": "UPDATE", "sparql_update": sparql}

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------
    def delete_medicament(self, mid: str) -> Dict[str, Any]:
        with self.lock:
            if not re.fullmatch(r"[A-Za-z0-9_]+", mid) or not self._est_medicament(mid):
                raise KeyError(mid)
            s = f"mdc:{mid}"
            update = f"""# 1. Retirer le médicament de la liste owl:AllDifferent (liste RDF chaînée)
DELETE {{ ?prec rdf:rest ?noeud . ?noeud rdf:first {s} ; rdf:rest ?suiv }}
INSERT {{ ?prec rdf:rest ?suiv }}
WHERE  {{ ?prec rdf:rest ?noeud . ?noeud rdf:first {s} ; rdf:rest ?suiv }} ;
DELETE {{ ?axiome owl:distinctMembers ?noeud . ?noeud rdf:first {s} ; rdf:rest ?suiv }}
INSERT {{ ?axiome owl:distinctMembers ?suiv }}
WHERE  {{ ?axiome owl:distinctMembers ?noeud . ?noeud rdf:first {s} ; rdf:rest ?suiv }} ;
# 2. Supprimer les interactions et essais cliniques qui le concernent
DELETE {{ ?i ?p ?o }} WHERE {{ ?i mdc:impliqueMedicament {s} ; ?p ?o }} ;
DELETE {{ ?essai ?p ?o }} WHERE {{ ?essai mdc:evalue {s} ; ?p ?o }} ;
# 3. Supprimer tous ses triplets (sujet et objet)
DELETE WHERE {{ {s} ?p ?o }} ;
DELETE WHERE {{ ?x ?p {s} }}"""
            sparql = self._commit(update)
            return {"ok": True, "id": mid, "operation": "DELETE", "sparql_update": sparql}

    # ------------------------------------------------------------------
    def get_options(self) -> Dict[str, Any]:
        """Listes de choix pour le formulaire (molécules, effets, conditions, maladies)."""
        def liste(q):
            return [{"id": _local(r["x"]), "label": r["l"]} for r in self._rows(q)]
        return {
            "classes": CLASSES_THERAPEUTIQUES,
            "molecules": liste("SELECT ?x ?l WHERE { ?x mdc:nomMolecule ?l } ORDER BY ?l"),
            "effets": liste("SELECT ?x ?l WHERE { ?x mdc:nomEffet ?l } ORDER BY ?l"),
            "conditions": liste("SELECT ?x ?l WHERE { ?x mdc:nomCondition ?l } ORDER BY ?l"),
            "maladies": liste("SELECT ?x ?l WHERE { ?x mal:nom ?l } ORDER BY ?l"),
        }
