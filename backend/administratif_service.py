# -*- coding: utf-8 -*-
"""
Service RDFLib - Module Service administratif
Dossiers patients, rendez-vous, facturation, paiements, remboursements, assurances.
Charge ontologie_administratif.owl + ontologie_personne.owl (liens Patient / Medecin).
"""
import os, re, shutil, threading, datetime
from decimal import Decimal
from rdflib import Graph, Namespace, Literal, URIRef, RDF
from rdflib.namespace import XSD

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADM_FILE = os.path.join(BASE_DIR, "ontologie_administratif.owl")
ADM_ORIG = os.path.join(BASE_DIR, "ontologie_administratif.original.owl")
PER_FILE = os.path.join(BASE_DIR, "ontologie_personne.owl")

ADM = Namespace("http://example.org/ontologie-administratif#")
PER = Namespace("http://example.org/ontologie-medicale#")
PREFIXES = ("PREFIX adm: <http://example.org/ontologie-administratif#>\n"
            "PREFIX per: <http://example.org/ontologie-medicale#>\n"
            "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n"
            "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
            "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n")

STATUTS_RDV = ["Planifie", "Confirme", "Annule", "Termine"]
MODES_PAIEMENT = ["Especes", "Carte", "Cheque", "Virement"]
CLASSES_INFEREES = ["RendezVousAnnule", "RendezVousConfirme", "DossierActif",
                    "FacturePayee", "FactureRembourseeParAssurance", "PatientAssure"]

# Regles SPARQL Update : reproduisent les classes definies HermiT apres chaque ecriture.
REGLES = [
    "INSERT { ?x rdf:type adm:RendezVousAnnule }  WHERE { ?x rdf:type adm:Rendez_vous ; adm:statutRDV 'Annule' }",
    "INSERT { ?x rdf:type adm:RendezVousConfirme } WHERE { ?x rdf:type adm:Rendez_vous ; adm:statutRDV 'Confirme' }",
    "INSERT { ?x rdf:type adm:DossierActif }      WHERE { ?x rdf:type ?c ; adm:statutDossier 'Actif' . FILTER(?c IN (adm:Dossier_patient, adm:Dossier_medicale)) }",
    "INSERT { ?x rdf:type adm:FacturePayee }      WHERE { ?x rdf:type adm:Facture ; adm:estReglePar ?p }",
    "INSERT { ?x rdf:type adm:FactureRembourseeParAssurance } WHERE { ?x rdf:type adm:Facture ; adm:estRembourseePar ?r }",
    "INSERT { ?x rdf:type adm:PatientAssure }     WHERE { ?x adm:estCouvertPar ?a }",
]


def _loc(term):
    return str(term).split("#")[-1]


def _lit_dec(v):
    return Literal(str(Decimal(str(v))), datatype=XSD.decimal)


def _lit_dt(v):
    s = str(v).strip().replace(" ", "T")
    if len(s) == 10:
        s += "T00:00:00"
    elif len(s) == 16:
        s += ":00"
    datetime.datetime.fromisoformat(s)          # leve ValueError si invalide
    return Literal(s, datatype=XSD.dateTime)


class ServiceAdministratif:
    def __init__(self):
        self._lock = threading.RLock()
        if not os.path.exists(ADM_ORIG) and os.path.exists(ADM_FILE):
            shutil.copyfile(ADM_FILE, ADM_ORIG)
        self.g = Graph()
        self._charger()

    # ------------------------------------------------------------ chargement
    def _charger(self):
        with self._lock:
            g = Graph()
            g.bind("adm", ADM); g.bind("per", PER)
            g.parse(PER_FILE, format="xml")
            g.parse(ADM_FILE, format="xml")
            self.g = g
            self.appliquer_regles()

    def appliquer_regles(self):
        with self._lock:
            for c in CLASSES_INFEREES:
                self.g.update(PREFIXES + f"DELETE WHERE {{ ?x rdf:type adm:{c} }}")
            for r in REGLES:
                self.g.update(PREFIXES + r)

    def sauvegarder(self):
        """Enregistre l'ontologie administrative (assertions seulement, sans types inferes)."""
        out = Graph()
        out.bind("adm", ADM); out.bind("per", PER)
        inferes = {ADM[c] for c in CLASSES_INFEREES}
        for s, p, o in self.g:
            if p == RDF.type and o in inferes:
                continue
            if str(s).startswith(str(ADM)) or str(p).startswith(str(ADM)):
                out.add((s, p, o))
        out.serialize(destination=ADM_FILE, format="xml")

    def reset(self):
        with self._lock:
            if os.path.exists(ADM_ORIG):
                shutil.copyfile(ADM_ORIG, ADM_FILE)
            self._charger()
        return {"operation": "reset", "message": "Ontologie administrative restauree."}

    # ----------------------------------------------------------------- SPARQL
    def select(self, query):
        with self._lock:
            res = self.g.query(query if query.lstrip().upper().startswith("PREFIX") else PREFIXES + query)
            return [{str(v): (str(r[v]) if r[v] is not None else None) for v in res.vars} for r in res]

    def sparql_json(self, query):
        """Format SPARQL 1.1 Query Results JSON (SELECT / ASK)."""
        with self._lock:
            res = self.g.query(PREFIXES + query)
            if res.type == "ASK":
                return {"head": {}, "boolean": bool(res.askAnswer)}
            return {"head": {"vars": [str(v) for v in res.vars]},
                    "results": {"bindings": [
                        {str(v): {"type": "uri" if isinstance(r[v], URIRef) else "literal", "value": str(r[v])}
                         for v in res.vars if r[v] is not None} for r in res]}}

    def _nom(self, ident):
        rows = self.select(f"SELECT ?n WHERE {{ per:{ident} per:nom ?n }} LIMIT 1")
        return rows[0]["n"] if rows else ident

    def existe(self, ident):
        return (PER[ident], None, None) in self.g or (ADM[ident], None, None) in self.g

    # ------------------------------------------------------------------ LECTURE
    def lister_dossiers(self):
        rows = self.select("""SELECT ?id ?patient ?pnom ?num ?salle ?date ?statut ?type WHERE {
            ?d rdf:type ?t ; adm:numeroDossierAdm ?num ; adm:concernePatient ?p .
            FILTER(?t IN (adm:Dossier_patient, adm:Dossier_medicale))
            FILTER NOT EXISTS { ?d rdf:type adm:Rendez_vous }
            OPTIONAL { ?p per:nom ?pnom } OPTIONAL { ?d adm:numeroSalle ?salle }
            OPTIONAL { ?d adm:dateOuverture ?date } OPTIONAL { ?d adm:statutDossier ?statut }
            BIND(STRAFTER(STR(?d), "#") AS ?id) BIND(STRAFTER(STR(?p), "#") AS ?patient)
            BIND(STRAFTER(STR(?t), "#") AS ?type) } ORDER BY ?num""")
        vus, out = set(), []
        for r in rows:
            if r["id"] not in vus:
                vus.add(r["id"]); out.append(r)
        return out

    def lister_rdv(self, statut=None):
        rows = self.select("""SELECT ?id ?patient ?pnom ?medecin ?mnom ?date ?motif ?duree ?statut ?facture WHERE {
            ?r rdf:type adm:Rendez_vous ; adm:concernePatient ?p ; adm:avecMedecin ?m ;
               adm:dateRendezVous ?date ; adm:statutRDV ?statut .
            OPTIONAL { ?p per:nom ?pnom } OPTIONAL { ?m per:nom ?mnom }
            OPTIONAL { ?r adm:motifRendezVous ?motif } OPTIONAL { ?r adm:dureeMinutes ?duree }
            OPTIONAL { ?f adm:concerneRendezVous ?r BIND(STRAFTER(STR(?f), "#") AS ?facture) }
            BIND(STRAFTER(STR(?r), "#") AS ?id) BIND(STRAFTER(STR(?p), "#") AS ?patient)
            BIND(STRAFTER(STR(?m), "#") AS ?medecin) } ORDER BY ?date""")
        vus, out = set(), []
        for r in rows:
            if r["id"] in vus or (statut and r["statut"] != statut):
                continue
            vus.add(r["id"]); out.append(r)
        return out

    def lister_factures(self):
        factures = self.select("""SELECT ?id ?numero ?rdv ?patient ?pnom ?total ?date WHERE {
            ?f rdf:type adm:Facture ; adm:numeroFacture ?numero ; adm:montantTotalTND ?total ;
               adm:facturePourPatient ?p . OPTIONAL { ?p per:nom ?pnom }
            OPTIONAL { ?f adm:dateFacture ?date } OPTIONAL { ?f adm:concerneRendezVous ?r }
            BIND(STRAFTER(STR(?f), "#") AS ?id) BIND(STRAFTER(STR(?p), "#") AS ?patient)
            BIND(STRAFTER(STR(?r), "#") AS ?rdv) } ORDER BY ?numero""")
        factures = list({f["id"]: f for f in factures}.values())      # dedoublonnage (plusieurs 'nom')
        paye, remb = {}, {}
        for r in self.select("SELECT ?f ?m WHERE { ?p adm:reglePourFacture ?fx ; adm:montantPayeTND ?m BIND(STRAFTER(STR(?fx),'#') AS ?f) }"):
            paye[r["f"]] = paye.get(r["f"], Decimal(0)) + Decimal(r["m"])
        for r in self.select("SELECT ?f ?m WHERE { ?p adm:rembourseFacture ?fx ; adm:montantRembourseTND ?m BIND(STRAFTER(STR(?fx),'#') AS ?f) }"):
            remb[r["f"]] = remb.get(r["f"], Decimal(0)) + Decimal(r["m"])
        out = []
        for f in factures:
            tot = Decimal(f["total"]); p = paye.get(f["id"], Decimal(0)); rb = remb.get(f["id"], Decimal(0))
            reste = max(tot - p - rb, Decimal(0))
            f.update(total=float(tot), paye=float(p), rembourse=float(rb), reste=float(reste),
                     statut="Soldee" if reste == 0 else ("Partielle" if p + rb > 0 else "Impayee"))
            out.append(f)
        return out

    def lister_assurances(self):
        return self.select("""SELECT ?id ?nom ?taux (COUNT(?p) AS ?assures) WHERE {
            ?a rdf:type adm:Assurance ; adm:nomAssurance ?nom ; adm:tauxCouverture ?taux .
            OPTIONAL { ?p adm:estCouvertPar ?a } BIND(STRAFTER(STR(?a), "#") AS ?id)
            } GROUP BY ?id ?nom ?taux ORDER BY ?nom""")

    def options(self):
        pats = self.select("SELECT DISTINCT ?id ?nom WHERE { ?p rdf:type ?t . FILTER(?t IN (per:Patient, per:PatientAdulte, per:PatientEnfant)) OPTIONAL { ?p per:nom ?nom } BIND(STRAFTER(STR(?p),'#') AS ?id) } ORDER BY ?nom")
        meds = self.select("SELECT DISTINCT ?id ?nom WHERE { ?p rdf:type ?t . FILTER(?t IN (per:Medecin, per:MedecinGeneraliste, per:MedecinSpecialiste, per:Cardiologue)) OPTIONAL { ?p per:nom ?nom } BIND(STRAFTER(STR(?p),'#') AS ?id) } ORDER BY ?nom")
        uniq = lambda L: list({x["id"]: x for x in L}.values())
        return {"patients": uniq(pats), "medecins": uniq(meds), "statuts": STATUTS_RDV, "modes": MODES_PAIEMENT}

    def resume(self):
        rdv, fac = self.lister_rdv(), self.lister_factures()
        return {"dossiers": len(self.lister_dossiers()), "rendez_vous": len(rdv),
                "rdv_a_venir": sum(1 for r in rdv if r["statut"] in ("Planifie", "Confirme")),
                "rdv_annules": sum(1 for r in rdv if r["statut"] == "Annule"),
                "factures": len(fac), "factures_impayees": sum(1 for f in fac if f["statut"] != "Soldee"),
                "chiffre_affaires_tnd": round(sum(f["total"] for f in fac), 2),
                "encaisse_tnd": round(sum(f["paye"] for f in fac), 2),
                "reste_a_payer_tnd": round(sum(f["reste"] for f in fac), 2),
                "assurances": len(self.lister_assurances())}

    def graphe(self):
        nodes, links, seen = [], [], set()
        def node(i, label, group):
            if i not in seen:
                seen.add(i); nodes.append({"id": i, "label": label, "group": group})
        for r in self.lister_rdv():
            node(r["id"], r["id"], "Rendez_vous"); node(r["patient"], r["pnom"] or r["patient"], "Patient")
            node(r["medecin"], r["mnom"] or r["medecin"], "Medecin")
            links += [{"source": r["id"], "target": r["patient"], "label": "concernePatient"},
                      {"source": r["id"], "target": r["medecin"], "label": "avecMedecin"}]
        for f in self.lister_factures():
            node(f["id"], f["numero"], "Facture"); links.append({"source": f["id"], "target": f["patient"], "label": "facturePourPatient"})
            if f["rdv"]: links.append({"source": f["id"], "target": f["rdv"], "label": "concerneRendezVous"})
        for a in self.lister_assurances():
            node(a["id"], a["nom"], "Assurance")
        for r in self.select("SELECT ?p ?a WHERE { ?px adm:estCouvertPar ?ax BIND(STRAFTER(STR(?px),'#') AS ?p) BIND(STRAFTER(STR(?ax),'#') AS ?a) }"):
            node(r["p"], self._nom(r["p"]), "Patient"); links.append({"source": r["p"], "target": r["a"], "label": "estCouvertPar"})
        return {"nodes": nodes, "links": links}

    # ------------------------------------------------------------ CRUD : RDV
    def _prochain_id(self, prefix):
        nums = [int(m.group(1)) for r in self.select(f"SELECT ?i WHERE {{ ?x rdf:type ?t BIND(STRAFTER(STR(?x),'#') AS ?i) FILTER(STRSTARTS(STRAFTER(STR(?x),'#'), '{prefix}_')) }}")
                if (m := re.match(rf"{prefix}_(\d+)$", r["i"]))]
        return f"{prefix}_{(max(nums) + 1) if nums else 1:02d}"

    def _verifier_rdv(self, patient, medecin, date_lit, ignorer=None):
        if not self.existe(patient): raise ValueError(f"Patient inconnu : {patient}")
        if not self.existe(medecin): raise ValueError(f"Medecin inconnu : {medecin}")
        for r in self.lister_rdv():                       # regle metier : pas de double reservation
            if r["medecin"] == medecin and r["id"] != ignorer and r["statut"] != "Annule" \
               and r["date"].replace(" ", "T")[:16] == str(date_lit)[:16]:
                raise ValueError(f"Conflit : {self._nom(medecin)} a deja le rendez-vous {r['id']} a ce creneau.")

    def creer_rdv(self, d):
        with self._lock:
            date = _lit_dt(d["date"]); statut = d.get("statut", "Planifie")
            if statut not in STATUTS_RDV: raise ValueError("Statut invalide")
            self._verifier_rdv(d["patient"], d["medecin"], date)
            rid = self._prochain_id("RDV")
            dossier = self.select(f"SELECT ?n WHERE {{ ?x adm:concernePatient per:{d['patient']} ; adm:numeroDossierAdm ?n }} LIMIT 1")
            q = PREFIXES + f"""INSERT DATA {{
  adm:{rid} rdf:type adm:Rendez_vous ;
      adm:concernePatient per:{d['patient']} ; adm:avecMedecin per:{d['medecin']} ;
      adm:dateRendezVous {date.n3()} ; adm:statutRDV "{statut}" ;
      adm:motifRendezVous {Literal(d.get('motif', '')).n3()} ; adm:dureeMinutes {int(d.get('duree', 20))} .
}}"""
            self.g.update(q); self.appliquer_regles(); self.sauvegarder()
            return {"operation": "create", "id": rid, "sparql_update": q.split("\n", 5)[5]}

    def modifier_rdv(self, rid, d):
        with self._lock:
            if (ADM[rid], RDF.type, ADM.Rendez_vous) not in self.g: raise KeyError(rid)
            actuel = next(r for r in self.lister_rdv() if r["id"] == rid)
            champs = {}
            if "date" in d:    champs["dateRendezVous"] = _lit_dt(d["date"]).n3()
            if "motif" in d:   champs["motifRendezVous"] = Literal(d["motif"]).n3()
            if "duree" in d:   champs["dureeMinutes"] = str(int(d["duree"]))
            if "statut" in d:
                if d["statut"] not in STATUTS_RDV: raise ValueError("Statut invalide")
                champs["statutRDV"] = f'"{d["statut"]}"'
            if "medecin" in d: champs["avecMedecin"] = f"per:{d['medecin']}"
            if "patient" in d: champs["concernePatient"] = f"per:{d['patient']}"
            if not champs: raise ValueError("Aucun champ a modifier")
            nv_med = d.get("medecin", actuel["medecin"]); nv_date = champs.get("dateRendezVous", None) or _lit_dt(actuel["date"]).n3()
            if d.get("statut", actuel["statut"]) != "Annule":
                self._verifier_rdv(d.get("patient", actuel["patient"]), nv_med, nv_date.split('"')[1], ignorer=rid)
            dele = " ".join(f"?r adm:{p} ?o{i} ." for i, p in enumerate(champs))
            ins = " ".join(f"?r adm:{p} {v} ." for p, v in champs.items())
            opt = " ".join(f"OPTIONAL {{ ?r adm:{p} ?o{i} }}" for i, p in enumerate(champs))
            q = PREFIXES + f"DELETE {{ {dele} }}\nINSERT {{ {ins} }}\nWHERE {{ BIND(adm:{rid} AS ?r) {opt} }}"
            self.g.update(q); self.appliquer_regles(); self.sauvegarder()
            return {"operation": "update", "id": rid, "sparql_update": q.split("\n", 5)[5]}

    def supprimer_rdv(self, rid):
        with self._lock:
            if (ADM[rid], RDF.type, ADM.Rendez_vous) not in self.g: raise KeyError(rid)
            if any(f["rdv"] == rid for f in self.lister_factures()):
                raise ValueError("Suppression refusee : une facture est liee a ce rendez-vous.")
            q = PREFIXES + f"DELETE WHERE {{ adm:{rid} ?p ?o }}"
            self.g.update(q); self.appliquer_regles(); self.sauvegarder()
            return {"operation": "delete", "id": rid, "sparql_update": q.split("\n", 5)[5]}

    # ---------------------------------------------- Facturation / paiements
    def creer_facture(self, d):
        with self._lock:
            rdv = next((r for r in self.lister_rdv() if r["id"] == d["rdv"]), None)
            if not rdv: raise KeyError(d["rdv"])
            if rdv["facture"]: raise ValueError(f"Ce rendez-vous a deja la facture {rdv['facture']}.")
            montant = Decimal(str(d["montant"]))
            if montant <= 0: raise ValueError("Montant invalide")
            fid = self._prochain_id("Facture"); num = f"FAC-{datetime.date.today().year}-{int(fid.split('_')[1]):03d}"
            q = PREFIXES + f"""INSERT DATA {{
  adm:{fid} rdf:type adm:Facture ; adm:numeroFacture "{num}" ; adm:montantTotalTND {_lit_dec(montant).n3()} ;
      adm:dateFacture "{datetime.date.today()}T00:00:00"^^xsd:dateTime ;
      adm:concerneRendezVous adm:{rdv['id']} ; adm:facturePourPatient per:{rdv['patient']} .
}}"""
            self.g.update(q); self.appliquer_regles(); self.sauvegarder()
            return {"operation": "create", "id": fid, "sparql_update": q.split("\n", 5)[5]}

    def enregistrer_paiement(self, d):
        with self._lock:
            fac = next((f for f in self.lister_factures() if f["id"] == d["facture"]), None)
            if not fac: raise KeyError(d["facture"])
            mode = d.get("mode", "Especes")
            if mode not in MODES_PAIEMENT: raise ValueError("Mode de paiement invalide")
            montant = Decimal(str(d["montant"]))
            if montant <= 0 or montant > Decimal(str(fac["reste"])):
                raise ValueError(f"Montant invalide (reste a payer : {fac['reste']} TND)")
            pid = self._prochain_id("Paiement")
            q = PREFIXES + f"""INSERT DATA {{
  adm:{pid} rdf:type adm:Paiement ; adm:montantPayeTND {_lit_dec(montant).n3()} ; adm:modePaiement "{mode}" ;
      adm:datePaiement "{datetime.date.today()}T00:00:00"^^xsd:dateTime ; adm:reglePourFacture adm:{fac['id']} .
  adm:{fac['id']} adm:estReglePar adm:{pid} .
}}"""
            self.g.update(q); self.appliquer_regles(); self.sauvegarder()
            return {"operation": "create", "id": pid, "sparql_update": q.split("\n", 5)[5]}


_instance = None
def get_service():
    global _instance
    if _instance is None:
        _instance = ServiceAdministratif()
    return _instance
