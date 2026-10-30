# -*- coding: utf-8 -*-
"""Tests du module IA Service administratif : intentions, entites, fautes de frappe, resultats + validation croisee."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sklearn.model_selection import StratifiedKFold, cross_val_score
from administratif_service import get_service
from ia_administratif_service import IAAdministratifService

# (question, intention attendue, nb minimal de resultats ou None)
CAS = [
 ("Quels sont les rendez-vous de Sami ?", "rdv_patient", 2),
 ("Montre-moi le planning de Patient Ahmed", "rdv_patient", 2),
 ("agenda du docteur Fatima", "rdv_medecin", 2),
 ("rendez-vous avec dr Ahmed", "rdv_medecin", 3),
 ("Quels rendez-vous sont annules ?", "rdv_statut", 1),
 ("rdv confirmes", "rdv_statut", 2),
 ("rendez-vous qui ne sont pas annules", "rdv_statut", 7),
 ("Quels sont les prochains rendez-vous ?", "rdv_a_venir", 3),
 ("Liste de tous les rendez-vous", "rdv_liste", 8),
 ("Quelles factures restent a payer ?", "facture_impayee", 3),
 ("liste des impayes", "facture_impayee", 3),
 ("Combien doit Sara ?", "facture_patient", 1),
 ("quelle est la facture la plus chere", "facture_max", 1),
 ("montre toutes les factures", "facture_liste", 6),
 ("Qui a paye par carte ?", "paiement_mode", 2),
 ("paiements en especes", "paiement_mode", 1),
 ("historique des paiements", "paiement_liste", 4),
 ("quelles factures sont remboursees", "remboursement_liste", 2),
 ("Qu'a rembourse la CNAM ?", "remboursement_assurance", 1, "ASSURANCE"),
 ("Qui est assure chez la STAR ?", "patients_assures", 1, "ASSURANCE"),
 ("patients sans assurance", "patients_non_assures", 1),
 ("liste des assurances", "assurance_liste", 3),
 ("dossier de Amina", "dossier_patient", 1),
 ("Dans quelle salle est Sami ?", "dossier_patient", 1),
 ("dossiers actifs", "dossier_liste", 5),
 ("dossiers archives", "dossier_liste", 1),
 ("chiffre d'affaires", "chiffre_affaires", 1),
 ("Quel medecin a le plus de rendez-vous ?", "medecin_plus_rdv", 1),
 # fautes de frappe (difflib)
 ("rendez-vous de Smai", "rdv_patient", 2),
 ("agenda du docteur Fatma", "rdv_medecin", 2),
 ("dossier de Aminna", "dossier_patient", 1),
]

def main():
    ia = IAAdministratifService(get_service())
    ok = 0
    for cas in CAS:
        q, attendu, nmin = cas[:3]
        ent_attendue = cas[3] if len(cas) > 3 else None          # type d'entite obligatoire (optionnel)
        r = ia.answer_question(q)
        bon = r["intention"] == attendu and (nmin is None or r["count"] >= nmin)
        if ent_attendue:
            bon = bon and any(e["type"] == ent_attendue for e in r["nlp"]["entites"]) and r["count"] < 4
        ok += bon
        print(f"[{'OK ' if bon else 'ECHEC'}] {q:48s} -> {r['intention']:24s} ({r['nlp']['intention_retenue']['confiance']:.2f}) n={r['count']}")
        if not bon: print(f"        attendu : {attendu} / >= {nmin} resultats")
    print(f"\n{ok}/{len(CAS)} questions correctes.")
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=0)
    sc = cross_val_score(ia.clf, ia.X, ia.y, cv=cv)
    print(f"Validation croisee (3 plis, {ia.training_size} phrases, {len(ia.labels)} intentions) : {sc.mean()*100:.0f} %")
    return ok == len(CAS)

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
