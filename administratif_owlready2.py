# -*- coding: utf-8 -*-
"""
Manipulation avec Owlready2 - Ontologie Medicale (Module Service administratif)
Domaine : Gestion administrative hospitaliere
Concept : dossiers patients, rendez-vous, facturation, paiements et remboursements d'assurance.

pip install owlready2
Genere : ontologie_administratif.owl (ouvrable dans Protege)
Lie au module Personne via ontologie_personne.owl (Patient, Medecin, Consultation).
"""
import os, sys, datetime, subprocess

try:
    import owlready2  # noqa: F401
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "owlready2", "-q"], check=True)

from owlready2 import (get_ontology, Thing, ObjectProperty, DataProperty,
                       FunctionalProperty, AllDisjoint, AllDifferent,
                       sync_reasoner_hermit)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
PERSONNE_OWL = os.path.join(OUT_DIR, "ontologie_personne.owl")
OUT_OWL = os.path.join(OUT_DIR, "ontologie_administratif.owl")

print("=" * 65)
print("ETAPE 1 : Creation de l'ontologie -- Module Service administratif")
print("=" * 65)
IRI = "http://example.org/ontologie-administratif#"
onto = get_ontology(IRI)
pers = get_ontology("file://" + PERSONNE_OWL.replace("\\", "/")).load()
print(f"[OK] {IRI}\n[OK] Module Personne charge pour les liens croises\n")

# ---------------------------------------------------------------- CLASSES
print("ETAPE 2 : Classes (hierarchie conforme a Protege)")
with onto:
    class Service_administratif(Thing): pass
    class Dossier_patient(Service_administratif): pass
    class Dossier_medicale(Dossier_patient): pass
    class Rendez_vous(Dossier_patient): pass
    class Facturation(Service_administratif): pass
    class Facture(Facturation): pass
    class Paiement(Facturation): pass
    class Rembourcement_Assurance(Facturation): pass   # orthographe du TTL global conservee
    class Assurance(Thing): pass

    AllDisjoint([Dossier_patient, Facturation, Assurance])
    AllDisjoint([Dossier_medicale, Rendez_vous])
    AllDisjoint([Facture, Paiement, Rembourcement_Assurance])
print("  Service_administratif > Dossier_patient > {Dossier_medicale, Rendez_vous}")
print("  Service_administratif > Facturation > {Facture, Paiement, Rembourcement_Assurance}")
print("  Assurance (nouvelle classe) ; disjonctions OK\n")

# ------------------------------------------------------- OBJECT PROPERTIES
print("ETAPE 3 : Object Properties")
with onto:
    class concernePatient(ObjectProperty, FunctionalProperty):
        domain = [Dossier_patient]; range = [pers.Patient]
    class facturePourPatient(ObjectProperty, FunctionalProperty):
        domain = [Facture]; range = [pers.Patient]
    class aPourDossier(ObjectProperty):
        domain = [pers.Patient]; range = [Dossier_patient]
        inverse_property = concernePatient
    class avecMedecin(ObjectProperty, FunctionalProperty):
        domain = [Rendez_vous]; range = [pers.Medecin]
    class contientConsultation(ObjectProperty):
        domain = [Dossier_medicale]; range = [pers.Consultation]
    class concerneRendezVous(ObjectProperty, FunctionalProperty):
        domain = [Facture]; range = [Rendez_vous]
    class estReglePar(ObjectProperty):
        domain = [Facture]; range = [Paiement]
    class reglePourFacture(ObjectProperty, FunctionalProperty):
        domain = [Paiement]; range = [Facture]
        inverse_property = estReglePar
    class estRembourseePar(ObjectProperty):
        domain = [Facture]; range = [Rembourcement_Assurance]
    class rembourseFacture(ObjectProperty, FunctionalProperty):
        domain = [Rembourcement_Assurance]; range = [Facture]
        inverse_property = estRembourseePar
    class verseePar(ObjectProperty, FunctionalProperty):
        domain = [Rembourcement_Assurance]; range = [Assurance]
    class estCouvertPar(ObjectProperty):
        domain = [pers.Patient]; range = [Assurance]
print("  concernePatient/aPourDossier, facturePourPatient, avecMedecin, contientConsultation,")
print("  concerneRendezVous, estReglePar/reglePourFacture, estRembourseePar/rembourseFacture,")
print("  verseePar, estCouvertPar\n")

# --------------------------------------------------------- DATA PROPERTIES
print("ETAPE 4 : Data Properties")
with onto:
    class numeroDossierAdm(DataProperty, FunctionalProperty):
        domain = [Dossier_patient]; range = [str]
    class dateOuverture(DataProperty, FunctionalProperty):
        domain = [Dossier_patient]; range = [datetime.datetime]
    class numeroSalle(DataProperty, FunctionalProperty):
        domain = [Dossier_patient]; range = [int]
    class statutDossier(DataProperty, FunctionalProperty):
        domain = [Dossier_patient]; range = [str]
    class dateRendezVous(DataProperty, FunctionalProperty):
        domain = [Rendez_vous]; range = [datetime.datetime]
    class motifRendezVous(DataProperty, FunctionalProperty):
        domain = [Rendez_vous]; range = [str]
    class dureeMinutes(DataProperty, FunctionalProperty):
        domain = [Rendez_vous]; range = [int]
    class statutRDV(DataProperty, FunctionalProperty):
        domain = [Rendez_vous]; range = [str]       # Planifie | Confirme | Annule | Termine
    class numeroFacture(DataProperty, FunctionalProperty):
        domain = [Facture]; range = [str]
    class dateFacture(DataProperty, FunctionalProperty):
        domain = [Facture]; range = [datetime.datetime]
    class montantTotalTND(DataProperty, FunctionalProperty):
        domain = [Facture]; range = [float]
    class montantPayeTND(DataProperty, FunctionalProperty):
        domain = [Paiement]; range = [float]
    class datePaiement(DataProperty, FunctionalProperty):
        domain = [Paiement]; range = [datetime.datetime]
    class modePaiement(DataProperty, FunctionalProperty):
        domain = [Paiement]; range = [str]          # Especes | Carte | Cheque | Virement
    class montantRembourseTND(DataProperty, FunctionalProperty):
        domain = [Rembourcement_Assurance]; range = [float]
    class dateRemboursement(DataProperty, FunctionalProperty):
        domain = [Rembourcement_Assurance]; range = [datetime.datetime]
    class nomAssurance(DataProperty, FunctionalProperty):
        domain = [Assurance]; range = [str]
    class tauxCouverture(DataProperty, FunctionalProperty):
        domain = [Assurance]; range = [float]
print("  16 proprietes de donnees (dates, montants TND, statuts, modes de paiement)\n")

# --------------------------------------------- CLASSES DEFINIES (HermiT)
print("ETAPE 5 : Classes definies (equivalentes) inferees par HermiT")
with onto:
    class RendezVousAnnule(Rendez_vous):
        equivalent_to = [Rendez_vous & statutRDV.value("Annule")]
    class RendezVousConfirme(Rendez_vous):
        equivalent_to = [Rendez_vous & statutRDV.value("Confirme")]
    class DossierActif(Dossier_patient):
        equivalent_to = [Dossier_patient & statutDossier.value("Actif")]
    class FacturePayee(Facture):
        equivalent_to = [Facture & estReglePar.some(Paiement)]
    class FactureRembourseeParAssurance(Facture):
        equivalent_to = [Facture & estRembourseePar.some(Rembourcement_Assurance)]
    class PatientAssure(pers.Patient):
        equivalent_to = [pers.Patient & estCouvertPar.some(Assurance)]
print("  RendezVousAnnule, RendezVousConfirme, DossierActif, FacturePayee,")
print("  FactureRembourseeParAssurance, PatientAssure\n")

# ------------------------------------------------------------- INDIVIDUS
print("ETAPE 6 : Individus")
D = lambda y, m, d: datetime.datetime(y, m, d); DT = datetime.datetime
with onto:
    cnam = Assurance("CNAM");  cnam.nomAssurance = "CNAM";  cnam.tauxCouverture = 0.70
    star = Assurance("STAR");  star.nomAssurance = "STAR Assurances"; star.tauxCouverture = 0.80
    gat  = Assurance("GAT");   gat.nomAssurance = "GAT Assurances";   gat.tauxCouverture = 0.60

    pers.Sami.estCouvertPar = [cnam]
    pers.Patient_Ahmed.estCouvertPar = [star]
    pers.Patient_Leila.estCouvertPar = [cnam]
    pers.Patient_Omar.estCouvertPar = [gat]

    # (id, patient, salle, date ouverture, statut)
    dossiers = [
        ("Dossier_Sami",   pers.Sami,           101, D(2026, 1, 12), "Actif"),
        ("Dossier_Ahmed",  pers.Patient_Ahmed,  102, D(2026, 2, 3),  "Actif"),
        ("Dossier_Leila",  pers.Patient_Leila,  103, D(2026, 2, 20), "Actif"),
        ("Dossier_Omar",   pers.Patient_Omar,   104, D(2026, 3, 8),  "Archive"),
        ("Dossier_Sara",   pers.Patient_Sara,   105, D(2026, 4, 1),  "Actif"),
        ("Dossier_Amina",  pers.Amina,          106, D(2026, 5, 15), "Actif"),
    ]
    dos = {}
    for i, (nid, pat, salle, d, st) in enumerate(dossiers, 1):
        cls = Dossier_medicale if nid in ("Dossier_Sami", "Dossier_Ahmed", "Dossier_Amina") else Dossier_patient
        x = cls(nid)
        x.numeroDossierAdm = f"DOS-2026-{i:03d}"; x.concernePatient = pat
        x.numeroSalle = salle; x.dateOuverture = d; x.statutDossier = st
        dos[nid] = x
    dos["Dossier_Sami"].contientConsultation = [pers.Consultation_1]

    # (id, patient, medecin, date-heure, motif, duree, statut)
    rdvs = [
        ("RDV_01", pers.Sami,          pers.Dr_Ahmed,    DT(2026, 11, 3, 9, 0),   "Controle grippe",       20, "Confirme"),
        ("RDV_02", pers.Patient_Ahmed, pers.Dr_Karim,    DT(2026, 11, 3, 10, 30), "Suivi hypertension",    30, "Planifie"),
        ("RDV_03", pers.Patient_Leila, pers.Dr_Fatima,   DT(2026, 11, 4, 14, 0),  "Douleurs abdominales",  30, "Confirme"),
        ("RDV_04", pers.Patient_Omar,  pers.Dr_Ahmed,    DT(2026, 10, 20, 11, 0), "Consultation generale", 20, "Annule"),
        ("RDV_05", pers.Patient_Sara,  pers.Dr_Sophie_Martin, DT(2026, 11, 5, 8, 30), "Bilan cardiaque",   45, "Planifie"),
        ("RDV_06", pers.Amina,         pers.Dr_Fatima,   DT(2026, 10, 25, 16, 0), "Fievre de l'enfant",    20, "Termine"),
        ("RDV_07", pers.Sami,          pers.Dr_Ahmed,    DT(2026, 10, 15, 9, 30), "Premiere consultation", 30, "Termine"),
        ("RDV_08", pers.Patient_Ahmed, pers.Dr_Aziz_Laribi, DT(2026, 10, 28, 15, 0), "Renouvellement ordonnance", 15, "Termine"),
    ]
    rdv = {}
    for nid, pat, med, dt, motif, dur, st in rdvs:
        x = Rendez_vous(nid)            # Rendez_vous est sous-classe de Dossier_patient
        x.concernePatient = pat
        x.avecMedecin = med; x.dateRendezVous = dt
        x.motifRendezVous = motif; x.dureeMinutes = dur; x.statutRDV = st
        x.numeroDossierAdm = dos[{"Sami": "Dossier_Sami", "Patient_Ahmed": "Dossier_Ahmed",
                                  "Patient_Leila": "Dossier_Leila", "Patient_Omar": "Dossier_Omar",
                                  "Patient_Sara": "Dossier_Sara", "Amina": "Dossier_Amina"}[pat.name]].numeroDossierAdm
        rdv[nid] = x

    # (id, numero, rdv, montant, date)
    factures = [
        ("Facture_01", "FAC-2026-001", "RDV_07",  60.0, D(2026, 10, 15)),
        ("Facture_02", "FAC-2026-002", "RDV_06",  45.0, D(2026, 10, 25)),
        ("Facture_03", "FAC-2026-003", "RDV_08",  35.0, D(2026, 10, 28)),
        ("Facture_04", "FAC-2026-004", "RDV_04",  50.0, D(2026, 10, 20)),
        ("Facture_05", "FAC-2026-005", "RDV_01", 120.0, D(2026, 11, 3)),
        ("Facture_06", "FAC-2026-006", "RDV_05", 180.0, D(2026, 11, 5)),
    ]
    fac = {}
    for nid, num, r, mt, d in factures:
        x = Facture(nid)
        x.numeroFacture = num; x.montantTotalTND = mt; x.dateFacture = d
        x.concerneRendezVous = rdv[r]; x.facturePourPatient = rdv[r].concernePatient
        fac[nid] = x

    # (id, facture, montant, date, mode)
    paiements = [
        ("Paiement_01", "Facture_01", 60.0, D(2026, 10, 15), "Especes"),
        ("Paiement_02", "Facture_02", 45.0, D(2026, 10, 25), "Carte"),
        ("Paiement_03", "Facture_03", 35.0, D(2026, 10, 28), "Cheque"),
        ("Paiement_04", "Facture_05", 40.0, D(2026, 11, 3),  "Carte"),
    ]
    for nid, f, mt, d, mode in paiements:
        x = Paiement(nid)
        x.montantPayeTND = mt; x.datePaiement = d; x.modePaiement = mode; x.reglePourFacture = fac[f]

    # (id, facture, assurance, montant, date)
    rembs = [
        ("Remboursement_01", "Facture_01", cnam, 42.0, D(2026, 10, 30)),
        ("Remboursement_02", "Facture_03", star, 28.0, D(2026, 10, 31)),
    ]
    for nid, f, a, mt, d in rembs:
        x = Rembourcement_Assurance(nid)
        x.montantRembourseTND = mt; x.dateRemboursement = d
        x.rembourseFacture = fac[f]; x.verseePar = a

    AllDifferent(list(dos.values()) + list(rdv.values()) + list(fac.values()))
print(f"  {len(dos)} dossiers, {len(rdv)} rendez-vous, {len(fac)} factures, 4 paiements, 2 remboursements, 3 assurances\n")

# Sauvegarde AVANT raisonnement : le fichier ne contient que les assertions ;
# dans Protege, lancer HermiT fait apparaitre les classes inferees.
onto.save(file=OUT_OWL, format="rdfxml")
print(f"[OK] Ontologie enregistree : {OUT_OWL}\n")

# --------------------------------------------------------------- HERMIT
print("ETAPE 7 : Raisonneur HermiT")
try:
    with onto:
        sync_reasoner_hermit([onto], infer_property_values=True)
    for c in (RendezVousAnnule, RendezVousConfirme, DossierActif, FacturePayee,
              FactureRembourseeParAssurance, PatientAssure):
        print(f"  {c.name:32s} -> {sorted(i.name for i in c.instances())}")
except Exception as e:                                   # Java absent, etc.
    print(f"  [!] HermiT non execute ({type(e).__name__}: {e}).")

