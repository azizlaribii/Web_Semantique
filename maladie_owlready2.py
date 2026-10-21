# -*- coding: utf-8 -*-
"""
Manipulation avec Owlready2 - Ontologie Medicale (Module Maladie)
pip install owlready2
"""
import sys, io, subprocess, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ETAPE 0
print("=" * 65)
print("ETAPE 0 : Verification / Installation owlready2")
print("=" * 65)
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

# ETAPE 1
print("=" * 65)
print("ETAPE 1 : Creation de l'ontologie OWL -- Module Maladie")
print("=" * 65)
IRI  = "http://example.org/ontologie-maladie#"
onto = get_ontology(IRI)
print(f"[OK] Ontologie creee avec IRI : {IRI}\n")

# ETAPE 2
print("=" * 65)
print("ETAPE 2 : Definition des classes et sous-classes")
print("=" * 65)
with onto:
    class Maladie(Thing): pass
    class MaladieInfectieuse(Maladie): pass
    class MaladieChronique(Maladie): pass
    class MaladieDigestive(Maladie): pass
    class Grippe(MaladieInfectieuse): pass
    class Angine(MaladieInfectieuse): pass
    class Diabete(MaladieChronique): pass
    class Hypertension(MaladieChronique): pass
    class UlcereGastrique(MaladieDigestive): pass
    class Symptome(Thing): pass
    class SymptomeGeneral(Symptome): pass
    class SymptomeRespiratoire(Symptome): pass
    class SymptomeDigestif(Symptome): pass
    class Medicament(Thing): pass
    class Ordonnance(Thing): pass
    class Operation(Thing): pass
    class Medecin(Thing): pass
    class Patient(Thing): pass
    class AgentPathogene(Thing): pass
    class Virus(AgentPathogene): pass
    class Bacterie(AgentPathogene): pass

print("  Classes Maladie definies :")
for cls in [Maladie, MaladieInfectieuse, MaladieChronique, MaladieDigestive,
            Grippe, Angine, Diabete, Hypertension, UlcereGastrique]:
    parent = cls.__bases__[0].name if cls.__bases__ else "-"
    print(f"    {cls.name:25s} sous-classe de -> {parent}")
print("\n  Classes Symptome definies :")
for cls in [Symptome, SymptomeGeneral, SymptomeRespiratoire, SymptomeDigestif]:
    parent = cls.__bases__[0].name if cls.__bases__ else "-"
    print(f"    {cls.name:25s} sous-classe de -> {parent}")
print()

# ETAPE 3
print("=" * 65)
print("ETAPE 3 : Disjonctions (owl:AllDisjointClasses)")
print("=" * 65)
with onto:
    AllDisjoint([MaladieInfectieuse, MaladieChronique, MaladieDigestive])
    AllDisjoint([Grippe, Angine])
    AllDisjoint([Diabete, Hypertension])
    AllDisjoint([SymptomeGeneral, SymptomeRespiratoire, SymptomeDigestif])
    AllDisjoint([Virus, Bacterie])
print("  [OK] MaladieInfectieuse DISJOINT MaladieChronique DISJOINT MaladieDigestive")
print("  [OK] Grippe DISJOINT Angine")
print("  [OK] Diabete DISJOINT Hypertension")
print("  [OK] Symptomes tous disjoints\n")

# ETAPE 4
print("=" * 65)
print("ETAPE 4 : Object Properties")
print("=" * 65)
with onto:
    class aPourSymptome(ObjectProperty):
        domain = [Maladie]; range = [Symptome]
    class estSymptomeDe(ObjectProperty):
        inverse_property = aPourSymptome
        domain = [Symptome]; range = [Maladie]
    class estTraiteePar(ObjectProperty):
        domain = [Maladie]; range = [Medicament]
    class traite(ObjectProperty):
        inverse_property = estTraiteePar
        domain = [Medicament]; range = [Maladie]
    class touche(ObjectProperty):
        domain = [Maladie]; range = [Patient]
    class souffreDe(ObjectProperty):
        inverse_property = touche
        domain = [Patient]; range = [Maladie]
    class necessite(ObjectProperty):
        domain = [Maladie]; range = [Operation]
    class estNecessairePour(ObjectProperty):
        inverse_property = necessite
        domain = [Operation]; range = [Maladie]
    class estPrescritePour(ObjectProperty):
        domain = [Ordonnance]; range = [Maladie]
    class concerneMaladie(ObjectProperty):
        inverse_property = estPrescritePour
        domain = [Maladie]; range = [Ordonnance]
    class necessiteSuiviPar(ObjectProperty):
        domain = [MaladieChronique]; range = [Medecin]
    class suit(ObjectProperty):
        inverse_property = necessiteSuiviPar
        domain = [Medecin]; range = [MaladieChronique]
    class aPourAgentPathogene(ObjectProperty):
        domain = [MaladieInfectieuse]; range = [AgentPathogene]
    class causeMaladie(ObjectProperty):
        inverse_property = aPourAgentPathogene
        domain = [AgentPathogene]; range = [MaladieInfectieuse]
    class provoque(TransitiveProperty, ObjectProperty):
        domain = [Maladie]; range = [Symptome]

print("  [OK] aPourSymptome     Maladie -> Symptome    [inverse: estSymptomeDe]")
print("  [OK] estTraiteePar     Maladie -> Medicament  [inverse: traite]")
print("  [OK] touche            Maladie -> Patient     [inverse: souffreDe]")
print("  [OK] necessite         Maladie -> Operation   [inverse: estNecessairePour]")
print("  [OK] estPrescritePour  Ordonnance -> Maladie  [inverse: concerneMaladie]")
print("  [OK] necessiteSuiviPar MaladieChronique -> Medecin [inverse: suit]")
print("  [OK] provoque          Maladie -> Symptome    [TRANSITIVE]\n")

# ETAPE 5
print("=" * 65)
print("ETAPE 5 : Data Properties")
print("=" * 65)
with onto:
    class nom(DataProperty, FunctionalProperty):
        domain = [Maladie]; range = [str]
    class description(DataProperty, FunctionalProperty):
        domain = [Maladie]; range = [str]
    class estContagieuse(DataProperty, FunctionalProperty):
        domain = [Maladie]; range = [bool]
    class estChronique(DataProperty, FunctionalProperty):
        domain = [Maladie]; range = [bool]
    class gravite(DataProperty, FunctionalProperty):
        domain = [Maladie]; range = [int]
    class dureeTraitement(DataProperty):
        domain = [Maladie]; range = [str]
    class codeCIM(DataProperty, FunctionalProperty):
        domain = [Maladie]; range = [str]
    class nomSymptome(DataProperty, FunctionalProperty):
        domain = [Symptome]; range = [str]

print("  [OK] nom, description, estContagieuse, estChronique, gravite")
print("  [OK] dureeTraitement, codeCIM (CIM-10), nomSymptome\n")

# ETAPE 6
print("=" * 65)
print("ETAPE 6 : Classes equivalentes (Defined Classes)")
print("=" * 65)
with onto:
    class MaladieGrave(Thing):
        equivalent_to = [Maladie & necessite.some(Operation)]
    class MaladieAvecSuivi(Thing):
        equivalent_to = [MaladieChronique & necessiteSuiviPar.some(Medecin)]
    class MaladieTraitee(Thing):
        equivalent_to = [Maladie & estTraiteePar.some(Medicament)]

print("  [OK] MaladieGrave     = Maladie AND (necessite SOME Operation)")
print("  [OK] MaladieAvecSuivi = MaladieChronique AND (necessiteSuiviPar SOME Medecin)")
print("  [OK] MaladieTraitee   = Maladie AND (estTraiteePar SOME Medicament)\n")

# ETAPE 7
print("=" * 65)
print("ETAPE 7 : Individus et assertions")
print("=" * 65)
with onto:
    fievre = SymptomeGeneral("Fievre"); fievre.nomSymptome = "Fievre"
    fatigue = SymptomeGeneral("Fatigue"); fatigue.nomSymptome = "Fatigue"
    toux = SymptomeRespiratoire("Toux"); toux.nomSymptome = "Toux"
    maux_gorge = SymptomeRespiratoire("Maux_de_gorge"); maux_gorge.nomSymptome = "Maux de gorge"
    nausee = SymptomeDigestif("Nausee"); nausee.nomSymptome = "Nausee"
    douleur_abd = SymptomeDigestif("Douleur_abdominale"); douleur_abd.nomSymptome = "Douleur abdominale"
    soif_excess = SymptomeGeneral("Soif_excessive"); soif_excess.nomSymptome = "Soif excessive"
    cephalee = SymptomeGeneral("Cephalee"); cephalee.nomSymptome = "Cephalee"

    paracetamol = Medicament("Paracetamol")
    amoxicilline = Medicament("Amoxicilline")
    ibuprofene = Medicament("Ibuprofene")
    metformine = Medicament("Metformine")
    amlodipine = Medicament("Amlodipine")
    omeprazole = Medicament("Omeprazole")

    ord_grippe = Ordonnance("Ordonnance_Grippe")
    ord_diabete = Ordonnance("Ordonnance_Diabete")
    op_gastro = Operation("Operation_Gastrique")
    dr_ali = Medecin("Dr_Ali_Maladie")
    dr_sonia = Medecin("Dr_Sonia_Maladie")
    patient_karim = Patient("Karim_Patient")
    patient_leila = Patient("Leila_Patient")

    virus_influenza = Virus("Virus_Influenza")
    bacterie_strepto = Bacterie("Streptocoque_Pyogenes")

    grippe_inst = Grippe("Grippe_Saisonniere")
    grippe_inst.nom = "Grippe saisonniere"
    grippe_inst.description = "Maladie infectieuse respiratoire causee par le virus Influenza."
    grippe_inst.estContagieuse = True
    grippe_inst.estChronique = False
    grippe_inst.gravite = 2
    grippe_inst.dureeTraitement = ["7 jours"]
    grippe_inst.codeCIM = "J11"
    grippe_inst.aPourSymptome = [fievre, toux, fatigue]
    grippe_inst.estTraiteePar = [paracetamol, ibuprofene]
    grippe_inst.touche = [patient_karim]
    grippe_inst.concerneMaladie = [ord_grippe]
    grippe_inst.aPourAgentPathogene = [virus_influenza]

    angine_inst = Angine("Angine_Streptocoque")
    angine_inst.nom = "Angine streptocoque"
    angine_inst.description = "Infection bacterienne des amygdales."
    angine_inst.estContagieuse = True
    angine_inst.estChronique = False
    angine_inst.gravite = 1
    angine_inst.dureeTraitement = ["10 jours"]
    angine_inst.codeCIM = "J03"
    angine_inst.aPourSymptome = [maux_gorge, fievre]
    angine_inst.estTraiteePar = [amoxicilline]
    angine_inst.touche = [patient_leila]
    angine_inst.aPourAgentPathogene = [bacterie_strepto]

    diabete_inst = Diabete("Diabete_Type2")
    diabete_inst.nom = "Diabete de type 2"
    diabete_inst.description = "Maladie chronique due a un defaut d'utilisation de l'insuline."
    diabete_inst.estContagieuse = False
    diabete_inst.estChronique = True
    diabete_inst.gravite = 2
    diabete_inst.dureeTraitement = ["Traitement a vie"]
    diabete_inst.codeCIM = "E11"
    diabete_inst.aPourSymptome = [soif_excess, fatigue]
    diabete_inst.estTraiteePar = [metformine]
    diabete_inst.touche = [patient_karim]
    diabete_inst.necessiteSuiviPar = [dr_ali]
    diabete_inst.concerneMaladie = [ord_diabete]

    hypertension_inst = Hypertension("Hypertension_Arterielle")
    hypertension_inst.nom = "Hypertension arterielle"
    hypertension_inst.description = "Pression arterielle anormalement elevee."
    hypertension_inst.estContagieuse = False
    hypertension_inst.estChronique = True
    hypertension_inst.gravite = 3
    hypertension_inst.dureeTraitement = ["Traitement a vie"]
    hypertension_inst.codeCIM = "I10"
    hypertension_inst.aPourSymptome = [cephalee, fatigue]
    hypertension_inst.estTraiteePar = [amlodipine]
    hypertension_inst.touche = [patient_leila]
    hypertension_inst.necessiteSuiviPar = [dr_sonia]

    ulcere_inst = UlcereGastrique("Ulcere_Gastrique_Sami")
    ulcere_inst.nom = "Ulcere gastrique"
    ulcere_inst.description = "Lesion de la muqueuse de l'estomac."
    ulcere_inst.estContagieuse = False
    ulcere_inst.estChronique = False
    ulcere_inst.gravite = 2
    ulcere_inst.dureeTraitement = ["4 a 8 semaines"]
    ulcere_inst.codeCIM = "K25"
    ulcere_inst.aPourSymptome = [nausee, douleur_abd]
    ulcere_inst.estTraiteePar = [omeprazole]
    ulcere_inst.necessite = [op_gastro]

    ord_grippe.estPrescritePour = [grippe_inst]
    ord_diabete.estPrescritePour = [diabete_inst]
    AllDifferent([grippe_inst, angine_inst, diabete_inst, hypertension_inst, ulcere_inst])

print("  [OK] Grippe_Saisonniere      (Grippe)          codeCIM: J11")
print("  [OK] Angine_Streptocoque     (Angine)          codeCIM: J03")
print("  [OK] Diabete_Type2           (Diabete)         codeCIM: E11 | suivi: Dr_Ali")
print("  [OK] Hypertension_Arterielle (Hypertension)    codeCIM: I10 | suivi: Dr_Sonia")
print("  [OK] Ulcere_Gastrique_Sami   (UlcereGastrique) codeCIM: K25 | necessite: Operation")
print("  [OK] AllDifferent declare\n")

# ETAPE 8
print("=" * 65)
print("ETAPE 8 : Annotations RDF/RDFS")
print("=" * 65)
with onto:
    Maladie.label = ["Maladie"]
    Maladie.comment = ["Toute affection pathologique dans le systeme medical."]
    MaladieInfectieuse.label = ["Maladie infectieuse"]
    MaladieChronique.label = ["Maladie chronique"]
    MaladieDigestive.label = ["Maladie digestive"]
    Symptome.label = ["Symptome"]
    MaladieGrave.label = ["Maladie grave"]
    MaladieGrave.comment = ["Classe definie : Maladie necessitant une Operation."]
    MaladieAvecSuivi.label = ["Maladie avec suivi"]
    MaladieAvecSuivi.comment = ["Classe definie : MaladieChronique avec suivi Medecin."]
    MaladieTraitee.label = ["Maladie traitee"]
    MaladieTraitee.comment = ["Classe definie : Maladie traitee par un Medicament."]
    aPourSymptome.label = ["a pour symptome"]
    estSymptomeDe.label = ["est symptome de"]
    estTraiteePar.label = ["est traitee par"]
    traite.label = ["traite"]
    touche.label = ["touche"]
    souffreDe.label = ["souffre de"]
    necessite.label = ["necessite"]
    estNecessairePour.label = ["est necessaire pour"]
    estPrescritePour.label = ["est prescrite pour"]
    concerneMaladie.label = ["concerne maladie"]
    necessiteSuiviPar.label = ["necessite suivi par"]
    suit.label = ["suit"]
    provoque.label = ["provoque"]
    AgentPathogene.label = ["Agent pathogene"]
    Virus.label = ["Virus"]
    Bacterie.label = ["Bacterie"]
    aPourAgentPathogene.label = ["a pour agent pathogene"]
    causeMaladie.label = ["cause maladie"]
print("  [OK] rdfs:label et rdfs:comment ajoutes\n")

# ETAPE 9
print("=" * 65)
print("ETAPE 9 : Interrogation de l'ontologie")
print("=" * 65)
print("\n  >> Hierarchie de Maladie :")
def print_tree(cls, indent=0):
    for sub in cls.subclasses():
        print("     " + "  " * indent + "|- " + sub.name)
        print_tree(sub, indent + 1)
print_tree(Maladie)
print("\n  >> Hierarchie de Symptome :")
print_tree(Symptome)
print("\n  >> Individus MaladieInfectieuse :")
for ind in MaladieInfectieuse.instances():
    print(f"     {ind.name:30s} | codeCIM={ind.codeCIM} | contagieuse={ind.estContagieuse} | gravite={ind.gravite}")
print("\n  >> Individus MaladieChronique :")
for ind in MaladieChronique.instances():
    print(f"     {ind.name:30s} | codeCIM={ind.codeCIM} | gravite={ind.gravite}")
print("\n  >> Symptomes de la Grippe :")
for s in grippe_inst.aPourSymptome:
    print(f"     - {s.name}")
print("\n  >> Medicaments de la Grippe :")
for m in grippe_inst.estTraiteePar:
    print(f"     - {m.name}")
print("\n  >> Maladies touchant Karim_Patient :")
for mal in Maladie.instances():
    if patient_karim in mal.touche:
        print(f"     - {mal.name}")
print(f"\n  >> Ulcere necessite : {ulcere_inst.necessite}")
print()

# ETAPE 10
print("=" * 65)
print("ETAPE 10 : Raisonnement et inference (HermiT / Pellet)")
print("=" * 65)
print("  [INFO] Necessite Java JRE >= 8 dans le PATH.")
try:
    with onto:
        sync_reasoner_hermit(infer_property_values=True)
    print("  [OK] HermiT termine.")
    print(f"  MaladieGrave infere     : {list(MaladieGrave.instances())}")
    print(f"  MaladieAvecSuivi infere : {list(MaladieAvecSuivi.instances())}")
    print(f"  MaladieTraitee infere   : {list(MaladieTraitee.instances())}")
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

# ETAPE 11
print("=" * 65)
print("ETAPE 11 : Serialisation et sauvegarde")
print("=" * 65)
OUT_DIR  = os.path.dirname(os.path.abspath(__file__))
OWL_FILE = os.path.join(OUT_DIR, "ontologie_maladie.owl")
onto.save(file=OWL_FILE, format="rdfxml")
print(f"  [OK] OWL/RDF-XML -> {OWL_FILE}\n")

# ETAPE 12
print("=" * 65)
print("ETAPE 12 : Chargement depuis fichier OWL")
print("=" * 65)
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
print("\n" + "=" * 65)
print(" Module Maladie -- owlready2 termine avec succes !")
print("=" * 65)
