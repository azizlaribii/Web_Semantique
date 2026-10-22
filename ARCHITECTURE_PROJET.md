# Architecture du Projet Web Sémantique — Classe Personne

Ce document décrit l'implémentation complète de l'architecture logicielle présentée sur la diapositive du projet, spécialisée pour la **classe `Personne`** (Médecins, Patients, Stagiaires, Personnel Médical).

---

## 📐 Schéma d'Architecture & Correspondance Technique

```
┌─────────────────────────────────┐
│     Front-end (Interfaces)      │
│  HTML5 / Modern CSS / Vanilla   │
└────────────────┬────────────────┘
                 │ (1) Question Utilisateur (Langage Naturel)
                 ▼
┌─────────────────────────────────┐
│          Module IA (API)        │
│  Moteur Sémantique NLP ➔ SPARQL │
└────────────────┬────────────────┘
                 │ (2) Requête SPARQL générée
                 ▼
┌─────────────────────────────────┐
│        Fuseki (API SPARQL)      │
│  Endpoint HTTP JSON standard    │
└────────────────┬────────────────┘
                 │ (3) Exécution SPARQL / Bindings
                 ▼
┌─────────────────────────────────┐
│   Back-end (Python + RDFLib)    │
│  Moteur Flask & Graphe RDFLib   │
└────────────────┬────────────────┘
                 │ (4) Triplets & Hiérarchie OWL
                 ▼
┌─────────────────────────────────┐
│     Protégé / Ontologie OWL     │
│     ontologie_personne.owl      │
└─────────────────────────────────┘
```

---

## 📁 Organisation des Fichiers

```
web_sémantique/
├── ontologie_personne.owl      # Fichier OWL officiel (Protégé / Owlready2) pour Personne
├── ontologie_medicale (1).ttl  # Source Turtle globale
├── personne_owlready2.py       # Script Python de manipulation Owlready2
├── run_app.py                  # LANCEUR en 1 clic (démarre le serveur & ouvre le navigateur)
│
├── backend/
│   ├── app.py                 # Serveur Flask principal (Back-end)
│   ├── rdflib_service.py      # Moteur Python + RDFLib (Gestion du graphe & SPARQL)
│   ├── fuseki_api.py          # Couche API compatible Apache Jena Fuseki JSON
│   └── ia_service.py          # Module IA (Traduction Question -> SPARQL)
│
└── frontend/
    ├── index.html             # Interface web complète avec animations du flux
    ├── style.css              # Design moderne glassmorphism (Dark mode & visual pipeline)
    └── app.js                 # Logique frontend, console SPARQL & graphe interactif
```

---

## 🚀 Comment Lancer le Projet ?

Ouvrez un terminal dans le dossier et exécutez simplement :

```powershell
python run_app.py
```

Le serveur Flask démarre sur `http://127.0.0.1:5000` et **ouvre automatiquement votre navigateur web**.

---

## 🔍 Les Composants Détaillés

### 1. Front-end (Interfaces Utilisateurs)
- **Barre de flux en direct** : anime en temps réel le passage de la question de gauche à droite à travers les 5 briques de la diapositive.
- **Onglet Assistant IA** : posez n'importe quelle question en français (ex : *"Qui soigne Sami ?"*, *"Quels sont les cardiologues ?"*).
- **Onglet Individus & Rôles** : fiches complètes avec filtres dynamiques (Médecins, Patients adultes, Patients enfants, Stagiaires).
- **Onglet Console SPARQL** : éditeur de requêtes direct avec exemples pré-configurés et mesure du temps d'exécution.
- **Onglet Graphe Sémantique** : réseau interactif (Vis.js) montrant les relations `soigne`, `connait`, `presente`, etc.

### 2. Module IA (API NLP ➔ SPARQL)
- Situé dans `backend/ia_service.py`.
- Analyse les intentions sémantiques de la question utilisateur.
- Identifie les entités médicales (`Cardiologue`, `Dr_Ahmed`, `Sami`, `PatientEnfant`, etc.).
- Construit automatiquement la requête SPARQL optimale avec les préfixes et les jointures d'ontologie.
- Fournit une explication claire en français de la déduction effectuée.

### 3. Fuseki (API SPARQL JSON)
- Situé dans `backend/fuseki_api.py`.
- Expose les endpoints `/api/sparql` et `/api/fuseki/query`.
- Format de réponse standard **SPARQL 1.1 Query Results JSON Format** (`head/vars` et `results/bindings`).
- Permet l'interrogation directe via curl, Postman ou Apache Jena.

### 4. Back-end (Python + RDFLib)
- Situé dans `backend/rdflib_service.py` et `backend/app.py`.
- Charge le fichier OWL via `rdflib.Graph()`.
- Gère les inférences de symétrie (relation `:connait`) et inverse (`:soigne` / `:estSoignePar`).

### 5. Protégé & OWL (Classe Personne)
- Fichier `ontologie_personne.owl`.
- Conforme aux règles d'ingénierie ontologique :
  - Disjonctions : `Medecin` disjoint de `Patient`, `PatientAdulte` disjoint de `PatientEnfant`.
  - Propriétés d'objet : `joueLeRoleDe`, `soigne`, `estSoignePar`, `connait`, `aConsulte`, `presente`.
  - Propriétés de données : `nom`, `age`, `numeroCIN`, `specialite`, `numeroOrdre`, `numeroDossier`, `groupeSanguin`.

---

## 🤝 Intégration avec les Autres Membres du Groupe

Pour fusionner les classes des autres membres (ex: `Maladie`, `Consultation`, `Medicament`) :
1. Ils ajoutent leurs classes et triplets dans l'ontologie globale ou fournissent leur fichier OWL.
2. Le moteur `rdflib_service.py` charge directement le fichier complet sans modification de code nécessaire.
3. Le module IA peut être enrichi de nouvelles règles de mots-clés dans `ia_service.py` pour leurs classes respectives.

---

# 💊 Module Médicament

Le module Médicament suit la même architecture que les modules Personne et Maladie :
**Front-end → Module IA → SPARQL → RDFLib → `ontologie_medicament.owl`**.

## Fichiers ajoutés

```
web_sémantique/
├── medicament_owlready2.py         # Script Owlready2 : crée l'ontologie + raisonneur HermiT
├── ontologie_medicament.owl        # Ontologie générée (ouvrable dans Protégé)
├── backend/
│   ├── medicament_service.py       # Service RDFLib (médicaments, graphe, résumé)
│   ├── ia_medicament_service.py    # Module IA : question en français -> SPARQL
│   └── test_ia_medicament.py       # 30 tests de l'IA (SPARQL + nombre de résultats)
└── frontend/
    └── medicament.js               # Onglet « Module Médicament » (IA, fiches, filtres, graphe)
```

Fichiers modifiés : `backend/app.py` (routes), `frontend/index.html` (onglet), `frontend/style.css` (styles),
`frontend/app.js` (onglets de résultats limités à leur module), `run_app.py` (message de démarrage).

## Ontologie (`http://example.org/ontologie-medicament#`, préfixe `mdc:`)

- **Classes** : `Medicament` (sous-classes `Antalgique`, `AntiInflammatoire`, `Antibiotique`, `Antidiabetique`,
  `Antihypertenseur`, `AntiUlcereux`, `Anticoagulant`), `Molecule`, `EffetSecondaire` (7 familles),
  `ConditionClinique`, `InteractionMedicamenteuse`, `EssaiClinique`.
- **Propriétés d'objet** : `contientMolecule`, `peutProvoquer`, `traite` et `estContreIndiquePour` (vers les maladies
  `mal:` du module Maladie), `estContreIndiqueEn`, `interagitAvec` (symétrique), `impliqueMedicament`, `evalue`, `aObserveEffet`.
- **Propriétés de données** : `nomCommercial`, `dosage`, `formeGalenique`, `posologie`, `codeATC`, `prixTND`,
  `necessiteOrdonnance`, `formuleBrute`, `masseMolaire`, `frequence`, `graviteEffet`, `phase`, `tauxEfficacite`…
- **Classes définies (inférées par HermiT)** : `EffetGrave`, `MedicamentARisque`, `MedicamentSurOrdonnance`,
  `MedicamentEvalueCliniquement`.
- Les données des essais cliniques et les prix sont des valeurs **pédagogiques fictives**.

## Routes API

| Route | Méthode | Rôle |
|---|---|---|
| `/api/medicaments` | GET | Fiches complètes des médicaments |
| `/api/graph-medicament` | GET | Nœuds et liens du graphe |
| `/api/summary-medicament` | GET | Statistiques du module |
| `/api/ia-medicament/ask` | POST `{"question": "..."}` | Question en français → SPARQL → résultats |

## Régénérer l'ontologie et tester

```powershell
python medicament_owlready2.py        # régénère ontologie_medicament.owl (Java requis pour HermiT)
python backend/test_ia_medicament.py  # vérifie l'IA Médicament
python run_app.py                     # lance l'application
```
