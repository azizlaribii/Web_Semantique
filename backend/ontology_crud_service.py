# -*- coding: utf-8 -*-
"""
Service CRUD Ontologie OntoSanté
Permet :
- L'extraction dynamique des entités (Patients, Maladies, Symptômes, Médicaments, Médecins)
- La suppression ciblée d'une relation RDF (sans supprimer les individus ni les classes)
- La modification d'une relation RDF
- L'ajout d'une nouvelle relation ou d'un individu selon le contexte
"""
import os
import rdflib
from rdflib import Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTL_PATH = os.path.join(BASE_DIR, "ontologie_medicale (1).ttl")
MAL_OWL_PATH = os.path.join(BASE_DIR, "ontologie_maladie.owl")
PERS_OWL_PATH = os.path.join(BASE_DIR, "ontologie_personne.owl")

MED = Namespace("http://example.org/ontologie-medicale#")
MAL = Namespace("http://example.org/ontologie-maladie#")


def _clean_str(val):
    if not val:
        return ""
    s = str(val).strip()
    if "#" in s:
        return s.split("#")[-1]
    if "/" in s and s.startswith("http"):
        return s.split("/")[-1]
    return s


def get_dynamic_entities(unified_graph):
    """
    Extrait dynamiquement tous les individus et catégories pertinents depuis le graphe RDF.
    """
    g = unified_graph

    # 1. Patients
    patients = set()
    for s in g.subjects(RDF.type, MED.Patient):
        patients.add(_clean_str(s))
    for s in g.subjects(MED.souffreDe, None):
        patients.add(_clean_str(s))
    for o in g.objects(None, MAL.touche):
        patients.add(_clean_str(o))
    patients.discard("Patient")
    patients.discard("Thing")
    patients.discard("NamedIndividual")

    # 2. Maladies
    maladies = set()
    for o in g.objects(None, MED.souffreDe):
        maladies.add(_clean_str(o))
    for s in g.subjects(None, None):
        types = [str(t) for t in g.objects(s, RDF.type)]
        if any("Maladie" in t for t in types):
            maladies.add(_clean_str(s))
    # Nettoyage
    system_words = {"Maladie", "MaladieInfectieuse", "MaladieChronique", "MaladieDigestive", "NamedIndividual", "Thing"}
    maladies = {m for m in maladies if m and m not in system_words}

    # 3. Symptômes
    symptomes = set()
    for o in g.objects(None, MED.aPourSymptome):
        symptomes.add(_clean_str(o))
    for o in g.objects(None, MAL.aPourSymptome):
        symptomes.add(_clean_str(o))
    for s in g.subjects(None, None):
        types = [str(t) for t in g.objects(s, RDF.type)]
        if any("Symptome" in t for t in types):
            symptomes.add(_clean_str(s))
    symp_system = {"Symptome", "SymptomeGeneral", "SymptomeRespiratoire", "SymptomeDigestif", "NamedIndividual", "Thing"}
    symptomes = {s for s in symptomes if s and s not in symp_system}

    # 4. Médicaments
    medicaments = set()
    for o in g.objects(None, MED.estTraiteePar):
        medicaments.add(_clean_str(o))
    for s in g.subjects(RDF.type, MED.Medicament):
        medicaments.add(_clean_str(s))
    med_system = {"Medicament", "Antibiotique", "Antalgique", "AntiInflammatoire", "NamedIndividual", "Thing"}
    medicaments = {m for m in medicaments if m and m not in med_system}

    # 5. Médecins
    medecins = set()
    for s in g.subjects(RDF.type, MED.Medecin):
        medecins.add(_clean_str(s))
    for s in g.subjects(MED.soigne, None):
        medecins.add(_clean_str(s))
    for s in g.subjects(MED.diagnostique, None):
        medecins.add(_clean_str(s))
    medecins.discard("Medecin")
    medecins.discard("NamedIndividual")
    medecins.discard("Thing")

    return {
        "patients": sorted(list(patients)),
        "maladies": sorted(list(maladies)),
        "symptomes": sorted(list(symptomes)),
        "medicaments": sorted(list(medicaments)),
        "medecins": sorted(list(medecins)),
        "types_maladie": ["MaladieInfectieuse", "MaladieChronique", "MaladieDigestive"]
    }


def _resolve_uri(identifier, default_ns=MED):
    id_str = _clean_str(identifier).strip().replace(" ", "_")
    return default_ns[id_str]


def delete_relation(item, reload_callback=None):
    """
    Supprime uniquement le triplet de relation correspondant sans toucher aux individus ni aux classes.
    """
    if not os.path.exists(TTL_PATH):
        raise FileNotFoundError(f"Fichier ontologie non trouvé : {TTL_PATH}")

    g_ttl = rdflib.Graph()
    g_ttl.parse(TTL_PATH, format="turtle")
    g_ttl.bind("med", MED)

    deleted_count = 0
    p_str = item.get("patient") or item.get("patientAdulte") or ""
    m_str = item.get("maladie") or item.get("maladieInfectieuse") or item.get("id") or item.get("nom") or ""
    s_str = item.get("symptome") or item.get("symptomeGeneral") or item.get("symptomeCommun") or ""
    med_str = item.get("medicament") or item.get("nomMedicament") or ""
    doc_str = item.get("medecin") or ""

    # Cas 1 : Relation Patient -> Maladie
    if p_str and m_str:
        p_uri = _resolve_uri(p_str)
        m_uri = _resolve_uri(m_str)
        # Supprime (Patient, souffreDe, Maladie)
        for t in list(g_ttl.triples((p_uri, MED.souffreDe, m_uri))):
            g_ttl.remove(t)
            deleted_count += 1
        # Supprime éventuel inverse (Maladie, touche, Patient)
        for t in list(g_ttl.triples((m_uri, None, p_uri))):
            if "touche" in str(t[1]):
                g_ttl.remove(t)
                deleted_count += 1

    # Cas 2 : Relation Maladie -> Symptome
    elif m_str and s_str:
        m_uri = _resolve_uri(m_str)
        s_uri = _resolve_uri(s_str)
        for t in list(g_ttl.triples((m_uri, MED.aPourSymptome, s_uri))):
            g_ttl.remove(t)
            deleted_count += 1
        for t in list(g_ttl.triples((m_uri, MAL.aPourSymptome, s_uri))):
            g_ttl.remove(t)
            deleted_count += 1

    # Cas 3 : Relation Maladie -> Medicament
    elif m_str and med_str:
        m_uri = _resolve_uri(m_str)
        med_uri = _resolve_uri(med_str)
        for t in list(g_ttl.triples((m_uri, MED.estTraiteePar, med_uri))):
            g_ttl.remove(t)
            deleted_count += 1

    # Cas 4 : Relation Médecin -> Maladie ou Patient
    elif doc_str:
        doc_uri = _resolve_uri(doc_str)
        if m_str:
            m_uri = _resolve_uri(m_str)
            for t in list(g_ttl.triples((doc_uri, MED.diagnostique, m_uri))):
                g_ttl.remove(t)
                deleted_count += 1
        if p_str:
            p_uri = _resolve_uri(p_str)
            for t in list(g_ttl.triples((doc_uri, MED.soigne, p_uri))):
                g_ttl.remove(t)
                deleted_count += 1

    # Cas 5 : Individu simple si aucune relation croisée (ex: Suppression d'une carte Maladie)
    elif m_str and not (p_str or s_str or med_str or doc_str):
        m_uri = _resolve_uri(m_str)
        target = _clean_str(m_str)
        for s, p, o in list(g_ttl.triples((None, None, None))):
            s_clean = _clean_str(s)
            o_clean = _clean_str(o)
            if s_clean == target or str(s) == str(m_uri):
                if p != RDF.type or o != OWL.Class:
                    g_ttl.remove((s, p, o))
                    deleted_count += 1
            elif o_clean == target or str(o) == str(m_uri):
                g_ttl.remove((s, p, o))
                deleted_count += 1

    # Sauvegarde Turtle propre
    g_ttl.serialize(destination=TTL_PATH, format="turtle")

    if reload_callback:
        reload_callback(f"Suppression relation RDF ({deleted_count} triplet(s) supprimé(s))")

    return {
        "success": True,
        "deleted_count": deleted_count,
        "message": f"Élément supprimé avec succès ({deleted_count} triplet(s) retiré(s) de l'ontologie)."
    }


def update_relation(old_item, new_item, reload_callback=None):
    """
    Modifie une relation RDF : retire l'ancien triplet et insère le nouveau triplet.
    """
    if not os.path.exists(TTL_PATH):
        raise FileNotFoundError(f"Fichier ontologie non trouvé : {TTL_PATH}")

    g_ttl = rdflib.Graph()
    g_ttl.parse(TTL_PATH, format="turtle")
    g_ttl.bind("med", MED)

    # 1. Supprimer l'ancienne relation
    old_p = old_item.get("patient") or ""
    old_m = old_item.get("maladie") or ""
    new_p = new_item.get("patient") or old_p
    new_m = new_item.get("maladie") or old_m

    if old_p and old_m:
        old_p_uri = _resolve_uri(old_p)
        old_m_uri = _resolve_uri(old_m)
        for t in list(g_ttl.triples((old_p_uri, MED.souffreDe, old_m_uri))):
            g_ttl.remove(t)

        new_p_uri = _resolve_uri(new_p)
        new_m_uri = _resolve_uri(new_m)
        g_ttl.add((new_p_uri, MED.souffreDe, new_m_uri))

    # Cas Maladie -> Symptome
    old_s = old_item.get("symptome") or ""
    new_s = new_item.get("symptome") or old_s
    if old_m and old_s:
        old_m_uri = _resolve_uri(old_m)
        old_s_uri = _resolve_uri(old_s)
        for t in list(g_ttl.triples((old_m_uri, MED.aPourSymptome, old_s_uri))):
            g_ttl.remove(t)
        new_m_uri = _resolve_uri(new_m)
        new_s_uri = _resolve_uri(new_s)
        g_ttl.add((new_m_uri, MED.aPourSymptome, new_s_uri))

    # Cas Maladie -> Medicament
    old_med = old_item.get("medicament") or ""
    new_med = new_item.get("medicament") or old_med
    if old_m and old_med:
        old_m_uri = _resolve_uri(old_m)
        old_med_uri = _resolve_uri(old_med)
        for t in list(g_ttl.triples((old_m_uri, MED.estTraiteePar, old_med_uri))):
            g_ttl.remove(t)
        new_m_uri = _resolve_uri(new_m)
        new_med_uri = _resolve_uri(new_med)
        g_ttl.add((new_m_uri, MED.estTraiteePar, new_med_uri))

    # Cas Modification d'une maladie seule (nom / label / type / gravite)
    old_m_single = old_item.get("maladie") or old_item.get("maladieInfectieuse") or old_item.get("id") or old_item.get("nom") or ""
    new_m_single = new_item.get("maladie") or new_item.get("maladieInfectieuse") or new_item.get("id") or old_m_single
    if old_m_single and not (old_p or old_s or old_med):
        old_m_uri = _resolve_uri(old_m_single)
        new_m_uri = _resolve_uri(new_m_single)
        new_nom = new_item.get("nom") or new_item.get("label") or _clean_str(new_m_uri).replace("_", " ")
        target = _clean_str(old_m_single)
        for s, p, o in list(g_ttl.triples((None, None, None))):
            if _clean_str(s) == target or str(s) == str(old_m_uri):
                if p in [RDFS.label, MED.nom]:
                    g_ttl.remove((s, p, o))
                elif p == MED.gravite and new_item.get("gravite"):
                    g_ttl.remove((s, p, o))
                elif p == RDF.type and new_item.get("type"):
                    if any(t in str(o) for t in ["MaladieInfectieuse", "MaladieChronique", "MaladieDigestive"]):
                        g_ttl.remove((s, p, o))
        g_ttl.add((new_m_uri, RDFS.label, Literal(new_nom, lang="fr")))
        g_ttl.add((new_m_uri, RDFS.label, Literal(new_nom)))
        g_ttl.add((new_m_uri, MED.nom, Literal(new_nom)))
        if new_item.get("gravite"):
            g_ttl.add((new_m_uri, MED.gravite, Literal(str(new_item["gravite"]))))
        if new_item.get("type"):
            g_ttl.add((new_m_uri, RDF.type, _resolve_uri(new_item["type"])))

    # Sauvegarde
    g_ttl.serialize(destination=TTL_PATH, format="turtle")

    if reload_callback:
        reload_callback("Modification relation RDF dans l'ontologie")

    return {
        "success": True,
        "message": "Relation modifiée avec succès dans l'ontologie.",
        "updated_item": new_item
    }


def add_contextual_item(data_type, data, reload_callback=None):
    """
    Ajoute une relation ou entité contextuelle dans l'ontologie en fonction du formulaire soumis.
    """
    if not os.path.exists(TTL_PATH):
        raise FileNotFoundError(f"Fichier ontologie non trouvé : {TTL_PATH}")

    g_ttl = rdflib.Graph()
    g_ttl.parse(TTL_PATH, format="turtle")
    g_ttl.bind("med", MED)

    item_added = {}

    if data_type == "relation_patient_maladie":
        patient = data.get("nouveau_patient", "").strip() or data.get("patient", "").strip()
        maladie = data.get("nouvelle_maladie", "").strip() or data.get("maladie", "").strip()
        if not patient or not maladie:
            raise ValueError("Le patient et la maladie sont obligatoires.")
        p_uri = _resolve_uri(patient)
        m_uri = _resolve_uri(maladie)
        # S'assurer que le patient et la maladie sont déclarés comme individus
        g_ttl.add((p_uri, RDF.type, MED.Patient))
        g_ttl.add((p_uri, RDF.type, OWL.NamedIndividual))
        g_ttl.add((p_uri, RDFS.label, Literal(patient.replace("_", " "))))

        g_ttl.add((m_uri, RDF.type, MED.Maladie))
        g_ttl.add((m_uri, RDF.type, OWL.NamedIndividual))
        g_ttl.add((m_uri, RDFS.label, Literal(maladie.replace("_", " "))))

        g_ttl.add((p_uri, MED.souffreDe, m_uri))
        item_added = {
            "patient": _clean_str(p_uri),
            "maladie": _clean_str(m_uri),
            "maladieInfectieuse": _clean_str(m_uri)
        }

    elif data_type == "relation_maladie_symptome":
        maladie = data.get("nouvelle_maladie", "").strip() or data.get("maladie", "").strip()
        symptome = data.get("nouveau_symptome", "").strip() or data.get("symptome", "").strip()
        if not maladie or not symptome:
            raise ValueError("La maladie et le symptôme sont obligatoires.")
        m_uri = _resolve_uri(maladie)
        s_uri = _resolve_uri(symptome)
        g_ttl.add((m_uri, RDF.type, MED.Maladie))
        g_ttl.add((m_uri, RDF.type, OWL.NamedIndividual))
        g_ttl.add((s_uri, RDF.type, MED.Symptome))
        g_ttl.add((s_uri, RDF.type, OWL.NamedIndividual))
        g_ttl.add((s_uri, RDFS.label, Literal(symptome.replace("_", " "))))
        g_ttl.add((m_uri, MED.aPourSymptome, s_uri))
        item_added = {
            "maladie": _clean_str(m_uri),
            "maladieInfectieuse": _clean_str(m_uri),
            "symptome": _clean_str(s_uri)
        }

    elif data_type == "symptome_commun":
        symptome = data.get("nouveau_symptome", "").strip() or data.get("symptome", "").strip()
        if not symptome:
            raise ValueError("Le nom du symptôme est obligatoire.")
        s_uri = _resolve_uri(symptome)
        m1_uri = _resolve_uri(data.get("maladie1", "Grippe"))
        m2_uri = _resolve_uri(data.get("maladie2", "Angine"))
        g_ttl.add((s_uri, RDF.type, MED.Symptome))
        g_ttl.add((s_uri, RDF.type, OWL.NamedIndividual))
        g_ttl.add((s_uri, RDFS.label, Literal(symptome.replace("_", " "))))
        g_ttl.add((m1_uri, MED.aPourSymptome, s_uri))
        g_ttl.add((m2_uri, MED.aPourSymptome, s_uri))
        item_added = {
            "symptomeCommun": _clean_str(s_uri),
            "symptome": _clean_str(s_uri),
            "maladie": "Grippe, Angine",
            "maladieInfectieuse": "Grippe, Angine"
        }

    elif data_type == "entity_symptome":
        symptome = data.get("nouveau_symptome", "").strip() or data.get("symptome", "").strip() or data.get("nom", "").strip()
        cat = data.get("type_symptome", "SymptomeGeneral").strip()
        if not symptome:
            raise ValueError("Le nom du symptôme est obligatoire.")
        s_uri = _resolve_uri(symptome)
        cat_uri = _resolve_uri(cat)
        g_ttl.add((s_uri, RDF.type, cat_uri))
        g_ttl.add((s_uri, RDF.type, MED.Symptome))
        g_ttl.add((s_uri, RDF.type, OWL.NamedIndividual))
        g_ttl.add((s_uri, RDFS.label, Literal(symptome.replace("_", " "))))
        item_added = {
            "symptome": _clean_str(s_uri),
            "type_symptome": cat,
            "symptomeGeneral": _clean_str(s_uri),
            "symptomeDigestif": _clean_str(s_uri)
        }

    elif data_type == "relation_maladie_medicament":
        maladie = data.get("nouvelle_maladie", "").strip() or data.get("maladie", "").strip()
        medicament = data.get("nouveau_medicament", "").strip() or data.get("medicament", "").strip()
        if not maladie or not medicament:
            raise ValueError("La maladie et le médicament sont obligatoires.")
        m_uri = _resolve_uri(maladie)
        med_uri = _resolve_uri(medicament)
        g_ttl.add((m_uri, RDF.type, MED.Maladie))
        g_ttl.add((m_uri, RDF.type, OWL.NamedIndividual))
        g_ttl.add((med_uri, RDF.type, MED.Medicament))
        g_ttl.add((med_uri, RDF.type, OWL.NamedIndividual))
        g_ttl.add((med_uri, RDFS.label, Literal(medicament.replace("_", " "))))
        g_ttl.add((m_uri, MED.estTraiteePar, med_uri))
        item_added = {
            "maladie": _clean_str(m_uri),
            "maladieInfectieuse": _clean_str(m_uri),
            "medicament": _clean_str(med_uri),
            "nomMedicament": _clean_str(med_uri)
        }

    elif data_type == "relation_medecin_maladie":
        medecin = data.get("nouveau_medecin", "").strip() or data.get("medecin", "").strip()
        maladie = data.get("nouvelle_maladie", "").strip() or data.get("maladie", "").strip()
        if not medecin or not maladie:
            raise ValueError("Le médecin et la maladie sont obligatoires.")
        d_uri = _resolve_uri(medecin)
        m_uri = _resolve_uri(maladie)
        g_ttl.add((d_uri, RDF.type, MED.Medecin))
        g_ttl.add((d_uri, RDF.type, OWL.NamedIndividual))
        g_ttl.add((m_uri, RDF.type, MED.Maladie))
        g_ttl.add((m_uri, RDF.type, OWL.NamedIndividual))
        g_ttl.add((d_uri, MED.diagnostique, m_uri))
        item_added = {
            "medecin": _clean_str(d_uri),
            "maladie": _clean_str(m_uri),
            "maladieInfectieuse": _clean_str(m_uri)
        }

    elif data_type == "entity_maladie":
        nom = data.get("nom", "").strip() or data.get("nouvelle_maladie", "").strip() or data.get("maladie", "").strip()
        cat = data.get("type", "MaladieInfectieuse").strip()
        if not nom:
            raise ValueError("Le nom de la maladie est obligatoire.")
        m_uri = _resolve_uri(nom)
        cat_uri = _resolve_uri(cat)
        g_ttl.add((m_uri, RDF.type, cat_uri))
        g_ttl.add((m_uri, RDF.type, OWL.NamedIndividual))
        g_ttl.add((m_uri, RDFS.label, Literal(nom, lang="fr")))
        g_ttl.add((m_uri, RDFS.label, Literal(nom)))
        g_ttl.add((m_uri, MED.nom, Literal(nom)))
        if data.get("gravite"):
            g_ttl.add((m_uri, MED.gravite, Literal(str(data["gravite"]))))
        item_added = {
            "maladie": _clean_str(m_uri),
            "maladieInfectieuse": _clean_str(m_uri),
            "nom": nom,
            "label": nom,
            "type": cat
        }

    elif data_type == "entity_patient":
        nom = data.get("nom", "").strip()
        if not nom:
            raise ValueError("Le nom du patient est obligatoire.")
        p_uri = _resolve_uri(nom)
        g_ttl.add((p_uri, RDF.type, MED.Patient))
        g_ttl.add((p_uri, RDF.type, OWL.NamedIndividual))
        g_ttl.add((p_uri, MED.nom, Literal(nom)))
        if data.get("age"):
            g_ttl.add((p_uri, MED.age, Literal(int(data["age"]), datatype=XSD.integer)))
        if data.get("telephone"):
            g_ttl.add((p_uri, MED.telephone, Literal(str(data["telephone"]))))
        if data.get("cin"):
            g_ttl.add((p_uri, MED.cin, Literal(str(data["cin"]))))
        item_added = {"patient": _clean_str(p_uri), "nom": nom}

    else:
        raise ValueError(f"Type de données non supporté : {data_type}")

    # Sauvegarde
    g_ttl.serialize(destination=TTL_PATH, format="turtle")

    if reload_callback:
        reload_callback(f"Ajout ontologique ({data_type})")

    return {
        "success": True,
        "message": "Élément enregistré avec succès dans l'ontologie.",
        "item": item_added
    }
