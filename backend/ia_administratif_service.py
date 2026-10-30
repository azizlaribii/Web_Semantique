# -*- coding: utf-8 -*-
"""
Module IA - Service administratif (sans LLM)
Question en francais -> analyse NLP -> intention + entites -> gabarit SPARQL -> execution.

Pipeline :
  1. Normalisation + tokenisation (spaCy fr_core_news_sm si disponible, sinon tokeniseur Python)
  2. Entites lues dans l'ontologie : patients, medecins, assurances, statuts, modes de paiement
  3. Correction des fautes de frappe (difflib)
  4. Delexicalisation : les entites sont remplacees par leur type (ent_pers, ent_ass, ent_sta, ent_mod)
  5. Intention : TF-IDF (mots + caracteres) + regression logistique (scikit-learn)
  6. Parametres : negation, superlatif, ordre
  7. Gabarit SPARQL de l'intention, rempli avec les entites
"""
import re, unicodedata, difflib, itertools
from typing import Dict, List, Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline, make_union

try:                                              # spaCy est optionnel (lemmes / POS)
    import spacy
    _NLP = spacy.load("fr_core_news_sm", disable=["ner", "parser"])
except Exception:
    spacy, _NLP = None, None

from administratif_service import PREFIXES, STATUTS_RDV, MODES_PAIEMENT

# ---------------------------------------------------------------- corpus
P, A, S, M = "ent_pers", "ent_ass", "ent_sta", "ent_mod"
CORPUS = {
 "rdv_liste": ["liste des rendez-vous", "montre tous les rendez-vous", "quels sont les rendez-vous", "affiche les rdv",
               "tous les rendez vous enregistres", "je veux voir le planning des rendez-vous", "combien de rendez-vous y a-t-il",
               "donne moi les rendez-vous", "agenda general de la clinique"],
 "rdv_patient": [f"rendez-vous de {P}", f"quels rendez-vous a {P}", f"quand est le rendez-vous de {P}", f"rdv du patient {P}",
                 f"le patient {P} a quels rendez-vous", f"montre les rendez-vous de {P}", f"prochain rdv de {P}",
                 f"{P} a-t-il un rendez-vous", f"consultations prevues pour {P}", f"quand {P} doit-il venir", f"planning du patient {P}"],
 "rdv_medecin": [f"agenda du docteur {P}", f"rendez-vous avec dr {P}", f"planning du medecin {P}", f"quels patients voit dr {P}",
                 f"rdv du dr {P}", f"emploi du temps du docteur {P}", f"qui consulte le docteur {P}", f"rendez-vous pris chez dr {P}",
                 f"consultations du medecin {P}", f"dr {P} est occupe quand", f"agenda de dr {P}"],
 "rdv_statut": [f"rendez-vous {S}", f"liste des rdv {S}", f"quels rendez-vous sont {S}", f"montre les rendez-vous {S}",
                f"les rdv {S}", f"affiche les rendez vous {S}", f"y a-t-il des rendez-vous {S}", f"consultations {S}",
                f"rendez-vous qui ne sont pas {S}", f"rdv non {S}"],
 "rdv_a_venir": ["rendez-vous a venir", "prochains rendez-vous", "quels sont les rendez-vous prevus", "rdv a venir cette semaine",
                 "les futurs rendez-vous", "rendez-vous en attente", "ce qui est planifie prochainement", "prochaines consultations"],
 "facture_liste": ["liste des factures", "montre toutes les factures", "quelles sont les factures", "affiche les factures",
                   "toutes les factures emises", "donne moi les factures", "combien de factures", "factures de la clinique"],
 "facture_impayee": ["factures impayees", "quelles factures restent a payer", "liste des impayes", "factures non reglees",
                     "qui doit encore de l'argent", "factures en attente de paiement", "reste a payer", "factures non payees",
                     "montre les factures non soldees", "factures sans paiement", "quels patients n'ont pas paye"],
 "facture_patient": [f"factures de {P}", f"combien doit {P}", f"facture du patient {P}", f"montre les factures de {P}",
                     f"quel est le montant a payer par {P}", f"{P} a-t-il paye sa facture", f"facturation de {P}",
                     f"situation financiere de {P}", f"que doit {P}"],
 "facture_max": ["facture la plus elevee", "quelle est la facture la plus chere", "plus grosse facture", "facture maximale",
                 "la facture au montant le plus eleve", "quelle consultation a coute le plus cher", "facture la plus importante"],
 "paiement_liste": ["liste des paiements", "montre les paiements", "quels paiements ont ete effectues", "tous les reglements",
                    "affiche les paiements enregistres", "historique des paiements", "qui a paye", "paiements recus"],
 "paiement_mode": [f"paiements par {M}", f"paiements en {M}", f"qui a paye par {M}", f"reglements effectues par {M}",
                   f"factures payees par {M}", f"montre les paiements par {M}", f"quels paiements en {M}", f"payes avec {M}"],
 "remboursement_liste": ["liste des remboursements", "montre les remboursements d'assurance", "quelles factures sont remboursees",
                         "remboursements effectues", "qui a ete rembourse", "affiche les remboursements", "factures remboursees par l'assurance",
                         "combien rembourse l'assurance"],
 "remboursement_assurance": [f"remboursements de {A}", f"qu'a rembourse {A}", f"factures remboursees par {A}",
                             f"montre les remboursements {A}", f"combien a verse {A}", f"remboursement via {A}", f"versements de {A}"],
 "patients_assures": [f"patients couverts par {A}", f"qui est assure chez {A}", f"assures de {A}", f"patients affilies a {A}",
                      f"quels patients ont {A}", "liste des patients assures", "patients avec assurance", "qui a une assurance",
                      f"adherents de {A}"],
 "patients_non_assures": ["patients sans assurance", "qui n'est pas assure", "patients non couverts", "patients qui n'ont aucune assurance",
                          "liste des non assures", "quels patients ne sont pas assures", "personnes sans couverture sociale"],
 "assurance_liste": ["liste des assurances", "quelles assurances sont disponibles", "taux de couverture des assurances",
                     "assurances partenaires", "montre les assurances", "quelles compagnies d'assurance", "quel est le taux de remboursement"],
 "dossier_patient": [f"dossier de {P}", f"montre le dossier du patient {P}", f"numero de dossier de {P}", f"dans quelle salle est {P}",
                     f"ou est hospitalise {P}", f"dossier medical de {P}", f"quand a ete ouvert le dossier de {P}", f"fiche administrative de {P}",
                     f"numero de salle de {P}"],
 "dossier_liste": ["liste des dossiers", "tous les dossiers patients", "quels dossiers sont actifs", "dossiers actifs", "montre les dossiers",
                   "dossiers archives", "combien de dossiers", "dossiers ouverts", "affiche les dossiers medicaux"],
 "chiffre_affaires": ["chiffre d'affaires", "combien a-t-on facture au total", "total des factures", "montant total encaisse",
                      "quelle est la somme des paiements", "recette totale de la clinique", "bilan financier", "combien d'argent a ete encaisse",
                      "somme facturee"],
 "medecin_plus_rdv": ["quel medecin a le plus de rendez-vous", "medecin le plus sollicite", "docteur avec le plus de consultations",
                      "nombre de rendez-vous par medecin", "qui est le medecin le plus demande", "repartition des rendez-vous par docteur",
                      "medecin le plus occupe"],
}
REQUIS = {"rdv_patient": "patient", "rdv_medecin": "medecin", "rdv_statut": "statut", "facture_patient": "patient",
          "paiement_mode": "mode", "remboursement_assurance": "assurance", "dossier_patient": "patient"}
STOP_NOMS = {"dr", "docteur", "patient", "pat", "ind", "stag", "ben", "de", "el", "le", "la", "des", "du", "mme", "mr", "stagiaire"}
STATUT_STEMS = {"annul": "Annule", "confirm": "Confirme", "planifi": "Planifie", "prevu": "Planifie", "termin": "Termine", "effectu": "Termine"}
MODE_STEMS = {"espec": "Especes", "cash": "Especes", "liquide": "Especes", "carte": "Carte", "cb": "Carte", "cheque": "Cheque", "virement": "Virement"}
NEGATIONS = {"sans", "pas", "aucun", "aucune", "non", "ni", "jamais"}


def norm(txt: str) -> str:
    t = unicodedata.normalize("NFD", txt.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


class IAAdministratifService:
    def __init__(self, service):
        self.svc = service
        self._train()
        self.refresh()

    # ---------------------------------------------------------- vocabulaire
    def refresh(self):
        """Relit les noms dans l'ontologie (un nouveau patient est reconnu sans reentrainement)."""
        opt = self.svc.options()
        self.alias = {}                                   # token -> {"patient": set(ids), "medecin": set(ids)}
        self.full = {}                                    # nom complet normalise -> (type, id)
        for typ, key in (("patient", "patients"), ("medecin", "medecins")):
            for p in opt[key]:
                names = [norm(p.get("nom") or ""), norm(p["id"].replace("_", " "))]
                for n in names:
                    if n: self.full[n] = (typ, p["id"])
                for tok in {t for n in names for t in n.split()}:
                    if len(tok) >= 3 and tok not in STOP_NOMS:
                        self.alias.setdefault(tok, {"patient": set(), "medecin": set()})[typ].add(p["id"])
        self.assurances = {}
        for a in self.svc.lister_assurances():
            for n in {norm(a["nom"]), norm(a["id"])}:
                for tok in n.split():
                    if tok not in ("assurances", "assurance"): self.assurances[tok] = a["id"]

    # ------------------------------------------------------------------ NLP
    def _tokens(self, question):
        if _NLP:
            return [{"texte": t.text, "lemme": t.lemma_, "pos": t.pos_, "norme": norm(t.text)} for t in _NLP(question) if not t.is_space]
        return [{"texte": w, "lemme": norm(w), "pos": "X", "norme": norm(w)} for w in re.findall(r"\w+|[^\w\s]", question)]

    def _mot_cle(self, w):
        """Mot-cle exact : assurance, statut de rendez-vous ou mode de paiement."""
        if w in self.assurances:
            return "ass", self.assurances[w]
        for stem, val in STATUT_STEMS.items():
            if w.startswith(stem): return "sta", val
        for stem, val in MODE_STEMS.items():
            if w.startswith(stem): return "mod", val
        return None

    def _entites(self, toks):
        ents, i = [], 0
        norms = [t["norme"] for t in toks]
        while i < len(norms):
            w = norms[i]
            if not w: i += 1; continue
            hit = None
            if w in self.alias:                                          # 1. nom exact
                hit = (self.alias[w], False)
            else:
                kw = self._mot_cle(w)                                    # 2. mot-cle exact (prioritaire sur la correction)
                if kw:
                    ents.append({"kind": kw[0], "debut": i, "fin": i + 1, "texte": toks[i]["texte"], "ids": [kw[1]], "corrige": False})
                    i += 1; continue
                if len(w) >= 3 and not all(t in self.known for t in w.split()) \
                        and w not in STOP_NOMS and not w.isdigit():      # 3. faute de frappe sur un nom
                    m = difflib.get_close_matches(w, list(self.alias), n=1, cutoff=0.75)
                    if m: hit = (self.alias[m[0]], True)
            if hit:
                cands = {k: set(v) for k, v in hit[0].items()}
                j = i + 1
                while j < len(norms) and norms[j] in self.alias:          # fusion "sami trabelsi"
                    nxt = self.alias[norms[j]]
                    inter = {k: cands[k] & nxt[k] for k in cands}
                    if not any(inter.values()): break
                    cands = inter; j += 1
                ents.append({"kind": "pers", "debut": i, "fin": j, "texte": " ".join(t["texte"] for t in toks[i:j]),
                             "cands": cands, "corrige": hit[1], "dr": i > 0 and norms[i - 1] in ("dr", "docteur", "medecin")})
                i = j; continue
            i += 1
        return ents

    @staticmethod
    def _masque(toks, ents):
        mark = {"pers": P, "sta": S, "mod": M, "ass": A}
        out, i = [], 0
        starts = {e["debut"]: e for e in ents}
        while i < len(toks):
            if i in starts:
                out.append(mark[starts[i]["kind"]]); i = starts[i]["fin"]
            else:
                if toks[i]["norme"]: out.append(toks[i]["norme"])
                i += 1
        return " ".join(out)

    # --------------------------------------------------------- classifieur
    def _train(self):
        X, y = [], []
        for intent, phrases in CORPUS.items():
            for ph in phrases:
                for variante in {ph, ph.replace("rendez-vous", "rendez vous").replace("-", " ")}:
                    X.append(norm(variante).replace("ent pers", P).replace("ent ass", A).replace("ent sta", S).replace("ent mod", M)); y.append(intent)
        self.labels = sorted(CORPUS)
        self.known = {t for x in X for t in x.split()}
        self.clf = make_pipeline(
            make_union(TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True),
                       TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True)),
            LogisticRegression(C=20, max_iter=2000))
        self.clf.fit(X, y)
        self.X, self.y = X, y
        self.training_size = len(X)

    def analyse(self, question: str) -> Dict[str, Any]:
        toks = self._tokens(question)
        ents = self._entites(toks)
        masked = self._masque(toks, ents)
        proba = self.clf.predict_proba([masked])[0]
        rang = sorted(zip(self.clf.classes_, proba), key=lambda x: -x[1])
        normes = [t["norme"] for t in toks]
        slots = {"negation": any(n in NEGATIONS for n in normes),
                 "superlatif": "plus" in normes and any(n in normes for n in ("eleve", "cher", "grand", "important", "sollicite", "occupe", "demande")) or "maximale" in normes,
                 "ordre": "DESC" if ("plus" in normes or "maximale" in normes) else ("ASC" if "moins" in normes else None)}
        return {"tokens": toks, "entites_brutes": ents, "texte_masque": masked, "classement": rang, "slots": slots}

    # ------------------------------------------------------------- SPARQL
    @staticmethod
    def _values(var, ids, ns="per"):
        return f"VALUES {var} {{ " + " ".join(f"{ns}:{i}" for i in ids) + " }"

    RDV = ("?r rdf:type adm:Rendez_vous ; adm:concernePatient ?p ; adm:avecMedecin ?m ; adm:dateRendezVous ?date ; adm:statutRDV ?statut .\n"
           "  OPTIONAL { ?p per:nom ?patient } OPTIONAL { ?m per:nom ?medecin } OPTIONAL { ?r adm:motifRendezVous ?motif }\n")
    RDV_SEL = "SELECT DISTINCT ?rendez_vous ?patient ?medecin ?date ?motif ?statut WHERE {\n  "
    RDV_BIND = "  BIND(STRAFTER(STR(?r), '#') AS ?rendez_vous)\n}"
    FAC = ("?f rdf:type adm:Facture ; adm:numeroFacture ?facture ; adm:montantTotalTND ?total ; adm:facturePourPatient ?p .\n"
           "  OPTIONAL { ?p per:nom ?patient }\n"
           "  OPTIONAL { SELECT ?f (SUM(?mp) AS ?paye) WHERE { ?pa adm:reglePourFacture ?f ; adm:montantPayeTND ?mp } GROUP BY ?f }\n"
           "  OPTIONAL { SELECT ?f (SUM(?mr) AS ?rembourse) WHERE { ?re adm:rembourseFacture ?f ; adm:montantRembourseTND ?mr } GROUP BY ?f }\n"
           "  BIND(?total - COALESCE(?paye, 0) - COALESCE(?rembourse, 0) AS ?reste)\n")
    FAC_SEL = "SELECT DISTINCT ?facture ?patient ?total ?paye ?rembourse ?reste WHERE {\n  "

    def _gabarit(self, intent, ents, slots):
        e = lambda k: next((x for x in ents if x["type"] == k), None)
        pat, med, ass, sta, mod = e("patient"), e("medecin"), e("assurance"), e("statut"), e("mode")
        if intent == "rdv_liste":
            return self.RDV_SEL + self.RDV + self.RDV_BIND + " ORDER BY ?date", "Tous les rendez-vous, du plus ancien au plus recent."
        if intent == "rdv_patient":
            return (self.RDV_SEL + self._values("?p", pat["ids"]) + "\n  " + self.RDV + self.RDV_BIND + " ORDER BY ?date",
                    f"Rendez-vous du patient {pat['texte']} (adm:concernePatient).")
        if intent == "rdv_medecin":
            return (self.RDV_SEL + self._values("?m", med["ids"]) + "\n  " + self.RDV + self.RDV_BIND + " ORDER BY ?date",
                    f"Agenda du medecin {med['texte']} (adm:avecMedecin).")
        if intent == "rdv_statut":
            op = "!=" if slots["negation"] else "="
            return (self.RDV_SEL + self.RDV + f"  FILTER(?statut {op} \"{sta['ids'][0]}\")\n" + self.RDV_BIND + " ORDER BY ?date",
                    f"Rendez-vous dont le statut {'n est pas' if slots['negation'] else 'est'} {sta['ids'][0]} (negation -> FILTER !=)." if slots["negation"]
                    else f"Rendez-vous au statut {sta['ids'][0]} (classe definie inferee : RendezVous{sta['ids'][0]}).")
        if intent == "rdv_a_venir":
            return (self.RDV_SEL + self.RDV + "  FILTER(?statut = \"Planifie\" || ?statut = \"Confirme\")\n" + self.RDV_BIND + " ORDER BY ?date",
                    "Rendez-vous planifies ou confirmes (pas encore termines ni annules).")
        if intent == "facture_liste":
            return self.FAC_SEL + self.FAC + "} ORDER BY ?facture", "Toutes les factures avec montants payes, rembourses et reste a payer."
        if intent == "facture_impayee":
            return (self.FAC_SEL + self.FAC + "  FILTER(?reste > 0)\n} ORDER BY DESC(?reste)",
                    "Factures dont total - paiements - remboursements > 0.")
        if intent == "facture_patient":
            return (self.FAC_SEL + self._values("?p", pat["ids"]) + "\n  " + self.FAC + "} ORDER BY ?facture",
                    f"Factures du patient {pat['texte']} (adm:facturePourPatient).")
        if intent == "facture_max":
            return (self.FAC_SEL + self.FAC + "} ORDER BY DESC(?total) LIMIT 1",
                    "Superlatif -> ORDER BY DESC(montantTotalTND) LIMIT 1.")
        if intent in ("paiement_liste", "paiement_mode"):
            flt = f"  FILTER(?mode = \"{mod['ids'][0]}\")\n" if intent == "paiement_mode" else ""
            return ("SELECT DISTINCT ?paiement ?facture ?patient ?montant ?mode ?date WHERE {\n"
                    "  ?pa rdf:type adm:Paiement ; adm:reglePourFacture ?f ; adm:montantPayeTND ?montant ; adm:modePaiement ?mode ; adm:datePaiement ?date .\n"
                    "  ?f adm:numeroFacture ?facture ; adm:facturePourPatient ?p . OPTIONAL { ?p per:nom ?patient }\n"
                    f"{flt}  BIND(STRAFTER(STR(?pa), '#') AS ?paiement)\n}} ORDER BY ?date",
                    f"Paiements effectues par {mod['ids'][0]}." if mod else "Tous les paiements enregistres.")
        if intent in ("remboursement_liste", "remboursement_assurance"):
            flt = self._values("?a", ass["ids"], "adm") + "\n  " if intent == "remboursement_assurance" else ""
            return ("SELECT DISTINCT ?remboursement ?facture ?patient ?assurance ?montant ?date WHERE {\n  " + flt +
                    "?re rdf:type adm:Rembourcement_Assurance ; adm:rembourseFacture ?f ; adm:verseePar ?a ; adm:montantRembourseTND ?montant ; adm:dateRemboursement ?date .\n"
                    "  ?a adm:nomAssurance ?assurance . ?f adm:numeroFacture ?facture ; adm:facturePourPatient ?p . OPTIONAL { ?p per:nom ?patient }\n"
                    "  BIND(STRAFTER(STR(?re), '#') AS ?remboursement)\n} ORDER BY ?date",
                    f"Remboursements verses par {ass['texte']}." if ass else "Remboursements d'assurance (classe FactureRembourseeParAssurance).")
        if intent == "patients_assures":
            flt = self._values("?a", ass["ids"], "adm") + "\n  " if ass else ""
            return ("SELECT DISTINCT ?patient ?assurance ?taux_couverture WHERE {\n  " + flt +
                    "?p adm:estCouvertPar ?a . ?a adm:nomAssurance ?assurance ; adm:tauxCouverture ?taux_couverture . OPTIONAL { ?p per:nom ?patient }\n} ORDER BY ?assurance",
                    "Patients couverts (classe definie PatientAssure : estCouvertPar some Assurance).")
        if intent == "patients_non_assures":
            return ("SELECT DISTINCT ?patient ?dossier WHERE {\n  ?d adm:concernePatient ?p ; adm:numeroDossierAdm ?dossier . FILTER NOT EXISTS { ?r rdf:type adm:Rendez_vous . FILTER(?r = ?d) }\n"
                    "  FILTER NOT EXISTS { ?p adm:estCouvertPar ?a }\n  OPTIONAL { ?p per:nom ?patient }\n}",
                    "Negation -> FILTER NOT EXISTS { ?patient adm:estCouvertPar ?assurance }.")
        if intent == "assurance_liste":
            return ("SELECT ?assurance ?taux_couverture WHERE { ?a rdf:type adm:Assurance ; adm:nomAssurance ?assurance ; adm:tauxCouverture ?taux_couverture } ORDER BY ?assurance",
                    "Assurances partenaires et leur taux de couverture.")
        if intent == "dossier_patient":
            return ("SELECT DISTINCT ?dossier ?patient ?salle ?ouverture ?statut WHERE {\n  " + self._values("?p", pat["ids"]) + "\n"
                    "  ?d adm:concernePatient ?p ; adm:numeroDossierAdm ?dossier . FILTER NOT EXISTS { ?d rdf:type adm:Rendez_vous }\n"
                    "  OPTIONAL { ?p per:nom ?patient } OPTIONAL { ?d adm:numeroSalle ?salle } OPTIONAL { ?d adm:dateOuverture ?ouverture } OPTIONAL { ?d adm:statutDossier ?statut }\n}",
                    f"Dossier administratif du patient {pat['texte']}.")
        if intent == "dossier_liste":
            statut = "Archive" if any(t in ("archive", "archives") for t in [x["norme"] for x in self._last_toks]) else ("Actif" if slots["negation"] is False and any(x["norme"] in ("actif", "actifs", "ouverts") for x in self._last_toks) else None)
            flt = f"  FILTER(?statut = \"{statut}\")\n" if statut else ""
            return ("SELECT DISTINCT ?dossier ?patient ?salle ?ouverture ?statut WHERE {\n"
                    "  ?d adm:concernePatient ?p ; adm:numeroDossierAdm ?dossier ; adm:statutDossier ?statut . FILTER NOT EXISTS { ?d rdf:type adm:Rendez_vous }\n"
                    f"  OPTIONAL {{ ?p per:nom ?patient }} OPTIONAL {{ ?d adm:numeroSalle ?salle }} OPTIONAL {{ ?d adm:dateOuverture ?ouverture }}\n{flt}}} ORDER BY ?dossier",
                    f"Dossiers au statut {statut}." if statut else "Tous les dossiers patients.")
        if intent == "chiffre_affaires":
            return ("SELECT (SUM(?total) AS ?total_facture) (SUM(COALESCE(?paye, 0)) AS ?total_encaisse) WHERE {\n"
                    "  ?f rdf:type adm:Facture ; adm:montantTotalTND ?total .\n"
                    "  OPTIONAL { SELECT ?f (SUM(?mp) AS ?paye) WHERE { ?pa adm:reglePourFacture ?f ; adm:montantPayeTND ?mp } GROUP BY ?f }\n}",
                    "Agregation : SUM des montants factures et encaisses (TND).")
        if intent == "medecin_plus_rdv":
            lim = " LIMIT 1" if slots["superlatif"] else ""
            return ("SELECT ?medecin (COUNT(DISTINCT ?r) AS ?nb_rendez_vous) WHERE {\n"
                    "  ?r rdf:type adm:Rendez_vous ; adm:avecMedecin ?m . ?m per:nom ?medecin\n} GROUP BY ?medecin ORDER BY DESC(?nb_rendez_vous)" + lim,
                    "Agregation COUNT par medecin" + (", superlatif -> LIMIT 1." if lim else "."))
        raise KeyError(intent)

    # ----------------------------------------------------------- orchestration
    def answer_question(self, question: str) -> Dict[str, Any]:
        a = self.analyse(question)
        self._last_toks = a["tokens"]
        # 1. intention la plus probable dont les entites obligatoires sont presentes
        choix = None
        for intent, p in a["classement"]:
            ents = self._resoudre(a["entites_brutes"], REQUIS.get(intent))
            besoin = REQUIS.get(intent)
            if besoin and not any(x["type"] == besoin for x in ents):
                continue
            choix = (intent, float(p), ents); break
        intent, conf, ents = choix or ("rdv_liste", 0.0, self._resoudre(a["entites_brutes"], None))
        slots = a["slots"]
        # negation sur assures -> intention dediee
        if intent == "patients_assures" and slots["negation"] and not any(x["type"] == "assurance" for x in ents):
            intent = "patients_non_assures"
        sparql, explication = self._gabarit(intent, ents, slots)
        rows = self.svc.select(sparql)
        donnees, vus = [], set()
        for r in rows:
            cle = tuple(r.values())
            if cle not in vus:
                vus.add(cle); donnees.append({k: self._clean(v) for k, v in r.items()})
        return {
            "intention": intent, "explication": explication, "sparql": PREFIXES + sparql, "count": len(donnees), "donnees": donnees,
            "reponse": self._phrase(intent, donnees),
            "nlp": {"tokens": [{k: t[k] for k in ("texte", "lemme", "pos", "norme")} for t in a["tokens"]],
                    "entites": [{"type": x["type"].upper(), "texte": x["texte"], "ids": x["ids"], "corrige": x["corrige"]} for x in ents],
                    "texte_masque": a["texte_masque"],
                    "intentions": [{"intention": i, "confiance": round(float(p), 3)} for i, p in a["classement"][:5]],
                    "intention_retenue": {"intention": intent, "confiance": round(conf, 3)},
                    "slots": slots, "outils": self.outils()}}

    def _resoudre(self, brutes, besoin):
        out = []
        for e in brutes:
            if e["kind"] == "pers":
                c = e["cands"]
                typ = "medecin" if (besoin == "medecin" and c["medecin"]) else \
                      "patient" if (besoin == "patient" and c["patient"]) else \
                      "medecin" if (e["dr"] and c["medecin"]) else ("patient" if c["patient"] else "medecin")
                out.append({"type": typ, "texte": e["texte"], "ids": sorted(c[typ]), "corrige": e["corrige"]})
            else:
                out.append({"type": {"sta": "statut", "mod": "mode", "ass": "assurance"}[e["kind"]], "texte": e["texte"],
                            "ids": e["ids"], "corrige": e["corrige"]})
        return out

    @staticmethod
    def _clean(v):
        if v is None: return ""
        return v.replace("T00:00:00", "").replace("T", " ") if re.match(r"^\d{4}-\d\d-\d\d", v) else v

    @staticmethod
    def _phrase(intent, d):
        if not d: return "Aucun resultat dans l'ontologie pour cette question."
        if intent == "chiffre_affaires":
            r = d[0]; return f"Total facture : {r.get('total_facture')} TND, dont {r.get('total_encaisse')} TND encaisses."
        if intent in ("facture_max", "medecin_plus_rdv"): return f"Reponse : {list(d[0].values())[0]}" + (f" ({list(d[0].values())[-1]})" if len(d[0]) > 1 else "")
        return f"{len(d)} resultat(s) trouve(s) dans l'ontologie."

    def outils(self):
        import sklearn
        return {"spaCy": (f"{spacy.__version__} - fr_core_news_sm" if _NLP else "tokeniseur Python (spaCy absent)"),
                "scikit-learn": f"{sklearn.__version__} - TF-IDF + LogisticRegression ({self.training_size} phrases, {len(self.labels)} intentions)",
                "difflib": "correction des fautes de frappe sur les noms"}
