"""
Manipulation avec Owlready2 - Ontologie Medicale (Classe Personne)
pip install owlready2
"""

import sys, io, subprocess, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ======================================================================
# ETAPE 0 : Installation de owlready2
# ======================================================================
print("=" * 60)
print("ETAPE 0 : Verification / Installation owlready2")
print("=" * 60)
subprocess.run([sys.executable, "-m", "pip", "install", "owlready2", "-q"], check=True)
print("[OK] owlready2 installe.\n")

from owlready2 import (
    get_ontology, Thing, World,
    ObjectProperty, DataProperty,
    FunctionalProperty, InverseFunctionalProperty,
    TransitiveProperty, SymmetricProperty,
    AllDisjoint, AllDifferent,
    sync_reasoner_hermit, sync_reasoner_pellet,
)
import datetime

# ======================================================================
# ETAPE 1 : Creer l'ontologie
# ======================================================================
print("=" * 60)
print("ETAPE 1 : Creation de l'ontologie OWL")
print("=" * 60)

IRI  = "http://example.org/ontologie-medicale#"
onto = get_ontology(IRI)
print(f"[OK] Ontologie creee avec IRI : {IRI}\n")

# ======================================================================
# ETAPE 2 : Definir les classes et sous-classes
# ======================================================================
print("=" * 60)
print("ETAPE 2 : Definition des classes et sous-classes")
print("=" * 60)

with onto:

    class Personne(Thing):
        pass

    class Role(Personne):
        pass

    class Medecin(Role):
        pass

    class MedecinGeneraliste(Medecin):
        pass

    class MedecinSpecialiste(Medecin):
        pass

    class Cardiologue(MedecinSpecialiste):
        pass

    class Patient(Role):
        pass

    class PatientAdulte(Patient):
        pass

    class PatientEnfant(Patient):
        pass

    class Stagiaire(Role):
        pass

    class Stuff_Medicale(Role):
        pass

    class Infirmier(Stuff_Medicale):
        pass

    class Maladie(Thing):
        pass

    class MaladieInfectieuse(Maladie):
        pass

    class Symptome(Thing):
        pass

    class Service(Thing):
        pass

    class Ordonnance(Thing):
        pass

    class Consultation(Thing):
        pass

print(f"  Classes definies :")
for cls in [Personne, Role, Medecin, MedecinGeneraliste, MedecinSpecialiste,
            Cardiologue, Patient, PatientAdulte, PatientEnfant,
            Stagiaire, Stuff_Medicale, Infirmier]:
    parent = cls.__bases__[0].name if cls.__bases__ else "-"
    print(f"    {cls.name:25s} sous-classe de -> {parent}")
print()

# ======================================================================
# ETAPE 3 : Disjonctions (owl:AllDisjointClasses)
# ======================================================================
print("=" * 60)
print("ETAPE 3 : Disjonctions (owl:AllDisjointClasses)")
print("=" * 60)

with onto:
    AllDisjoint([Medecin, Patient])
    AllDisjoint([Medecin, Patient, Stagiaire, Stuff_Medicale])
    AllDisjoint([MedecinGeneraliste, MedecinSpecialiste])
    AllDisjoint([PatientAdulte, PatientEnfant])

print("  [OK] Medecin  DISJOINT AVEC  Patient")
print("  [OK] MedecinGeneraliste  DISJOINT AVEC  MedecinSpecialiste")
print("  [OK] PatientAdulte  DISJOINT AVEC  PatientEnfant")
print("  [OK] Medecin, Patient, Stagiaire, Stuff_Medicale tous disjoints\n")

# ======================================================================
# ETAPE 4 : Object Properties
# ======================================================================
print("=" * 60)
print("ETAPE 4 : Object Properties")
print("=" * 60)

with onto:

    class joueLeRoleDe(ObjectProperty):
        domain = [Personne]
        range  = [Role]

    class estSoignePar(ObjectProperty):
        domain = [Patient]
        range  = [Medecin]

    class soigne(ObjectProperty):
        inverse_property = estSoignePar
        domain = [Medecin]
        range  = [Patient]

    class connait(SymmetricProperty, ObjectProperty):
        domain = [Personne]
        range  = [Personne]

    class aConsulte(TransitiveProperty, ObjectProperty):
        domain = [Personne]
        range  = [Personne]

    class presente(ObjectProperty):
        domain = [Patient]
        range  = [Symptome]

    class realise(ObjectProperty):
        domain = [Medecin]
        range  = [Consultation]

    class redige(ObjectProperty):
        domain = [Medecin]
        range  = [Ordonnance]

    class diagnostique(ObjectProperty):
        domain = [Medecin]
        range  = [Maladie]

    class appartientA(ObjectProperty):
        domain = [Medecin]
        range  = [Service]

    class estPrisEnChargePar(ObjectProperty):
        domain = [Patient]
        range  = [Service]

print("  [OK] joueLeRoleDe       Personne -> Role")
print("  [OK] estSoignePar       Patient  -> Medecin  [inverse: soigne]")
print("  [OK] soigne             Medecin  -> Patient  [inverse: estSoignePar]")
print("  [OK] connait            Personne -> Personne [SYMETRIQUE]")
print("  [OK] aConsulte          Personne -> Personne [TRANSITIVE]")
print("  [OK] presente           Patient  -> Symptome")
print("  [OK] realise            Medecin  -> Consultation")
print("  [OK] redige             Medecin  -> Ordonnance")
print("  [OK] diagnostique       Medecin  -> Maladie")
print("  [OK] appartientA        Medecin  -> Service")
print("  [OK] estPrisEnChargePar Patient  -> Service\n")

# ======================================================================
# ETAPE 5 : Data Properties
# ======================================================================
print("=" * 60)
print("ETAPE 5 : Data Properties")
print("=" * 60)

with onto:

    class nom(DataProperty, FunctionalProperty):
        domain = [Personne]; range = [str]

    class prenom(DataProperty, FunctionalProperty):
        domain = [Personne]; range = [str]

    class age(DataProperty, FunctionalProperty):
        domain = [Personne]; range = [int]

    class dateNaissance(DataProperty, FunctionalProperty):
        domain = [Personne]; range = [datetime.date]

    class telephone(DataProperty):
        domain = [Personne]; range = [str]

    class email(DataProperty, FunctionalProperty):
        domain = [Personne]; range = [str]

    class adresse(DataProperty):
        domain = [Personne]; range = [str]

    class numeroCIN(DataProperty, FunctionalProperty, InverseFunctionalProperty):
        domain = [Personne]; range = [str]

    class specialite(DataProperty):
        domain = [MedecinSpecialiste]; range = [str]

    class numeroOrdre(DataProperty, FunctionalProperty):
        domain = [Medecin]; range = [str]

    class groupeSanguin(DataProperty):
        domain = [Patient]; range = [str]

    class numeroDossier(DataProperty, FunctionalProperty):
        domain = [Patient]; range = [str]

print("  [OK] nom, prenom         xsd:string  [Functional]")
print("  [OK] age                 xsd:integer [Functional]")
print("  [OK] dateNaissance       xsd:date    [Functional]")
print("  [OK] telephone, adresse  xsd:string")
print("  [OK] email               xsd:string  [Functional]")
print("  [OK] numeroCIN           xsd:string  [Functional + InverseFunctional]")
print("  [OK] specialite          xsd:string  (domain: MedecinSpecialiste)")
print("  [OK] numeroOrdre         xsd:string  [Functional] (domain: Medecin)")
print("  [OK] groupeSanguin       xsd:string  (domain: Patient)")
print("  [OK] numeroDossier       xsd:string  [Functional] (domain: Patient)\n")

# ======================================================================
# ETAPE 6 : Classes equivalentes (owl:equivalentClass)
# ======================================================================
print("=" * 60)
print("ETAPE 6 : Classes equivalentes (Defined Classes)")
print("=" * 60)

with onto:

    class MedecinActif(Thing):
        equivalent_to = [Medecin & realise.some(Consultation)]

    class PatientEnregistre(Thing):
        equivalent_to = [Patient & numeroDossier.some(str)]

print("  [OK] MedecinActif      = Medecin AND (realise SOME Consultation)")
print("  [OK] PatientEnregistre = Patient  AND (numeroDossier SOME xsd:string)\n")

# ======================================================================
# ETAPE 7 : Individus et assertions
# ======================================================================
print("=" * 60)
print("ETAPE 7 : Individus et assertions")
print("=" * 60)

with onto:

    dr_ahmed = Medecin("Dr_Ahmed")
    dr_ahmed.nom         = "Dr Ahmed Ben Salah"
    dr_ahmed.prenom      = "Ahmed"
    dr_ahmed.age         = 50
    dr_ahmed.telephone   = ["+216 71 000 001"]
    dr_ahmed.email       = "ahmed.bensalah@hopital.tn"
    dr_ahmed.numeroCIN   = "00123456"
    dr_ahmed.numeroOrdre = "MED-001"
    dr_ahmed.adresse     = ["3 Avenue Habib Bourguiba, Tunis"]

    dr_karim = MedecinSpecialiste("Dr_Karim")
    dr_karim.nom         = "Dr Karim Mansour"
    dr_karim.prenom      = "Karim"
    dr_karim.age         = 40
    dr_karim.telephone   = ["+216 71 000 002"]
    dr_karim.email       = "karim.mansour@hopital.tn"
    dr_karim.numeroCIN   = "00234567"
    dr_karim.specialite  = ["Cardiologie"]
    dr_karim.numeroOrdre = "MED-002"

    sami = PatientAdulte("Sami")
    sami.nom           = "Sami Trabelsi"
    sami.prenom        = "Sami"
    sami.age           = 32
    sami.telephone     = ["+216 22 333 444"]
    sami.numeroDossier = "PAT-001"
    sami.groupeSanguin = ["A+"]
    sami.adresse       = ["12 Rue de la Republique, Tunis"]
    sami.numeroCIN     = "00345678"

    amina = PatientEnfant("Amina")
    amina.nom           = "Amina Gharbi"
    amina.prenom        = "Amina"
    amina.age           = 8
    amina.numeroDossier = "PAT-002"
    amina.groupeSanguin = ["O+"]
    amina.numeroCIN     = "00456789"

    ali = Stagiaire("Ali_Stagiaire")
    ali.nom       = "Ali Ben Romdhane"
    ali.prenom    = "Ali"
    ali.age       = 25
    ali.telephone = ["+216 55 000 111"]
    ali.numeroCIN = "00567890"

    service_cardio   = Service("Service_Cardio")
    service_urgences = Service("Service_Urgences")
    consult_1        = Consultation("Consultation_1")
    grippe_sami      = MaladieInfectieuse("Grippe_Sami")
    fievre_sami      = Symptome("Fievre_Sami")

    dr_ahmed.appartientA  = [service_cardio]
    dr_ahmed.diagnostique = [grippe_sami]
    dr_ahmed.realise      = [consult_1]
    dr_ahmed.soigne       = [sami]
    dr_ahmed.connait      = [dr_karim]

    dr_karim.appartientA  = [service_cardio]
    dr_karim.soigne       = [sami]

    sami.estSoignePar       = [dr_ahmed]
    sami.estPrisEnChargePar = [service_cardio]
    sami.presente           = [fievre_sami]

    amina.estPrisEnChargePar = [service_urgences]

    dr_fatima = MedecinGeneraliste("Dr_Fatima")
    dr_fatima.nom         = "Dr Fatima Benali"
    dr_fatima.prenom      = "Fatima"
    dr_fatima.age         = 35
    dr_fatima.telephone   = ["+216 71 000 003"]
    dr_fatima.email       = "fatima.benali@hopital.tn"
    dr_fatima.numeroCIN   = "00678901"
    dr_fatima.numeroOrdre = "MED-003"
    dr_fatima.adresse     = ["7 Rue Ibn Khaldoun, Tunis"]
    dr_fatima.appartientA = [service_urgences]

    AllDifferent([dr_ahmed, dr_karim, dr_fatima, sami, amina, ali])

print("  [OK] Dr_Ahmed      (Medecin)             cree")
print("  [OK] Dr_Karim      (MedecinSpecialiste)  cree")
print("  [OK] Dr_Fatima     (MedecinGeneraliste)  cree - Service Urgences")
print("  [OK] Sami          (PatientAdulte)        cree")
print("  [OK] Amina         (PatientEnfant)        creee")
print("  [OK] Ali_Stagiaire (Stagiaire)            cree")
print("  [OK] AllDifferent declare sur tous les individus Personne\n")

# ======================================================================
# ETAPE 8 : Annotations RDF / RDFS (labels, comments)
# ======================================================================
print("=" * 60)
print("ETAPE 8 : Annotations RDF/RDFS")
print("=" * 60)

with onto:
    Personne.label        = ["Personne"]
    Personne.comment      = ["Toute entite humaine dans le systeme medical."]
    Medecin.label         = ["Medecin"]
    Medecin.comment       = ["Professionnel de sante autorise a pratiquer la medecine."]
    Patient.label         = ["Patient"]
    Patient.comment       = ["Personne recevant des soins medicaux."]
    Role.label            = ["Role"]
    MedecinActif.label    = ["Medecin actif"]
    MedecinActif.comment  = ["Classe definie (Medecin qui realise au moins une Consultation)."]
    PatientEnregistre.label   = ["Patient enregistre"]
    PatientEnregistre.comment = ["Classe definie (Patient qui possede un numero de dossier)."]

    joueLeRoleDe.label  = ["joue le role de"]
    estSoignePar.label  = ["est soigne par"]
    soigne.label        = ["soigne"]
    presente.label      = ["presente"]
    connait.label       = ["connait"]
    aConsulte.label     = ["a consulte"]
    nom.label           = ["nom"]
    age.label           = ["age"]
    numeroCIN.label     = ["numero CIN"]
    numeroDossier.label = ["numero de dossier"]
    groupeSanguin.label = ["groupe sanguin"]

print("  [OK] rdfs:label et rdfs:comment ajoutes sur classes et proprietes\n")

# ======================================================================
# ETAPE 9 : Interrogation de l'ontologie (style SPARQL en Python)
# ======================================================================
print("=" * 60)
print("ETAPE 9 : Interrogation de l'ontologie")
print("=" * 60)

print("\n  >> Hierarchie de Personne :")
def print_tree(cls, indent=0):
    for sub in cls.subclasses():
        print("     " + "  " * indent + "|- " + sub.name)
        print_tree(sub, indent + 1)
print_tree(Personne)

print("\n  >> Individus de type Medecin :")
for ind in Medecin.instances():
    print(f"     {ind.name:20s} | nom={ind.nom} | age={ind.age}")

print("\n  >> Individus de type Patient :")
for ind in Patient.instances():
    print(f"     {ind.name:20s} | nom={ind.nom} | age={ind.age} | dossier={ind.numeroDossier}")

print("\n  >> Proprietes de Dr_Ahmed :")
print(f"     appartientA   = {dr_ahmed.appartientA}")
print(f"     soigne        = {dr_ahmed.soigne}")
print(f"     connait       = {dr_ahmed.connait}")

print("\n  >> Proprietes de Sami :")
print(f"     estSoignePar       = {sami.estSoignePar}")
print(f"     presente           = {sami.presente}")
print(f"     estPrisEnChargePar = {sami.estPrisEnChargePar}")

print("\n  >> Test symetrie (connait) :")
print(f"     dr_ahmed.connait = {dr_ahmed.connait}")
print(f"     dr_karim.connait = {dr_karim.connait}  <- infere auto par symetrie")
print()

# ======================================================================
# ETAPE 10 : Raisonnement et inference
# ======================================================================
print("=" * 60)
print("ETAPE 10 : Raisonnement et inference (HermiT / Pellet)")
print("=" * 60)
print("  [INFO] Necessite Java JRE >= 8 dans le PATH.")

try:
    with onto:
        sync_reasoner_hermit(infer_property_values=True)
    print("  [OK] HermiT termine.")
    print(f"  MedecinActif infere     : {list(MedecinActif.instances())}")
    print(f"  PatientEnregistre infere: {list(PatientEnregistre.instances())}")
except Exception as e:
    print(f"  [!] HermiT : {e}")
    try:
        with onto:
            sync_reasoner_pellet(infer_property_values=True)
        print("  [OK] Pellet termine.")
    except Exception as e2:
        print(f"  [!] Pellet : {e2}")
        print("  -> Installez Java JRE >= 8 pour activer le raisonnement.")
print()

# ======================================================================
# ETAPE 11 : Serialisation et sauvegarde OWL
# ======================================================================
print("=" * 60)
print("ETAPE 11 : Serialisation et sauvegarde")
print("=" * 60)

OUT_DIR  = os.path.dirname(os.path.abspath(__file__))
OWL_FILE = os.path.join(OUT_DIR, "ontologie_personne.owl")

onto.save(file=OWL_FILE, format="rdfxml")
print(f"  [OK] OWL/RDF-XML -> {OWL_FILE}")
print()

# ======================================================================
# ETAPE 12 : Recharger l'ontologie depuis le fichier OWL
# ======================================================================
print("=" * 60)
print("ETAPE 12 : Chargement depuis fichier OWL")
print("=" * 60)

world2 = World()
onto2 = world2.get_ontology("file://" + OWL_FILE.replace("\\", "/")).load()
print(f"  [OK] Ontologie rechargee depuis : {OWL_FILE}")
print(f"  Classes         : {len(list(onto2.classes()))}")
print(f"  Individus       : {len(list(onto2.individuals()))}")
print(f"  Obj.Properties  : {len(list(onto2.object_properties()))}")
print(f"  Data Properties : {len(list(onto2.data_properties()))}")

print("\n  Individus charges :")
for ind in onto2.individuals():
    print(f"    - {ind.name}")

print("\n" + "=" * 60)
print(" Manipulation owlready2 terminee avec succes !")
print("=" * 60)
