# -*- coding: utf-8 -*-
"""
Manipulation avec Owlready2 - Ontologie Medicale (Module Medicament)
Domaine : Pharmaceutique et Sante
Concept : molecules, effets secondaires, contre-indications, interactions et donnees cliniques.

pip install owlready2
Genere : ontologie_medicament.owl (ouvrable dans Protege)
"""
import sys, io, subprocess, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ETAPE 0
print("=" * 65)
print("ETAPE 0 : Verification / Installation owlready2")
print("=" * 65)
try:
    import owlready2  # noqa: F401
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "owlready2", "-q"], check=True)
print("[OK] owlready2 disponible.\n")

from owlready2 import (
    get_ontology, Thing, World,
    ObjectProperty, DataProperty,
    FunctionalProperty, SymmetricProperty,
    AllDisjoint, AllDifferent,
    sync_reasoner_hermit, sync_reasoner_pellet,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
MALADIE_OWL = os.path.join(OUT_DIR, "ontologie_maladie.owl")

# ETAPE 1
print("=" * 65)
print("ETAPE 1 : Creation de l'ontologie OWL -- Module Medicament")
print("=" * 65)
IRI = "http://example.org/ontologie-medicament#"
onto = get_ontology(IRI)
print(f"[OK] Ontologie creee avec IRI : {IRI}")

# Liaison avec le module Maladie : on charge ontologie_maladie.owl (sans owl:imports)
# pour pouvoir pointer vers ses individus (Grippe_Saisonniere, Diabete_Type2, ...).
mal = None
if os.path.exists(MALADIE_OWL):
    mal = get_ontology("file://" + MALADIE_OWL.replace("\\", "/")).load()
    print(f"[OK] Module Maladie charge pour les liens croises : {MALADIE_OWL}\n")
else:
    print("[!] ontologie_maladie.owl introuvable : les liens vers les maladies seront ignores.\n")

# ETAPE 2
print("=" * 65)
print("ETAPE 2 : Definition des classes et sous-classes")
print("=" * 65)
with onto:
    # --- Medicaments par classe therapeutique ---
    class Medicament(Thing): pass
    class Antalgique(Medicament): pass
    class AntiInflammatoire(Medicament): pass
    class Antibiotique(Medicament): pass
    class Antidiabetique(Medicament): pass
    class Antihypertenseur(Medicament): pass
    class AntiUlcereux(Medicament): pass
    class Anticoagulant(Medicament): pass

    # --- Molecules (principes actifs) ---
    class Molecule(Thing): pass

    # --- Effets secondaires ---
    class EffetSecondaire(Thing): pass
    class EffetDigestif(EffetSecondaire): pass
    class EffetNeurologique(EffetSecondaire): pass
    class EffetCutane(EffetSecondaire): pass
    class EffetCardiovasculaire(EffetSecondaire): pass
    class EffetHepatique(EffetSecondaire): pass
    class EffetHematologique(EffetSecondaire): pass
    class EffetMetabolique(EffetSecondaire): pass

    # --- Contre-indications non pathologiques (grossesse, allergie, ...) ---
    class ConditionClinique(Thing): pass

    # --- Interactions medicamenteuses (relation reifiee) ---
    class InteractionMedicamenteuse(Thing): pass

    # --- Donnees cliniques ---
    class EssaiClinique(Thing): pass

print("  Classes Medicament :")
for cls in [Medicament, Antalgique, AntiInflammatoire, Antibiotique, Antidiabetique,
            Antihypertenseur, AntiUlcereux, Anticoagulant]:
    print(f"    {cls.name:25s} sous-classe de -> {cls.__bases__[0].name}")
print("  Classes EffetSecondaire :")
for cls in [EffetDigestif, EffetNeurologique, EffetCutane, EffetCardiovasculaire,
            EffetHepatique, EffetHematologique, EffetMetabolique]:
    print(f"    {cls.name:25s} sous-classe de -> {cls.__bases__[0].name}")
print("  Autres : Molecule, ConditionClinique, InteractionMedicamenteuse, EssaiClinique\n")

# ETAPE 3
print("=" * 65)
print("ETAPE 3 : Disjonctions (owl:AllDisjointClasses)")
print("=" * 65)
with onto:
    # Un medicament peut etre a la fois Antalgique et AntiInflammatoire (ex: Aspirine),
    # mais les autres classes therapeutiques sont exclusives.
    AllDisjoint([Antibiotique, Antidiabetique, Antihypertenseur, AntiUlcereux, Anticoagulant])
    AllDisjoint([EffetDigestif, EffetNeurologique, EffetCutane, EffetCardiovasculaire,
                 EffetHepatique, EffetHematologique, EffetMetabolique])
    AllDisjoint([Medicament, Molecule, EffetSecondaire, ConditionClinique,
                 InteractionMedicamenteuse, EssaiClinique])
print("  [OK] Antibiotique / Antidiabetique / Antihypertenseur / AntiUlcereux / Anticoagulant disjoints")
print("  [OK] Familles d'effets secondaires disjointes")
print("  [OK] Medicament / Molecule / EffetSecondaire / ConditionClinique / Interaction / Essai disjoints\n")

# ETAPE 4
print("=" * 65)
print("ETAPE 4 : Object Properties")
print("=" * 65)
with onto:
    class contientMolecule(ObjectProperty):
        domain = [Medicament]; range = [Molecule]
    class estPrincipeActifDe(ObjectProperty):
        inverse_property = contientMolecule
        domain = [Molecule]; range = [Medicament]

    class peutProvoquer(ObjectProperty):
        domain = [Medicament]; range = [EffetSecondaire]
    class estProvoquePar(ObjectProperty):
        inverse_property = peutProvoquer
        domain = [EffetSecondaire]; range = [Medicament]

    class traite(ObjectProperty):
        domain = [Medicament]
        if mal is not None: range = [mal.Maladie]

    class estContreIndiquePour(ObjectProperty):
        domain = [Medicament]
        if mal is not None: range = [mal.Maladie]

    class estContreIndiqueEn(ObjectProperty):
        domain = [Medicament]; range = [ConditionClinique]

    class interagitAvec(ObjectProperty, SymmetricProperty):
        domain = [Medicament]; range = [Medicament]

    class impliqueMedicament(ObjectProperty):
        domain = [InteractionMedicamenteuse]; range = [Medicament]

    class evalue(ObjectProperty):
        domain = [EssaiClinique]; range = [Medicament]
    class estEvaluePar(ObjectProperty):
        inverse_property = evalue
        domain = [Medicament]; range = [EssaiClinique]

    class aObserveEffet(ObjectProperty):
        domain = [EssaiClinique]; range = [EffetSecondaire]

print("  [OK] contientMolecule      Medicament -> Molecule        [inverse: estPrincipeActifDe]")
print("  [OK] peutProvoquer         Medicament -> EffetSecondaire [inverse: estProvoquePar]")
print("  [OK] traite                Medicament -> mal:Maladie     (lien module Maladie)")
print("  [OK] estContreIndiquePour  Medicament -> mal:Maladie")
print("  [OK] estContreIndiqueEn    Medicament -> ConditionClinique")
print("  [OK] interagitAvec         Medicament -> Medicament      [SYMMETRIC]")
print("  [OK] impliqueMedicament    Interaction -> Medicament")
print("  [OK] evalue                EssaiClinique -> Medicament   [inverse: estEvaluePar]")
print("  [OK] aObserveEffet         EssaiClinique -> EffetSecondaire\n")

# ETAPE 5
print("=" * 65)
print("ETAPE 5 : Data Properties")
print("=" * 65)
with onto:
    # Medicament
    class nomCommercial(DataProperty, FunctionalProperty):
        domain = [Medicament]; range = [str]
    class dosage(DataProperty, FunctionalProperty):
        domain = [Medicament]; range = [str]
    class formeGalenique(DataProperty, FunctionalProperty):
        domain = [Medicament]; range = [str]
    class voieAdministration(DataProperty, FunctionalProperty):
        domain = [Medicament]; range = [str]
    class posologie(DataProperty, FunctionalProperty):
        domain = [Medicament]; range = [str]
    class codeATC(DataProperty, FunctionalProperty):
        domain = [Medicament]; range = [str]
    class prixTND(DataProperty, FunctionalProperty):
        domain = [Medicament]; range = [float]
    class necessiteOrdonnance(DataProperty, FunctionalProperty):
        domain = [Medicament]; range = [bool]
    # Molecule
    class nomMolecule(DataProperty, FunctionalProperty):
        domain = [Molecule]; range = [str]
    class formuleBrute(DataProperty, FunctionalProperty):
        domain = [Molecule]; range = [str]
    class masseMolaire(DataProperty, FunctionalProperty):
        domain = [Molecule]; range = [float]
    # Effet secondaire
    class nomEffet(DataProperty, FunctionalProperty):
        domain = [EffetSecondaire]; range = [str]
    class frequence(DataProperty, FunctionalProperty):
        domain = [EffetSecondaire]; range = [str]
    class graviteEffet(DataProperty, FunctionalProperty):
        domain = [EffetSecondaire]; range = [int]
    # Condition clinique
    class nomCondition(DataProperty, FunctionalProperty):
        domain = [ConditionClinique]; range = [str]
    # Interaction
    class niveauRisque(DataProperty, FunctionalProperty):
        domain = [InteractionMedicamenteuse]; range = [str]
    class descriptionInteraction(DataProperty, FunctionalProperty):
        domain = [InteractionMedicamenteuse]; range = [str]
    # Essai clinique
    class phase(DataProperty, FunctionalProperty):
        domain = [EssaiClinique]; range = [int]
    class nombrePatients(DataProperty, FunctionalProperty):
        domain = [EssaiClinique]; range = [int]
    class tauxEfficacite(DataProperty, FunctionalProperty):
        domain = [EssaiClinique]; range = [float]
    class anneeEssai(DataProperty, FunctionalProperty):
        domain = [EssaiClinique]; range = [int]
    class objectifEssai(DataProperty, FunctionalProperty):
        domain = [EssaiClinique]; range = [str]

print("  [OK] Medicament : nomCommercial, dosage, formeGalenique, voieAdministration,")
print("                    posologie, codeATC, prixTND, necessiteOrdonnance")
print("  [OK] Molecule   : nomMolecule, formuleBrute, masseMolaire")
print("  [OK] Effet      : nomEffet, frequence, graviteEffet (1 legere, 2 moderee, 3 grave)")
print("  [OK] Interaction: niveauRisque, descriptionInteraction")
print("  [OK] Essai      : phase, nombrePatients, tauxEfficacite, anneeEssai, objectifEssai\n")

# ETAPE 6
print("=" * 65)
print("ETAPE 6 : Restrictions et classes definies")
print("=" * 65)
with onto:
    # Tout medicament contient au moins une molecule
    Medicament.is_a.append(contientMolecule.some(Molecule))

    class EffetGrave(Thing):
        equivalent_to = [EffetSecondaire & graviteEffet.value(3)]
    class MedicamentARisque(Thing):
        equivalent_to = [Medicament & peutProvoquer.some(EffetGrave)]
    class MedicamentSurOrdonnance(Thing):
        equivalent_to = [Medicament & necessiteOrdonnance.value(True)]
    class MedicamentEvalueCliniquement(Thing):
        equivalent_to = [Medicament & estEvaluePar.some(EssaiClinique)]

print("  [OK] Medicament SUBCLASS OF (contientMolecule SOME Molecule)")
print("  [OK] EffetGrave                   = EffetSecondaire AND (graviteEffet VALUE 3)")
print("  [OK] MedicamentARisque            = Medicament AND (peutProvoquer SOME EffetGrave)")
print("  [OK] MedicamentSurOrdonnance      = Medicament AND (necessiteOrdonnance VALUE true)")
print("  [OK] MedicamentEvalueCliniquement = Medicament AND (estEvaluePar SOME EssaiClinique)\n")

# ETAPE 7
print("=" * 65)
print("ETAPE 7 : Individus et assertions")
print("=" * 65)


def M(name):
    """Recupere un individu du module Maladie (ou None si non charge)."""
    return getattr(mal, name, None) if mal is not None else None


def maladies(*names):
    return [m for m in (M(n) for n in names) if m is not None]


with onto:
    # ---------- Molecules ----------
    def molecule(ident, nom, formule, masse):
        m = Molecule(ident)
        m.nomMolecule = nom; m.formuleBrute = formule; m.masseMolaire = masse
        return m

    mol_paracetamol = molecule("Mol_Paracetamol", "Paracetamol", "C8H9NO2", 151.16)
    mol_ibuprofene  = molecule("Mol_Ibuprofene", "Ibuprofene", "C13H18O2", 206.28)
    mol_amoxicilline = molecule("Mol_Amoxicilline", "Amoxicilline", "C16H19N3O5S", 365.40)
    mol_metformine  = molecule("Mol_Metformine", "Metformine", "C4H11N5", 129.16)
    mol_amlodipine  = molecule("Mol_Amlodipine", "Amlodipine", "C20H25ClN2O5", 408.88)
    mol_omeprazole  = molecule("Mol_Omeprazole", "Omeprazole", "C17H19N3O3S", 345.42)
    mol_aspirine    = molecule("Mol_Acide_Acetylsalicylique", "Acide acetylsalicylique", "C9H8O4", 180.16)
    mol_warfarine   = molecule("Mol_Warfarine", "Warfarine", "C19H16O4", 308.33)

    # ---------- Effets secondaires ----------
    def effet(cls, ident, nom, freq, grav):
        e = cls(ident)
        e.nomEffet = nom; e.frequence = freq; e.graviteEffet = grav
        return e

    e_hepato    = effet(EffetHepatique, "Hepatotoxicite", "Hepatotoxicite (surdosage)", "Rare", 3)
    e_nausee    = effet(EffetDigestif, "Nausee_Effet", "Nausees", "Frequent", 1)
    e_diarrhee  = effet(EffetDigestif, "Diarrhee", "Diarrhee", "Tres frequent", 1)
    e_gastralg  = effet(EffetDigestif, "Douleur_Gastrique", "Douleurs et brulures d'estomac", "Frequent", 2)
    e_hemo_dig  = effet(EffetHematologique, "Hemorragie_Digestive", "Hemorragie digestive", "Rare", 3)
    e_saign     = effet(EffetHematologique, "Saignement", "Saignements (gencives, nez, hematomes)", "Frequent", 3)
    e_eruption  = effet(EffetCutane, "Eruption_Cutanee", "Eruption cutanee / urticaire", "Frequent", 2)
    e_oedeme    = effet(EffetCardiovasculaire, "Oedeme_Chevilles", "Oedemes des chevilles", "Tres frequent", 1)
    e_bouffee   = effet(EffetCardiovasculaire, "Bouffees_Chaleur", "Bouffees de chaleur", "Frequent", 1)
    e_cephalee  = effet(EffetNeurologique, "Cephalee_Effet", "Maux de tete", "Frequent", 1)
    e_vertige   = effet(EffetNeurologique, "Vertige_Effet", "Vertiges", "Peu frequent", 1)
    e_acidose   = effet(EffetMetabolique, "Acidose_Lactique", "Acidose lactique", "Tres rare", 3)

    # ---------- Conditions cliniques (contre-indications non pathologiques) ----------
    def condition(ident, nom):
        c = ConditionClinique(ident); c.nomCondition = nom
        return c

    c_grossesse = condition("Grossesse", "Grossesse")
    c_ins_hep   = condition("Insuffisance_Hepatique_Severe", "Insuffisance hepatique severe")
    c_ins_ren   = condition("Insuffisance_Renale_Severe", "Insuffisance renale severe")
    c_allergie  = condition("Allergie_Penicilline", "Allergie aux penicillines")
    c_enfant    = condition("Enfant_Infection_Virale", "Enfant avec infection virale (risque de syndrome de Reye)")
    c_hypotens  = condition("Hypotension_Severe", "Hypotension severe / choc")

    # ---------- Medicaments ----------
    def medicament(classes, ident, nom, dos, forme, poso, atc, prix, ordo, molecules):
        m = classes[0](ident)
        for c in classes[1:]:
            m.is_a.append(c)
        m.nomCommercial = nom; m.dosage = dos; m.formeGalenique = forme
        m.voieAdministration = "Orale"; m.posologie = poso; m.codeATC = atc
        m.prixTND = prix; m.necessiteOrdonnance = ordo
        m.contientMolecule = molecules
        return m

    doliprane = medicament([Antalgique], "Doliprane", "Doliprane", "1000 mg", "Comprime",
                           "1 comprime toutes les 6 h, maximum 4 g par jour", "N02BE01", 3.20, False,
                           [mol_paracetamol])
    brufen = medicament([AntiInflammatoire, Antalgique], "Brufen", "Brufen", "400 mg", "Comprime pellicule",
                        "1 comprime 3 fois par jour au cours des repas", "M01AE01", 5.80, False,
                        [mol_ibuprofene])
    clamoxyl = medicament([Antibiotique], "Clamoxyl", "Clamoxyl", "1 g", "Comprime dispersible",
                          "1 g 2 a 3 fois par jour pendant 6 a 10 jours", "J01CA04", 9.50, True,
                          [mol_amoxicilline])
    glucophage = medicament([Antidiabetique], "Glucophage", "Glucophage", "850 mg", "Comprime pellicule",
                            "1 comprime 2 a 3 fois par jour pendant les repas", "A10BA02", 6.40, True,
                            [mol_metformine])
    amlor = medicament([Antihypertenseur], "Amlor", "Amlor", "5 mg", "Gelule",
                       "1 gelule par jour", "C08CA01", 12.70, True,
                       [mol_amlodipine])
    mopral = medicament([AntiUlcereux], "Mopral", "Mopral", "20 mg", "Gelule gastro-resistante",
                        "1 gelule par jour avant le repas, 4 a 8 semaines", "A02BC01", 14.90, True,
                        [mol_omeprazole])
    aspegic = medicament([Antalgique, AntiInflammatoire], "Aspegic", "Aspegic", "500 mg", "Sachet",
                         "1 sachet toutes les 4 a 6 h, maximum 3 g par jour", "N02BA01", 4.10, False,
                         [mol_aspirine])
    coumadine = medicament([Anticoagulant], "Coumadine", "Coumadine", "5 mg", "Comprime secable",
                           "Dose adaptee selon l'INR, 1 prise par jour", "B01AA03", 8.30, True,
                           [mol_warfarine])

    # Effets secondaires
    doliprane.peutProvoquer  = [e_hepato, e_nausee]
    brufen.peutProvoquer     = [e_gastralg, e_hemo_dig, e_cephalee]
    clamoxyl.peutProvoquer   = [e_diarrhee, e_nausee, e_eruption]
    glucophage.peutProvoquer = [e_diarrhee, e_nausee, e_acidose]
    amlor.peutProvoquer      = [e_oedeme, e_cephalee, e_bouffee, e_vertige]
    mopral.peutProvoquer     = [e_cephalee, e_diarrhee, e_vertige]
    aspegic.peutProvoquer    = [e_gastralg, e_hemo_dig, e_saign]
    coumadine.peutProvoquer  = [e_saign, e_hemo_dig]

    # Contre-indications (conditions cliniques)
    doliprane.estContreIndiqueEn  = [c_ins_hep]
    brufen.estContreIndiqueEn     = [c_grossesse, c_ins_ren]
    clamoxyl.estContreIndiqueEn   = [c_allergie]
    glucophage.estContreIndiqueEn = [c_ins_ren]
    amlor.estContreIndiqueEn      = [c_hypotens]
    aspegic.estContreIndiqueEn    = [c_grossesse, c_enfant]
    coumadine.estContreIndiqueEn  = [c_grossesse]

    # Liens avec le module Maladie
    doliprane.traite  = maladies("Grippe_Saisonniere", "Angine_Streptocoque")
    brufen.traite     = maladies("Grippe_Saisonniere")
    clamoxyl.traite   = maladies("Angine_Streptocoque")
    glucophage.traite = maladies("Diabete_Type2")
    amlor.traite      = maladies("Hypertension_Arterielle")
    mopral.traite     = maladies("Ulcere_Gastrique_Sami")
    aspegic.traite    = maladies("Grippe_Saisonniere")

    brufen.estContreIndiquePour    = maladies("Ulcere_Gastrique_Sami", "Hypertension_Arterielle")
    aspegic.estContreIndiquePour   = maladies("Ulcere_Gastrique_Sami")
    coumadine.estContreIndiquePour = maladies("Ulcere_Gastrique_Sami")

    # Interactions medicamenteuses
    def interaction(ident, m1, m2, risque, desc):
        i = InteractionMedicamenteuse(ident)
        i.impliqueMedicament = [m1, m2]
        i.niveauRisque = risque; i.descriptionInteraction = desc
        m1.interagitAvec.append(m2)
        return i

    interaction("Interaction_Coumadine_Aspegic", coumadine, aspegic, "Eleve",
                "Association deconseillee : risque hemorragique fortement augmente.")
    interaction("Interaction_Coumadine_Brufen", coumadine, brufen, "Eleve",
                "AINS + anticoagulant : risque d'hemorragie digestive.")
    interaction("Interaction_Brufen_Aspegic", brufen, aspegic, "Modere",
                "Deux AINS associes : toxicite digestive cumulee.")
    interaction("Interaction_Brufen_Amlor", brufen, amlor, "Modere",
                "Les AINS diminuent l'effet antihypertenseur.")
    interaction("Interaction_Coumadine_Doliprane", coumadine, doliprane, "Faible",
                "Paracetamol a forte dose prolonge : surveiller l'INR.")

    # Donnees cliniques (valeurs pedagogiques fictives)
    def essai(ident, med, ph, nb, taux, annee, objectif, effets):
        e = EssaiClinique(ident)
        e.evalue = [med]; e.phase = ph; e.nombrePatients = nb
        e.tauxEfficacite = taux; e.anneeEssai = annee; e.objectifEssai = objectif
        e.aObserveEffet = effets
        return e

    essai("Essai_Doliprane_Fievre", doliprane, 4, 320, 87.5, 2021,
          "Baisse de la fievre en moins de 4 heures", [e_nausee])
    essai("Essai_Brufen_Douleur", brufen, 4, 410, 82.0, 2020,
          "Soulagement des douleurs inflammatoires", [e_gastralg, e_cephalee])
    essai("Essai_Clamoxyl_Angine", clamoxyl, 3, 250, 91.0, 2019,
          "Guerison de l'angine a streptocoque", [e_diarrhee, e_eruption])
    essai("Essai_Glucophage_HbA1c", glucophage, 4, 1200, 74.0, 2022,
          "Controle de l'HbA1c chez le diabetique de type 2", [e_diarrhee, e_nausee])
    essai("Essai_Amlor_Tension", amlor, 3, 540, 79.5, 2021,
          "Normalisation de la pression arterielle", [e_oedeme, e_cephalee])
    essai("Essai_Mopral_Ulcere", mopral, 3, 300, 93.0, 2018,
          "Cicatrisation de l'ulcere gastrique", [e_cephalee])

    AllDifferent([doliprane, brufen, clamoxyl, glucophage, amlor, mopral, aspegic, coumadine])

print("  [OK] 8 molecules, 12 effets secondaires, 6 conditions cliniques")
print("  [OK] 8 medicaments : Doliprane, Brufen, Clamoxyl, Glucophage, Amlor, Mopral, Aspegic, Coumadine")
print("  [OK] 5 interactions medicamenteuses, 6 essais cliniques")
print(f"  [OK] Liens vers le module Maladie : {'actifs' if mal is not None else 'desactives'}\n")

# ETAPE 8
print("=" * 65)
print("ETAPE 8 : Annotations RDF/RDFS")
print("=" * 65)
with onto:
    Medicament.label = ["Medicament"]
    Medicament.comment = ["Produit pharmaceutique commercialise, contenant au moins une molecule active."]
    Antalgique.label = ["Antalgique"]
    AntiInflammatoire.label = ["Anti-inflammatoire"]
    Antibiotique.label = ["Antibiotique"]
    Antidiabetique.label = ["Antidiabetique"]
    Antihypertenseur.label = ["Antihypertenseur"]
    AntiUlcereux.label = ["Anti-ulcereux"]
    Anticoagulant.label = ["Anticoagulant"]
    Molecule.label = ["Molecule"]
    Molecule.comment = ["Principe actif contenu dans un medicament."]
    EffetSecondaire.label = ["Effet secondaire"]
    EffetSecondaire.comment = ["Effet indesirable pouvant etre provoque par un medicament."]
    ConditionClinique.label = ["Condition clinique"]
    ConditionClinique.comment = ["Situation du patient qui contre-indique un medicament (grossesse, allergie, ...)."]
    InteractionMedicamenteuse.label = ["Interaction medicamenteuse"]
    EssaiClinique.label = ["Essai clinique"]
    EssaiClinique.comment = ["Donnees cliniques evaluant un medicament (valeurs pedagogiques fictives)."]
    EffetGrave.label = ["Effet grave"]
    EffetGrave.comment = ["Classe definie : EffetSecondaire dont la gravite vaut 3."]
    MedicamentARisque.label = ["Medicament a risque"]
    MedicamentARisque.comment = ["Classe definie : Medicament pouvant provoquer un EffetGrave."]
    MedicamentSurOrdonnance.label = ["Medicament sur ordonnance"]
    MedicamentEvalueCliniquement.label = ["Medicament evalue cliniquement"]
    contientMolecule.label = ["contient molecule"]
    estPrincipeActifDe.label = ["est principe actif de"]
    peutProvoquer.label = ["peut provoquer"]
    estProvoquePar.label = ["est provoque par"]
    traite.label = ["traite"]
    estContreIndiquePour.label = ["est contre-indique pour"]
    estContreIndiqueEn.label = ["est contre-indique en cas de"]
    interagitAvec.label = ["interagit avec"]
    evalue.label = ["evalue"]
    estEvaluePar.label = ["est evalue par"]
    aObserveEffet.label = ["a observe l'effet"]
print("  [OK] rdfs:label et rdfs:comment ajoutes\n")

# ETAPE 9
print("=" * 65)
print("ETAPE 9 : Interrogation de l'ontologie")
print("=" * 65)
print("\n  >> Medicaments par classe therapeutique :")
for cls in [Antalgique, AntiInflammatoire, Antibiotique, Antidiabetique,
            Antihypertenseur, AntiUlcereux, Anticoagulant]:
    print(f"     {cls.name:20s}: {', '.join(i.name for i in cls.instances())}")
print("\n  >> Effets secondaires de Brufen :")
for e in brufen.peutProvoquer:
    print(f"     - {e.nomEffet} ({e.frequence}, gravite {e.graviteEffet})")
print("\n  >> Medicaments interagissant avec Coumadine :")
for m in coumadine.interagitAvec:
    print(f"     - {m.name}")
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
except Exception as e:
    print(f"  [!] HermiT : {e}")
    try:
        with onto:
            sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)
        print("  [OK] Pellet termine.")
    except Exception as e2:
        print(f"  [!] Pellet : {e2}")
        print("  -> Installez Java JRE >= 8 pour activer le raisonnement.")
print(f"  EffetGrave infere                   : {[i.name for i in EffetGrave.instances()]}")
print(f"  MedicamentARisque infere            : {[i.name for i in MedicamentARisque.instances()]}")
print(f"  MedicamentSurOrdonnance infere      : {[i.name for i in MedicamentSurOrdonnance.instances()]}")
print(f"  MedicamentEvalueCliniquement infere : {[i.name for i in MedicamentEvalueCliniquement.instances()]}")
print()

# ETAPE 11
print("=" * 65)
print("ETAPE 11 : Serialisation et sauvegarde")
print("=" * 65)
OWL_FILE = os.path.join(OUT_DIR, "ontologie_medicament.owl")
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
print("\n" + "=" * 65)
print(" Module Medicament -- owlready2 termine avec succes !")
print("=" * 65)
