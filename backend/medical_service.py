
# -*- coding: utf-8 -*-
"""
Service RDFLib - Module Service médical.

Gestion :
- Consultations
- Opérations
- Ordonnances
- Patients et médecins depuis ontologie_personne.owl

Les deux ontologies sont chargées séparément :
- ontologie_medicale.owl
- ontologie_personne.owl

Les personnes sont recherchées dans les deux graphes.
Les modifications médicales sont sauvegardées uniquement
dans ontologie_medicale.owl.
"""

import os
import re
import shutil
import threading
import uuid

from rdflib import (
    Graph,
    Namespace,
    URIRef,
    Literal,
    RDF,
    RDFS,
    OWL,
    XSD,
)


# ============================================================
# CHEMINS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

OWL_PATH = os.path.join(
    BASE_DIR,
    "ontologie_medicale.owl"
)

PERSON_PATH = os.path.join(
    BASE_DIR,
    "ontologie_personne.owl"
)

BACKUP_PATH = os.path.join(
    BASE_DIR,
    "ontologie_medicale.original.owl"
)


# ============================================================
# NAMESPACE
# ============================================================

# Dans ton projet, les personnes utilisent également
# le namespace de l'ontologie médicale.
NS = Namespace(
    "http://example.org/ontologie-medicale#"
)


# ============================================================
# TYPES MÉDICAUX
# ============================================================

KINDS = {
    "Consultation": {
        "sub": [
            "ConsultationGenerale",
            "ConsultationSpecialisee",
            "ConsultationUrgence",
            "ConsultationControle",
        ],
        "date": "dateConsultation",
    },

    "Opération": {
        "sub": [
            "OperationChirurgicale",
            "OperationUrgente",
            "OperationEsthetique",
        ],
        "date": "date_de_l’opération",
    },

    "Ordonnance": {
        "sub": [
            "OrdonnanceSimple",
            "OrdonnanceSpecialisee",
            "OrdonnanceRenouvelable",
        ],
        "date": "dateOrdonnance",
    },
}


# Sous-classes de personnes connues dans ton autre service.
# La recherche utilise également les relations rdfs:subClassOf.
PERSON_CLASSES = {
    "Patient": [
        "Patient",
        "PatientAdulte",
        "PatientEnfant",
    ],

    "Medecin": [
        "Medecin",
        "MedecinGeneraliste",
        "MedecinSpecialiste",
        "Cardiologue",
    ],
}


# ============================================================
# SERVICE MÉDICAL
# ============================================================

class MedicalService:

    def __init__(self):

        self.lock = threading.RLock()

        # Graphe médical : consultations, opérations,
        # ordonnances et relations médicales.
        self.graph = Graph()

        # Graphe des personnes : patients et médecins.
        self.people_graph = Graph()

        self.load()

        # Sauvegarde initiale de l'ontologie médicale.
        if not os.path.exists(BACKUP_PATH):
            shutil.copy2(
                OWL_PATH,
                BACKUP_PATH
            )

    # ========================================================
    # CHARGEMENT DES ONTOLOGIES
    # ========================================================

    def load(self):

        with self.lock:

            if not os.path.exists(OWL_PATH):
                raise FileNotFoundError(
                    f"Ontologie médicale introuvable : {OWL_PATH}"
                )

            self.graph = Graph()
            self.people_graph = Graph()

            self.graph.bind("med", NS)
            self.people_graph.bind("med", NS)

            # Chargement de l'ontologie médicale.
            self.graph.parse(
                OWL_PATH,
                format="xml"
            )

            print(
                "[MedicalService] Ontologie médicale chargée :",
                OWL_PATH
            )

            # Chargement séparé de l'ontologie des personnes.
            if os.path.exists(PERSON_PATH):

                self.people_graph.parse(
                    PERSON_PATH,
                    format="xml"
                )

                print(
                    "[MedicalService] Ontologie des personnes chargée :",
                    PERSON_PATH
                )

            else:

                print(
                    "[MedicalService] ATTENTION : ontologie des personnes absente :",
                    PERSON_PATH
                )

            print(
                "[MedicalService] Triplets médicaux :",
                len(self.graph)
            )

            print(
                "[MedicalService] Triplets personnes :",
                len(self.people_graph)
            )

            print(
                "[MedicalService] Patients trouvés :",
                len(self._people("Patient"))
            )

            print(
                "[MedicalService] Médecins trouvés :",
                len(self._people("Medecin"))
            )

    # ========================================================
    # GRAPHE COMBINÉ POUR LA LECTURE
    # ========================================================

    def _combined_graph(self):
        """
        Retourne une copie réunissant les deux ontologies.

        Cette méthode sert à rechercher les personnes et leurs
        classes sans fusionner les fichiers sur le disque.
        """

        combined = Graph()

        for triple in self.people_graph:
            combined.add(triple)

        for triple in self.graph:
            combined.add(triple)

        combined.bind("med", NS)

        return combined

    # ========================================================
    # SAUVEGARDE
    # ========================================================

    def save(self):
        """
        Sauvegarde uniquement le graphe médical.

        ontologie_personne.owl n'est jamais écrasée ici.
        """

        with self.lock:

            self.graph.serialize(
                destination=OWL_PATH,
                format="xml"
            )

            print(
                "[MedicalService] Ontologie médicale sauvegardée :",
                OWL_PATH
            )

    # ========================================================
    # UTILITAIRES
    # ========================================================

    @staticmethod
    def local(value):

        return (
            str(value)
            .split("#")[-1]
            .split("/")[-1]
        )

    # ========================================================
    # RÉCUPÉRATION DES SOUS-CLASSES
    # ========================================================

    def _subclasses_of(self, graph, class_name):
        """
        Recherche une classe et toutes ses sous-classes
        directes ou indirectes.
        """

        root = NS[class_name]

        classes = {root}
        pending = [root]

        while pending:

            parent = pending.pop()

            for child in graph.subjects(
                RDFS.subClassOf,
                parent
            ):

                if child not in classes:

                    classes.add(child)
                    pending.append(child)

        return classes

    # ========================================================
    # PATIENTS ET MÉDECINS
    # ========================================================

    def _people(self, kind):
        """
        Recherche les personnes dans les deux ontologies.

        Accepte :
        - les individus explicitement typés Patient / Medecin ;
        - les individus typés avec une sous-classe ;
        - les individus ayant un nom ou un label.
        """

        with self.lock:

            if kind not in PERSON_CLASSES:
                return []

            graph = self._combined_graph()

            classes = set()

            # Classes connues explicitement.
            for class_name in PERSON_CLASSES[kind]:

                classes.update(
                    self._subclasses_of(
                        graph,
                        class_name
                    )
                )

            people = []
            seen = set()

            for class_uri in classes:

                for uri in graph.subjects(
                    RDF.type,
                    class_uri
                ):

                    if uri in seen:
                        continue

                    # Ne pas retourner les classes elles-mêmes.
                    if (
                        (uri, RDF.type, OWL.Class) in graph
                        or (uri, RDF.type, RDFS.Class) in graph
                    ):
                        continue

                    is_individual = (
                        (uri, RDF.type, OWL.NamedIndividual)
                        in graph
                    )

                    name = (
                        graph.value(uri, NS.nom)
                        or graph.value(uri, RDFS.label)
                    )

                    # Un individu doit être déclaré ou posséder
                    # un nom/label.
                    if not is_individual and name is None:
                        continue

                    if name is None:
                        name = self.local(uri)

                    seen.add(uri)

                    people.append({
                        "id": str(uri),
                        "nom": str(name),
                    })

            return sorted(
                people,
                key=lambda person: person["nom"].lower()
            )

    # ========================================================
    # OPTIONS DES FORMULAIRES
    # ========================================================

    def options(self):

        with self.lock:

            patients = self._people("Patient")
            medecins = self._people("Medecin")

            print(
                "[MedicalService] Options patients :",
                len(patients)
            )

            print(
                "[MedicalService] Options médecins :",
                len(medecins)
            )

            return {
                "patients": patients,
                "medecins": medecins,
                "sousTypes": {
                    kind: values["sub"]
                    for kind, values in KINDS.items()
                },
            }

    # ========================================================
    # DÉTECTION DES TYPES MÉDICAUX
    # ========================================================

    def _is_kind(self, uri, kind):

        if kind not in KINDS:
            return False

        classes = self._subclasses_of(
            self.graph,
            kind
        )

        return any(
            (uri, RDF.type, cls) in self.graph
            for cls in classes
        )

    # ========================================================
    # LISTE DES ÉLÉMENTS MÉDICAUX
    # ========================================================

    def records(self, kind=None):

        with self.lock:

            output = []

            for current_kind in KINDS:

                if kind and current_kind != kind:
                    continue

                classes = self._subclasses_of(
                    self.graph,
                    current_kind
                )

                seen = set()

                for class_uri in classes:

                    for uri in self.graph.subjects(
                        RDF.type,
                        class_uri
                    ):

                        if uri in seen:
                            continue

                        if (
                            (uri, RDF.type, OWL.NamedIndividual)
                            not in self.graph
                        ):
                            continue

                        seen.add(uri)

                        properties = {}

                        for predicate, obj in self.graph.predicate_objects(uri):

                            if predicate in (
                                RDF.type,
                                RDFS.label
                            ):
                                continue

                            properties[self.local(predicate)] = (
                                self.local(obj)
                                if isinstance(obj, URIRef)
                                else str(obj)
                            )

                        label = (
                            self.graph.value(uri, RDFS.label)
                            or self.graph.value(uri, NS.nom)
                            or self.local(uri)
                        )

                        subtype = ""

                        for candidate in KINDS[current_kind]["sub"]:

                            if (
                                uri,
                                RDF.type,
                                NS[candidate]
                            ) in self.graph:

                                subtype = candidate
                                break

                        output.append({
                            "id": str(uri),
                            "uri": self.local(uri),
                            "type": current_kind,
                            "sousType": subtype,
                            "label": str(label),
                            "properties": properties,
                        })

            return sorted(
                output,
                key=lambda row: (
                    row["type"],
                    row["label"].lower()
                )
            )

    # ========================================================
    # STATISTIQUES
    # ========================================================

    def summary(self):

        rows = self.records()

        return {
            kind: sum(
                1
                for row in rows
                if row["type"] == kind
            )
            for kind in KINDS
        }

    # ========================================================
    # CRÉATION
    # ========================================================

    def create(self, data):

        kind = (data.get("type") or "").strip()

        if kind not in KINDS:
            raise ValueError("Type médical invalide.")

        label = (data.get("label") or "").strip()

        if not label:
            raise ValueError("Le libellé est obligatoire.")

        subtype = data.get("sousType") or ""

        if subtype and subtype not in KINDS[kind]["sub"]:
            raise ValueError("Sous-type invalide.")

        with self.lock:

            slug = re.sub(
                r"[^A-Za-z0-9_-]+",
                "_",
                label
            ).strip("_")[:35] or "Element"

            kind_slug = (
                kind
                .replace("é", "e")
                .replace("ô", "o")
            )

            uri = NS[
                f"{kind_slug}_{slug}_{uuid.uuid4().hex[:6]}"
            ]

            self.graph.add((
                uri,
                RDF.type,
                OWL.NamedIndividual
            ))

            self.graph.add((
                uri,
                RDF.type,
                NS[kind]
            ))

            if subtype:

                self.graph.add((
                    uri,
                    RDF.type,
                    NS[subtype]
                ))

            self.graph.add((
                uri,
                RDFS.label,
                Literal(label, lang="fr")
            ))

            # Date
            date = data.get("date")

            if date:

                predicate = NS[KINDS[kind]["date"]]

                self.graph.add((
                    uri,
                    predicate,
                    Literal(date, datatype=XSD.date)
                ))

            # Tarif consultation
            if (
                kind == "Consultation"
                and data.get("tarif") not in (None, "")
            ):

                self.graph.add((
                    uri,
                    NS.tarif,
                    Literal(
                        float(data["tarif"]),
                        datatype=XSD.decimal
                    )
                ))

            # Durée et urgence opération
            if kind == "Opération":

                if data.get("duree") not in (None, ""):

                    self.graph.add((
                        uri,
                        NS["durée"],
                        Literal(
                            int(data["duree"]),
                            datatype=XSD.integer
                        )
                    ))

                if data.get("urgent") is not None:

                    self.graph.add((
                        uri,
                        NS.est_urgent,
                        Literal(
                            bool(data["urgent"]),
                            datatype=XSD.boolean
                        )
                    ))

            # Validité ordonnance
            if (
                kind == "Ordonnance"
                and data.get("validite") not in (None, "")
            ):

                self.graph.add((
                    uri,
                    NS["durée_de_validité"],
                    Literal(
                        int(data["validite"]),
                        datatype=XSD.integer
                    )
                ))

            # Relations patient et médecin.
            patient = data.get("patient")
            medecin = data.get("medecin")

            if patient:

                patient_uri = URIRef(patient)

                predicate = (
                    NS.estDestineeA
                    if kind == "Ordonnance"
                    else NS.concerne
                )

                self.graph.add((
                    uri,
                    predicate,
                    patient_uri
                ))

            if medecin:

                medecin_uri = URIRef(medecin)

                predicate = (
                    NS.redige
                    if kind == "Ordonnance"
                    else NS.realise
                )

                self.graph.add((
                    medecin_uri,
                    predicate,
                    uri
                ))

            self.save()

            return {
                "ok": True,
                "id": str(uri),
                "label": label,
                "type": kind,
                "operation": "INSERT DATA",
            }

    # ========================================================
    # MODIFICATION
    # ========================================================

    def update(self, uri, data):

        with self.lock:

            subject = URIRef(uri)

            row = next(
                (
                    item
                    for item in self.records()
                    if item["id"] == uri
                ),
                None
            )

            if not row:
                raise KeyError(uri)

            label = (
                data.get("label") or row["label"]
            ).strip()

            self.graph.remove((
                subject,
                RDFS.label,
                None
            ))

            self.graph.add((
                subject,
                RDFS.label,
                Literal(label, lang="fr")
            ))

            kind = row["type"]

            date = data.get("date")

            if date:

                predicate = NS[KINDS[kind]["date"]]

                self.graph.remove((
                    subject,
                    predicate,
                    None
                ))

                self.graph.add((
                    subject,
                    predicate,
                    Literal(date, datatype=XSD.date)
                ))

            if (
                kind == "Consultation"
                and data.get("tarif") not in (None, "")
            ):

                self.graph.remove((
                    subject,
                    NS.tarif,
                    None
                ))

                self.graph.add((
                    subject,
                    NS.tarif,
                    Literal(
                        float(data["tarif"]),
                        datatype=XSD.decimal
                    )
                ))

            if (
                kind == "Opération"
                and data.get("duree") not in (None, "")
            ):

                self.graph.remove((
                    subject,
                    NS["durée"],
                    None
                ))

                self.graph.add((
                    subject,
                    NS["durée"],
                    Literal(
                        int(data["duree"]),
                        datatype=XSD.integer
                    )
                ))

            self.save()

            return {
                "ok": True,
                "id": uri,
                "operation": "DELETE/INSERT WHERE",
            }

    # ========================================================
    # SUPPRESSION
    # ========================================================

    def delete(self, uri):

        with self.lock:

            subject = URIRef(uri)

            if not any(
                row["id"] == uri
                for row in self.records()
            ):
                raise KeyError(uri)

            self.graph.remove((
                subject,
                None,
                None
            ))

            self.graph.remove((
                None,
                None,
                subject
            ))

            self.save()

            return {
                "ok": True,
                "id": uri,
                "operation": "DELETE WHERE",
            }

    # ========================================================
    # RÉINITIALISATION
    # ========================================================

    def reset(self):

        with self.lock:

            if not os.path.exists(BACKUP_PATH):
                raise FileNotFoundError(
                    f"Sauvegarde introuvable : {BACKUP_PATH}"
                )

            shutil.copy2(
                BACKUP_PATH,
                OWL_PATH
            )

            self.load()

            return {
                "ok": True
            }

    # ========================================================
    # QUESTIONS EN LANGAGE NATUREL
    # ========================================================

    def ask(self, question):

        low = question.lower()

        if any(
            word in low
            for word in [
                "operation",
                "opération",
                "chirurg",
            ]
        ):

            kind = "Opération"

        elif any(
            word in low
            for word in [
                "ordonnance",
                "prescription",
            ]
        ):

            kind = "Ordonnance"

        else:

            kind = "Consultation"

        rows = self.records(kind)

        count_query = any(
            word in low
            for word in [
                "combien",
                "nombre",
                "total",
            ]
        )

        sparql = f"""
PREFIX med: <{NS}>
PREFIX rdfs: <{RDFS}>

SELECT ?element ?label
WHERE {{
    ?element a med:{kind} .
    OPTIONAL {{
        ?element rdfs:label ?label .
    }}
}}
"""

        if count_query:

            data = [{
                "type": kind,
                "nombre": len(rows),
            }]

            intention = (
                "nombre_"
                + kind.lower()
            )

        else:

            data = [
                {
                    "element": row["label"],
                    **row["properties"],
                }
                for row in rows
            ]

            intention = (
                "liste_"
                + kind.lower()
            )

        return {
            "intention": intention,

            "explication": (
                f"{len(rows)} élément(s) de type {kind} "
                "trouvé(s) dans l'ontologie médicale."
            ),

            "sparql": sparql,

            "donnees": data,

            "count": len(rows),

            "nlp": {
                "question": question,

                "entites": [{
                    "type": "CLASSE_MEDICALE",
                    "valeur": kind,
                }],

                "intention_retenue": {
                    "intention": (
                        "nombre"
                        if count_query
                        else "liste"
                    ),
                    "confiance": 0.99,
                },
            },
        }
